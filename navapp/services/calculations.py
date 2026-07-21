from __future__ import annotations

import calendar
from collections.abc import Iterable
from contextlib import suppress
from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal, localcontext
from functools import reduce
from operator import mul

from django.core.exceptions import ObjectDoesNotExist

FORMULA_VERSION = "legacy_excel_v1"


@dataclass(frozen=True, slots=True)
class NavPoint:
    valuation_month: date
    valuation_date: date
    nav: Decimal
    revision: int = 1


class CalculationValidationError(ValueError):
    def __init__(self, issues: list[str]):
        self.issues = issues
        super().__init__("; ".join(issues))


def month_end(value: date) -> date:
    return value.replace(day=calendar.monthrange(value.year, value.month)[1])


def next_month(value: date) -> date:
    year = value.year + (1 if value.month == 12 else 0)
    month = 1 if value.month == 12 else value.month + 1
    return date(year, month, calendar.monthrange(year, month)[1])


def _decimal(value: object) -> Decimal:
    return value if isinstance(value, Decimal) else Decimal(str(value))


def validate_nav_points(
    points: Iterable[NavPoint], inception_date: date, report_end: date
) -> list[NavPoint]:
    ordered = sorted(
        (p for p in points if p.valuation_month <= report_end), key=lambda p: p.valuation_month
    )
    issues: list[str] = []
    if not ordered:
        issues.append("報告截止日前沒有 NAV 觀察值。")
        raise CalculationValidationError(issues)

    seen: set[date] = set()
    for point in ordered:
        if point.nav <= 0:
            issues.append(f"{point.valuation_month:%Y-%m} 的 NAV 必須大於零。")
        if point.valuation_month != month_end(point.valuation_month):
            issues.append(f"估值月份 {point.valuation_month} 不是日曆月底。")
        if point.valuation_month in seen:
            issues.append(f"NAV 月份重複：{point.valuation_month:%Y-%m}。")
        seen.add(point.valuation_month)

    expected_first = month_end(inception_date)
    if ordered[0].valuation_month != expected_first:
        issues.append(
            f"首個 NAV 月份必須是成立月份 {expected_first:%Y-%m}；"
            f"目前為 {ordered[0].valuation_month:%Y-%m}。"
        )

    current = ordered[0].valuation_month
    for point in ordered[1:]:
        expected = next_month(current)
        if point.valuation_month != expected:
            issues.append(f"在 {point.valuation_month:%Y-%m} 前缺少 NAV 月份 {expected:%Y-%m}。")
        current = point.valuation_month

    if ordered[-1].valuation_month != report_end:
        issues.append(f"缺少 {report_end:%Y-%m} 的季末 NAV。")
    if issues:
        raise CalculationValidationError(issues)
    return ordered


def monthly_returns(points: list[NavPoint], inception_nav: Decimal) -> list[Decimal]:
    if inception_nav <= 0:
        raise CalculationValidationError(["成立時 NAV 必須大於零。"])
    returns: list[Decimal] = []
    prior = inception_nav
    for point in points:
        returns.append(point.nav / prior - Decimal(1))
        prior = point.nav
    return returns


def sample_standard_deviation(values: list[Decimal]) -> Decimal | None:
    if len(values) < 2:
        return None
    with localcontext() as ctx:
        ctx.prec = 50
        count = Decimal(len(values))
        mean = sum(values, Decimal(0)) / count
        variance = sum(((value - mean) ** 2 for value in values), Decimal(0)) / (count - 1)
        return +variance.sqrt()


