from datetime import date
from decimal import Decimal

import pytest

from navapp.services.calculations import (
    CalculationValidationError,
    NavPoint,
    calculate_performance,
    format_percent,
    maximum_drawdown,
    monthly_returns,
    round_for_display,
)


def assert_close(actual: str | None, expected: str, tolerance: str = "0.0000000001") -> None:
    assert actual is not None
    assert abs(Decimal(actual) - Decimal(expected)) <= Decimal(tolerance)


def test_xsq_2026_q1_regression(xsq_points):
    result = calculate_performance(
        points=xsq_points,
        inception_nav=Decimal("100"),
        inception_date=date(2022, 7, 7),
        report_end=date(2026, 3, 31),
        annual_rfr_decimal=Decimal("0.04190858333333334"),
    )
    raw = result["metrics_raw"]
    display = result["metrics_display"]

    assert_close(raw["latest_quarter_return"], "-0.162368981826")
    assert_close(raw["ytd_return"], "-0.162368981826")
    assert_close(raw["itd_return"], "-0.227209948356")
    assert_close(raw["annualized_return"], "-0.066423869173")
    assert_close(raw["positive_months"], "0.377777777778")
    assert_close(raw["negative_months"], "0.622222222222")
    assert_close(raw["annualized_volatility"], "0.539204281708")
    assert_close(raw["trailing_12_month_volatility"], "0.780396076888")
    assert_close(raw["sharpe_ratio"], "-0.200911706717")
    assert_close(raw["maximum_drawdown"], "-0.574353049798", "0.000000001")

    assert display["latest_quarter_return"] == "-16.24%"
    assert display["ytd_return"] == "-16.24%"
    assert display["itd_return"] == "-22.72%"
    assert display["annualized_return"] == "-6.64%"
    assert display["positive_months"] == "38%"
    assert display["negative_months"] == "62%"
    assert display["annualized_volatility"] == "53.92%"
    assert display["sharpe_ratio"] == "-0.201"


def test_first_monthly_return_uses_inception_nav():
    point = NavPoint(date(2024, 1, 31), date(2024, 1, 31), Decimal("110"))
    assert monthly_returns([point], Decimal("100")) == [Decimal("0.1")]


def test_quarterly_matrix_first_partial_quarter_and_ytd():
    points = [
        NavPoint(date(2024, 2, 29), date(2024, 2, 29), Decimal("102")),
        NavPoint(date(2024, 3, 31), date(2024, 3, 31), Decimal("105")),
    ]
    result = calculate_performance(
        points=points,
        inception_nav=Decimal("100"),
        inception_date=date(2024, 2, 1),
        report_end=date(2024, 3, 31),
    )
    assert result["quarterly_matrix"]["2024"]["q1"]["raw"] == "0.05"
    assert result["quarterly_matrix"]["2024"]["ytd"]["raw"] == "0.05"


def test_monthly_report_uses_month_end_and_exposes_latest_month_return():
    points = [
        NavPoint(date(2024, 1, 31), date(2024, 1, 31), Decimal("101")),
        NavPoint(date(2024, 2, 29), date(2024, 2, 29), Decimal("103")),
    ]

    result = calculate_performance(
        points=points,
        inception_nav=Decimal("100"),
        inception_date=date(2024, 1, 1),
        report_end=date(2024, 2, 29),
        report_type="MONTHLY",
    )

    assert result["report_type"] == "MONTHLY"
    assert result["monthly"][-1]["nav"] == "103"
    assert result["monthly"][-1]["nav_display"] == "103.00"
    assert result["metrics_raw"]["latest_period_return"] == str(
        Decimal("103") / Decimal("101") - Decimal(1)
    )
    assert result["details"]["latest_period_return"]["formula"] == "NAV[t] / NAV[t-1] - 1"


def test_itd_does_not_assume_inception_nav_is_100():
    points = [
        NavPoint(date(2024, 1, 31), date(2024, 1, 31), Decimal("52")),
        NavPoint(date(2024, 2, 29), date(2024, 2, 29), Decimal("54")),
        NavPoint(date(2024, 3, 31), date(2024, 3, 31), Decimal("55")),
    ]
    result = calculate_performance(
        points=points,
        inception_nav=Decimal("50"),
        inception_date=date(2024, 1, 5),
        report_end=date(2024, 3, 31),
    )
    assert result["metrics_raw"]["itd_return"] == "0.1"


