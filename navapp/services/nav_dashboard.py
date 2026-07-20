from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from io import BytesIO
from typing import TYPE_CHECKING

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

if TYPE_CHECKING:
    from navapp.models import NAVRecord


@dataclass(frozen=True, slots=True)
class DashboardMonth:
    month: int
    record: NAVRecord | None
    nav_display: str
    monthly_return: Decimal | None
    monthly_return_display: str
    monthly_return_class: str
    cumulative_return: Decimal | None
    cumulative_return_display: str
    cumulative_return_class: str
    is_next: bool = False


@dataclass(frozen=True, slots=True)
class DashboardYear:
    year: int
    months: tuple[DashboardMonth, ...]
    latest_nav_display: str
    latest_month_label: str
    return_label: str
    period_return: Decimal | None
    period_return_display: str
    period_return_class: str
    baseline_note: str
    high_nav_display: str
    high_month_label: str
    low_nav_display: str
    low_month_label: str
    has_records: bool
    is_current_input_year: bool


def _format_nav(value: Decimal | None, places: int = 6) -> str:
    if value is None:
        return "—"
    rounded = value.quantize(Decimal(1).scaleb(-places), rounding=ROUND_HALF_UP)
    return f"{rounded:.{places}f}"


def _format_percent(value: Decimal | None, places: int = 2) -> str:
    if value is None:
        return "—"
    rounded = (value * 100).quantize(Decimal(1).scaleb(-places), rounding=ROUND_HALF_UP)
    prefix = "+" if rounded > 0 else ""
    return f"{prefix}{rounded:.{places}f}%"


def _return_class(value: Decimal | None) -> str:
    if value is None or value == 0:
        return "nav-return-neutral"
    return "nav-return-positive" if value > 0 else "nav-return-negative"


def _months_are_consecutive(previous: date, current: date) -> bool:
    previous_index = previous.year * 12 + previous.month
    current_index = current.year * 12 + current.month
    return current_index == previous_index + 1


def build_nav_dashboard_years(
    records: Iterable[NAVRecord],
    *,
    next_period: date | None,
    default_period: date,
) -> list[DashboardYear]:
    ordered = sorted(records, key=lambda item: item.valuation_month)
    by_year: dict[int, list[NAVRecord]] = defaultdict(list)
    december_by_year: dict[int, NAVRecord] = {}
    for record in ordered:
        by_year[record.valuation_month.year].append(record)
        if record.valuation_month.month == 12:
            december_by_year[record.valuation_month.year] = record
    if next_period:
        by_year.setdefault(next_period.year, [])

    dashboard_years: list[DashboardYear] = []
    for year in sorted(by_year, reverse=True):
        year_records = by_year[year]
        previous_year_end = december_by_year.get(year - 1)
        baseline = (
            previous_year_end.nav_per_share
            if previous_year_end
            else year_records[0].nav_per_share
            if year_records
            else None
        )
        fallback_used = bool(year_records and previous_year_end is None)
        rows: list[DashboardMonth] = []
        prior_record = previous_year_end
        for index, record in enumerate(year_records):
            monthly_return = (
                record.nav_per_share / prior_record.nav_per_share - Decimal(1)
                if prior_record
                and _months_are_consecutive(
                    prior_record.valuation_month,
                    record.valuation_month,
                )
                else None
            )
            cumulative_return = (
                record.nav_per_share / baseline - Decimal(1)
                if baseline is not None and not (fallback_used and index == 0)
                else None
            )
            rows.append(
                DashboardMonth(
                    month=record.valuation_month.month,
                    record=record,
                    nav_display=_format_nav(record.nav_per_share),
                    monthly_return=monthly_return,
                    monthly_return_display=_format_percent(monthly_return),
                    monthly_return_class=_return_class(monthly_return),
                    cumulative_return=cumulative_return,
                    cumulative_return_display=_format_percent(cumulative_return),
                    cumulative_return_class=_return_class(cumulative_return),
                )
            )
            prior_record = record

        if next_period and next_period.year == year:
            rows.append(
                DashboardMonth(
                    month=next_period.month,
                    record=None,
                    nav_display="—",
                    monthly_return=None,
                    monthly_return_display="—",
                    monthly_return_class="nav-return-neutral",
                    cumulative_return=None,
                    cumulative_return_display="—",
                    cumulative_return_class="nav-return-neutral",
                    is_next=True,
                )
            )
            rows.sort(key=lambda row: row.month)

        if year_records:
            latest = year_records[-1]
            highest = max(year_records, key=lambda item: item.nav_per_share)
            lowest = min(year_records, key=lambda item: item.nav_per_share)
            period_return = latest.nav_per_share / baseline - Decimal(1) if baseline else None
            if latest.valuation_month.month == 12:
                return_label = "全年度回報（FY）"
            elif year == default_period.year:
                return_label = "年初至今回報（YTD）"
            else:
                return_label = "期間回報"
            baseline_note = (
                f"以 {year - 1} 年 12 月 NAV 為基準"
                if previous_year_end
                else f"無上一年度末 NAV；以 {year} 年首筆 NAV 為基準"
            )
            latest_nav_display = _format_nav(latest.nav_per_share)
            latest_month_label = (
                f"{latest.valuation_month.year} 年 {latest.valuation_month.month} 月"
            )
            high_nav_display = _format_nav(highest.nav_per_share)
            high_month_label = (
                f"{highest.valuation_month.year} 年 {highest.valuation_month.month} 月"
            )
            low_nav_display = _format_nav(lowest.nav_per_share)
            low_month_label = f"{lowest.valuation_month.year} 年 {lowest.valuation_month.month} 月"
        else:
            period_return = None
            return_label = "年初至今回報（YTD）"
            baseline_note = "輸入首筆 NAV 後顯示回報"
            latest_nav_display = "—"
            latest_month_label = "尚未輸入"
            high_nav_display = "—"
            high_month_label = "尚未輸入"
            low_nav_display = "—"
            low_month_label = "尚未輸入"

        dashboard_years.append(
            DashboardYear(
                year=year,
                months=tuple(rows),
                latest_nav_display=latest_nav_display,
                latest_month_label=latest_month_label,
                return_label=return_label,
                period_return=period_return,
                period_return_display=_format_percent(period_return),
                period_return_class=_return_class(period_return),
                baseline_note=baseline_note,
                high_nav_display=high_nav_display,
                high_month_label=high_month_label,
                low_nav_display=low_nav_display,
                low_month_label=low_month_label,
                has_records=bool(year_records),
                is_current_input_year=bool(next_period and next_period.year == year),
            )
        )
    return dashboard_years