def quarterly_matrix(
    points: list[NavPoint], inception_nav: Decimal, report_end: date
) -> dict[str, dict[str, Decimal | None]]:
    quarter_ends = [p for p in points if p.valuation_month.month in {3, 6, 9, 12}]
    matrix: dict[str, dict[str, Decimal | None]] = {}
    previous_quarter_nav: Decimal | None = None
    for point in quarter_ends:
        year_key = str(point.valuation_month.year)
        row = matrix.setdefault(
            year_key, {"q1": None, "q2": None, "q3": None, "q4": None, "ytd": None}
        )
        baseline = previous_quarter_nav if previous_quarter_nav is not None else inception_nav
        row[f"q{((point.valuation_month.month - 1) // 3) + 1}"] = point.nav / baseline - 1
        previous_quarter_nav = point.nav

    years = sorted({point.valuation_month.year for point in points})
    by_month = {point.valuation_month: point for point in points}
    for year in years:
        year_points = [p for p in points if p.valuation_month.year == year]
        if not year_points:
            continue
        latest = max(year_points, key=lambda p: p.valuation_month)
        previous_december = by_month.get(date(year - 1, 12, 31))
        baseline = previous_december.nav if previous_december else inception_nav
        matrix.setdefault(str(year), {"q1": None, "q2": None, "q3": None, "q4": None, "ytd": None})[
            "ytd"
        ] = latest.nav / baseline - 1
    return matrix


def maximum_drawdown(points: list[NavPoint], inception_nav: Decimal) -> Decimal:
    peak = inception_nav
    minimum = Decimal(0)
    for point in points:
        peak = max(peak, point.nav)
        minimum = min(minimum, point.nav / peak - 1)
    return minimum


def day_based_cagr(latest_nav: Decimal, inception_nav: Decimal, actual_days: int) -> Decimal | None:
    if actual_days <= 0:
        return None
    with localcontext() as ctx:
        ctx.prec = 50
        ratio = latest_nav / inception_nav
        exponent = Decimal("365.25") / Decimal(actual_days)
        return +((ratio.ln() * exponent).exp() - 1)


def round_for_display(value: Decimal | None, places: int) -> Decimal | None:
    if value is None:
        return None
    quantum = Decimal(1).scaleb(-places)
    return value.quantize(quantum, rounding=ROUND_HALF_UP)


def format_percent(value: Decimal | None, places: int = 2) -> str:
    if value is None:
        return "N/A"
    rounded = round_for_display(value * 100, places)
    return f"{rounded:.{places}f}%"


def format_decimal(value: Decimal | None, places: int = 3) -> str:
    if value is None:
        return "N/A"
    rounded = round_for_display(value, places)
    return f"{rounded:.{places}f}"


def _detail(
    name: str,
    formula: str,
    value: Decimal | None,
    display: str,
    inputs: dict[str, object],
    report_end: date,
    warning: str = "",
) -> dict[str, object]:
    return {
        "name": name,
        "formula_version": FORMULA_VERSION,
        "formula": formula,
        "inputs": {key: str(item) for key, item in inputs.items()},
        "raw": str(value) if value is not None else None,
        "display": display,
        "data_cutoff": report_end.isoformat(),
        "validation_status": "PASS" if value is not None else "N/A",
        "warning": warning,
    }