def test_zero_month_percentage_and_max_gain_loss():
    points = [
        NavPoint(date(2024, 1, 31), date(2024, 1, 31), Decimal("100")),
        NavPoint(date(2024, 2, 29), date(2024, 2, 29), Decimal("110")),
        NavPoint(date(2024, 3, 31), date(2024, 3, 31), Decimal("99")),
    ]
    result = calculate_performance(
        points=points,
        inception_nav=Decimal("100"),
        inception_date=date(2024, 1, 1),
        report_end=date(2024, 3, 31),
    )
    raw = result["metrics_raw"]
    assert Decimal(raw["zero_months"]) == Decimal(1) / Decimal(3)
    assert Decimal(raw["maximum_monthly_gain"]) == Decimal("0.1")
    assert Decimal(raw["maximum_monthly_loss"]) == Decimal("-0.1")


def test_trailing_volatility_is_na_with_fewer_than_twelve_returns():
    points = [
        NavPoint(date(2024, 1, 31), date(2024, 1, 31), Decimal("101")),
        NavPoint(date(2024, 2, 29), date(2024, 2, 29), Decimal("102")),
        NavPoint(date(2024, 3, 31), date(2024, 3, 31), Decimal("103")),
    ]
    result = calculate_performance(
        points=points,
        inception_nav=Decimal("100"),
        inception_date=date(2024, 1, 1),
        report_end=date(2024, 3, 31),
    )
    assert result["metrics_raw"]["trailing_12_month_volatility"] is None
    assert result["metrics_display"]["trailing_12_month_volatility"] == "N/A"


def test_dynamic_drawdown_uses_running_peak():
    points = [
        NavPoint(date(2024, 1, 31), date(2024, 1, 31), Decimal("120")),
        NavPoint(date(2024, 2, 29), date(2024, 2, 29), Decimal("60")),
    ]
    assert maximum_drawdown(points, Decimal("100")) == Decimal("-0.5")


@pytest.mark.parametrize(
    "points,expected",
    [
        (
            [
                NavPoint(date(2024, 1, 31), date(2024, 1, 31), Decimal("101")),
                NavPoint(date(2024, 3, 31), date(2024, 3, 31), Decimal("102")),
            ],
            "缺少 NAV 月份 2024-02",
        ),
        (
            [
                NavPoint(date(2024, 1, 31), date(2024, 1, 31), Decimal("101")),
                NavPoint(date(2024, 1, 31), date(2024, 1, 31), Decimal("102")),
                NavPoint(date(2024, 3, 31), date(2024, 3, 31), Decimal("103")),
            ],
            "NAV 月份重複",
        ),
        (
            [
                NavPoint(date(2024, 1, 31), date(2024, 1, 31), Decimal("101")),
                NavPoint(date(2024, 2, 29), date(2024, 2, 29), Decimal("0")),
                NavPoint(date(2024, 3, 31), date(2024, 3, 31), Decimal("102")),
            ],
            "必須大於零",
        ),
    ],
)
def test_invalid_nav_sequences_block_calculation(points, expected):
    with pytest.raises(CalculationValidationError, match=expected):
        calculate_performance(
            points=points,
            inception_nav=Decimal("100"),
            inception_date=date(2024, 1, 1),
            report_end=date(2024, 3, 31),
        )


def test_missing_quarter_end_blocks_calculation():
    points = [
        NavPoint(date(2024, 1, 31), date(2024, 1, 31), Decimal("101")),
        NavPoint(date(2024, 2, 29), date(2024, 2, 29), Decimal("102")),
    ]
    with pytest.raises(CalculationValidationError, match="季末 NAV"):
        calculate_performance(
            points=points,
            inception_nav=Decimal("100"),
            inception_date=date(2024, 1, 1),
            report_end=date(2024, 3, 31),
        )


def test_presentation_rounding_is_half_up():
    assert round_for_display(Decimal("1.005"), 2) == Decimal("1.01")
    assert format_percent(Decimal("-0.162368981826"), 2) == "-16.24%"
