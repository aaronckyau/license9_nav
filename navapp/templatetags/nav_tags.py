from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from django import template

register = template.Library()


@register.filter
def get_item(mapping, key):
    return mapping.get(key) if mapping else None


@register.filter
def nav_display(value, places=6):
    if value in {None, ""}:
        return "—"
    try:
        places = int(places)
        rounded = Decimal(str(value)).quantize(Decimal(1).scaleb(-places), rounding=ROUND_HALF_UP)
    except (InvalidOperation, TypeError, ValueError):
        return value
    return f"{rounded:.{places}f}"


@register.filter
def metric_label(value):
    labels = {
        "latest_quarter_return": "Latest Quarter Return",
        "ytd_return": "YTD Return",
        "itd_return": "ITD Return",
        "annualized_return": "Annualized Return",
        "annualized_volatility": "Annualized Volatility",
        "trailing_12_month_volatility": "Trailing 12-Month Volatility",
        "positive_months": "Positive Months",
        "negative_months": "Negative Months",
        "zero_months": "Zero Months",
        "maximum_monthly_gain": "Maximum Monthly Gain",
        "maximum_monthly_loss": "Maximum Monthly Loss",
        "maximum_drawdown": "Maximum Drawdown",
        "annual_rfr": "Annual RFR",
        "sharpe_ratio": "Sharpe Ratio",
        "day_based_cagr": "Day-Based CAGR",
    }
    key = str(value)
    return labels.get(key, key.replace("_", " ").title())