def calculate_performance(
    *,
    points: Iterable[NavPoint],
    inception_nav: Decimal,
    inception_date: date,
    report_end: date,
    annual_rfr_decimal: Decimal | None = None,
    percentage_places: int = 2,
    sharpe_places: int = 3,
    report_type: str = "QUARTERLY",
) -> dict[str, object]:
    if report_type not in {"MONTHLY", "QUARTERLY"}:
        raise CalculationValidationError(["不支援的報告類型。"])
    if report_end != month_end(report_end):
        raise CalculationValidationError(["報告截止日必須為日曆月底。"])
    if report_type == "QUARTERLY" and report_end.month not in {3, 6, 9, 12}:
        raise CalculationValidationError(["報告截止日必須為日曆季度末日。"])
    inception_nav = _decimal(inception_nav)
    annual_rfr_decimal = _decimal(annual_rfr_decimal) if annual_rfr_decimal is not None else None
    ordered = validate_nav_points(points, inception_date, report_end)
    returns = monthly_returns(ordered, inception_nav)
    latest = ordered[-1]
    matrix = quarterly_matrix(ordered, inception_nav, report_end)
    latest_quarter = (
        matrix[str(report_end.year)][f"q{report_end.month // 3}"]
        if report_type == "QUARTERLY"
        else None
    )
    latest_period = latest_quarter if report_type == "QUARTERLY" else returns[-1]
    ytd = matrix[str(report_end.year)]["ytd"]
    itd = latest.nav / inception_nav - 1
    growth = reduce(mul, (Decimal(1) + value for value in returns), Decimal(1))
    annualized_return = growth ** (Decimal(12) / Decimal(len(returns))) - 1
    monthly_sd = sample_standard_deviation(returns)
    annualized_volatility = monthly_sd * Decimal(12).sqrt() if monthly_sd is not None else None
    t12_sd = sample_standard_deviation(returns[-12:]) if len(returns) >= 12 else None
    trailing_12_volatility = t12_sd * Decimal(12).sqrt() if t12_sd is not None else None
    count = Decimal(len(returns))
    positive = Decimal(sum(1 for value in returns if value > 0)) / count
    negative = Decimal(sum(1 for value in returns if value < 0)) / count
    zero = Decimal(sum(1 for value in returns if value == 0)) / count
    max_gain = max(returns)
    max_loss = min(returns)
    drawdown = maximum_drawdown(ordered, inception_nav)
    sharpe = None
    if (
        annual_rfr_decimal is not None
        and annualized_volatility is not None
        and annualized_volatility != 0
    ):
        sharpe = (annualized_return - annual_rfr_decimal) / annualized_volatility
    cagr = day_based_cagr(latest.nav, inception_nav, (report_end - inception_date).days)

    metrics = {
        "ytd_return": ytd,
        "itd_return": itd,
        "annualized_return": annualized_return,
        "annualized_volatility": annualized_volatility,
        "trailing_12_month_volatility": trailing_12_volatility,
        "positive_months": positive,
        "negative_months": negative,
        "zero_months": zero,
        "maximum_monthly_gain": max_gain,
        "maximum_monthly_loss": max_loss,
        "maximum_drawdown": drawdown,
        "annual_rfr": annual_rfr_decimal,
        "sharpe_ratio": sharpe,
        "day_based_cagr": cagr,
    }
    if report_type == "QUARTERLY":
        metrics = {"latest_quarter_return": latest_quarter, **metrics}
    else:
        metrics = {"latest_period_return": latest_period, **metrics}
    displays = {
        key: (
            format_decimal(value, sharpe_places)
            if key == "sharpe_ratio"
            else format_percent(
                value,
                0
                if key in {"positive_months", "negative_months", "zero_months"}
                else percentage_places,
            )
        )
        for key, value in metrics.items()
    }
    details = {
        "ytd_return": _detail(
            "YTD return",
            "Latest NAV / previous year-end NAV - 1",
            ytd,
            displays["ytd_return"],
            {"latest_nav": latest.nav},
            report_end,
        ),
        "itd_return": _detail(
            "ITD return",
            "Latest NAV / inception NAV - 1",
            itd,
            displays["itd_return"],
            {"latest_nav": latest.nav, "inception_nav": inception_nav},
            report_end,
        ),
        "annualized_return": _detail(
            "Annualized return",
            "PRODUCT(1 + monthly returns)^(12 / N) - 1",
            annualized_return,
            displays["annualized_return"],
            {"monthly_return_count": len(returns), "growth_factor": growth},
            report_end,
        ),
        "annualized_volatility": _detail(
            "Annualized volatility since inception",
            "STDEV.S(monthly returns) * SQRT(12)",
            annualized_volatility,
            displays["annualized_volatility"],
            {"monthly_return_count": len(returns), "monthly_sd": monthly_sd},
            report_end,
        ),
        "trailing_12_month_volatility": _detail(
            "Trailing 12-month volatility",
            "STDEV.S(latest 12 monthly returns) * SQRT(12)",
            trailing_12_volatility,
            displays["trailing_12_month_volatility"],
            {"available_returns": len(returns)},
            report_end,
        ),
        "maximum_drawdown": _detail(
            "Maximum drawdown",
            "MIN(NAV / dynamic running peak - 1)",
            drawdown,
            displays["maximum_drawdown"],
            {"observations": len(ordered), "inception_nav": inception_nav},
            report_end,
            warning="Intentional correction from the workbook fixed-cell result.",
        ),
        "sharpe_ratio": _detail(
            "Sharpe ratio",
            "(annualized return - annual RFR) / annualized volatility since inception",
            sharpe,
            displays["sharpe_ratio"],
            {
                "annualized_return": annualized_return,
                "annual_rfr": annual_rfr_decimal,
                "annualized_volatility": annualized_volatility,
            },
            report_end,
            warning=("Legacy workbook method; this is not a monthly excess-return Sharpe ratio."),
        ),
    }
    if report_type == "QUARTERLY":
        details = {
            "latest_quarter_return": _detail(
                "Latest quarter return",
                "Quarter-end NAV / previous quarter-end NAV - 1",
                latest_quarter,
                displays["latest_quarter_return"],
                {"report_end": report_end, "latest_nav": latest.nav},
                report_end,
            ),
            **details,
        }
    else:
        details = {
            "latest_period_return": _detail(
                "Latest month return",
                "NAV[t] / NAV[t-1] - 1",
                latest_period,
                displays["latest_period_return"],
                {"report_end": report_end, "latest_nav": latest.nav},
                report_end,
            ),
            **details,
        }

    monthly = [
        {
            "valuation_month": point.valuation_month.isoformat(),
            "valuation_date": point.valuation_date.isoformat(),
            "nav": str(point.nav),
            "revision": point.revision,
            "return_raw": str(return_value),
            "return_display": format_percent(return_value, percentage_places),
        }
        for point, return_value in zip(ordered, returns, strict=True)
    ]
    serial_matrix = {
        year: {
            key: {
                "raw": str(value) if value is not None else None,
                "display": format_percent(value, percentage_places) if value is not None else "—",
            }
            for key, value in row.items()
        }
        for year, row in matrix.items()
    }
    return {
        "report_type": report_type,
        "formula_version": FORMULA_VERSION,
        "report_end": report_end.isoformat(),
        "source_nav_version": ":".join(str(point.revision) for point in ordered),
        "monthly": monthly,
        "quarterly_matrix": serial_matrix,
        "metrics_raw": {
            key: str(value) if value is not None else None for key, value in metrics.items()
        },
        "metrics_display": displays,
        "details": details,
        "validation": {"status": "PASS", "issues": []},
    }


def calculate_for_report(report) -> dict[str, object]:
    rfr_value = None
    with suppress(ObjectDoesNotExist):
        rfr_value = report.rfr_snapshot.annual_value_decimal
    navs = report.share_class.nav_records.filter(
        is_active=True, valuation_month__lte=report.report_date
    ).order_by("valuation_month")
    points = [
        NavPoint(
            valuation_month=item.valuation_month,
            valuation_date=item.valuation_date,
            nav=item.nav_per_share,
            revision=item.revision,
        )
        for item in navs
    ]
    resolved = report.fund.resolved()
    return calculate_performance(
        points=points,
        inception_nav=report.share_class.inception_nav,
        inception_date=report.share_class.inception_date,
        report_end=report.report_date,
        annual_rfr_decimal=rfr_value,
        percentage_places=int(resolved["percentage_decimal_places"]),
        sharpe_places=int(resolved["sharpe_decimal_places"]),
        report_type=getattr(report, "report_type", "QUARTERLY"),
    )
