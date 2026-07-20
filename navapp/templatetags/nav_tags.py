from datetime import date
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from django import template

register = template.Library()


@register.filter
def zh_date(value):
    if value in {None, ""}:
        return "—"
    try:
        parsed = value if isinstance(value, date) else date.fromisoformat(str(value))
    except (TypeError, ValueError):
        return value
    return f"{parsed.year} 年 {parsed.month} 月 {parsed.day} 日"


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
        "latest_quarter_return": "最新季度回報",
        "ytd_return": "年初至今回報",
        "itd_return": "成立至今回報",
        "annualized_return": "年化回報",
        "annualized_volatility": "年化波幅",
        "trailing_12_month_volatility": "過去 12 個月波幅",
        "positive_months": "正回報月份",
        "negative_months": "負回報月份",
        "zero_months": "零回報月份",
        "maximum_monthly_gain": "最大單月升幅",
        "maximum_monthly_loss": "最大單月跌幅",
        "maximum_drawdown": "最大回撤",
        "annual_rfr": "年度無風險利率",
        "sharpe_ratio": "夏普比率",
        "day_based_cagr": "按日計算複合年增長率",
    }
    key = str(value)
    return labels.get(key, key)


@register.filter
def choice_label(value):
    labels = {
        "NET": "扣除費用後",
        "GROSS": "扣除費用前",
        "OFFICIAL": "正式",
        "INDICATIVE": "參考",
        "DRAFT": "草稿",
        "READY": "可供定稿",
        "FINAL": "已定稿",
        "STALE": "資料已變更，需重新產生",
        "GENERATION_FAILED": "產生失敗",
        "COMMENTARY_REQUIRED": "需要填寫評論",
        "DOCX": "Word 文件",
        "PDF": "PDF 文件",
        "Fund": "基金",
        "ShareClass": "股份類別",
        "NAVRecord": "NAV 紀錄",
        "QuarterlyReport": "季度報告",
        "OrganizationSettings": "機構設定",
        "CREATE": "建立",
        "UPDATE": "更新",
        "GENERATE": "產生報告",
        "GENERATE_DOCX": "產生 Word 報告",
        "FINALIZE": "定稿",
        "BULK_NAV_IMPORT": "批次匯入 NAV",
        "MANUAL_RFR_OVERRIDE": "手動覆寫無風險利率",
        "SIMPLE_ENTRY": "三步流程輸入",
        "MARK_REPORTS_STALE": "標示報告需重新產生",
        "NAV Quarterly Reporting": "NAV 季度報告系統",
    }
    return labels.get(str(value), value)


@register.filter
def zh_text(value):
    text = str(value or "")
    exact = {
        "Manager Commentary is required.": "必須填寫基金經理評論。",
        "Report end must be a calendar quarter end.": "報告截止日必須為日曆季度末日。",
        "Quarter-end NAV / previous quarter-end NAV - 1": "季度末 NAV ÷ 上一季度末 NAV − 1",
        "Latest NAV / previous year-end NAV - 1": "最新 NAV ÷ 上一年度末 NAV − 1",
        "Latest NAV / inception NAV - 1": "最新 NAV ÷ 成立時 NAV − 1",
        "PRODUCT(1 + monthly returns)^(12 / N) - 1": "連乘（1 + 每月回報）^(12 ÷ N) − 1",
        "STDEV.S(monthly returns) * SQRT(12)": "每月回報樣本標準差 × √12",
        "STDEV.S(latest 12 monthly returns) * SQRT(12)": "最近 12 個月回報樣本標準差 × √12",
        "MIN(NAV / dynamic running peak - 1)": "最小值（NAV ÷ 動態歷史高位 − 1）",
        "(annualized return - annual RFR) / annualized volatility since inception": "（年化回報 − 年化無風險利率）÷ 成立以來年化波動率",
        "Intentional correction from the workbook fixed-cell result.": "此結果已刻意修正工作簿固定儲存格算法。",
        "Legacy workbook method; this is not a monthly excess-return Sharpe ratio.": "沿用舊版工作簿算法；此數值並非按月超額回報計算的夏普比率。",
        "LibreOffice executable 'soffice' was not found.": "找不到 LibreOffice 執行檔 'soffice'。",
        "RFR snapshot is required.": "必須建立無風險利率快照。",
        "Exactly 12 RFR observations are required.": "必須有正好 12 筆無風險利率觀察值。",
        "Generated DOCX and PDF files are required.": "必須先產生 DOCX 及 PDF 檔案。",
        "Report snapshot is required.": "必須建立報告快照。",
        "RFR observations extend beyond the report end.": "無風險利率觀察日期不得超過報告截止日。",
        "No NAV records are available through the report date.": "報告截止日前沒有可用的 NAV 紀錄。",
    }
    if text in exact:
        return exact[text]
    prefixes = {
        "Missing valuation months:": "缺少估值月份：",
        "Generation failed:": "產生報告失敗：",
        "Finalization blocked:": "無法定稿：",
        "Fund settings changed:": "基金設定已變更：",
        "Share-class settings changed:": "股份類別設定已變更：",
        "Organization settings changed:": "機構設定已變更：",
    }
    for source, translated in prefixes.items():
        if text.startswith(source):
            return translated + text[len(source) :]
    return text