def generate_nav_year_chart(records: Iterable[NAVRecord], *, mobile: bool = False) -> bytes:
    ordered = sorted(records, key=lambda item: item.valuation_month)
    if not ordered:
        raise ValueError("At least one NAV record is required.")

    x_values = list(range(len(ordered)))
    y_values = [float(item.nav_per_share) for item in ordered]
    labels = [str(item.valuation_month.month) for item in ordered]
    fig, axis = plt.subplots(figsize=(5.2, 4.3) if mobile else (9.4, 3.4), dpi=160)
    try:
        fig.patch.set_facecolor("white")
        axis.set_facecolor("white")
        axis.plot(
            x_values,
            y_values,
            color="#1769D2",
            linewidth=2.2,
            marker="o",
            markersize=5,
            markerfacecolor="white",
            markeredgewidth=1.8,
        )
        if len(ordered) > 1:
            axis.fill_between(x_values, y_values, min(y_values), color="#1769D2", alpha=0.07)
        for index, (x_value, record, y_value) in enumerate(
            zip(x_values, ordered, y_values, strict=True)
        ):
            axis.annotate(
                _format_nav(record.nav_per_share, 3),
                (x_value, y_value),
                xytext=(0, 8 if not mobile or index % 2 == 0 else 22),
                textcoords="offset points",
                ha="left" if mobile else "center",
                va="bottom",
                fontsize=6.5 if mobile else 7,
                color="#42536A",
                rotation=45 if mobile else 0,
            )
        axis.set_xticks(x_values, labels)
        axis.set_xlabel("Month", color="#64748B", fontsize=8)
        axis.set_ylabel("NAV per Share", color="#64748B", fontsize=8)
        axis.tick_params(axis="both", colors="#64748B", labelsize=8, length=0)
        axis.grid(axis="y", color="#E5EBF2", linewidth=0.7)
        axis.grid(axis="x", visible=False)
        axis.spines[["top", "right", "left"]].set_visible(False)
        axis.spines["bottom"].set_color("#DCE4EE")
        axis.margins(x=0.06 if mobile else 0.04, y=0.28 if mobile else 0.22)
        fig.tight_layout(pad=0.7)
        output = BytesIO()
        fig.savefig(output, format="png", bbox_inches="tight", facecolor="white")
        return output.getvalue()
    finally:
        plt.close(fig)
