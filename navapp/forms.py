from __future__ import annotations

import re
from datetime import date, timedelta
from decimal import Decimal
from zipfile import BadZipFile, ZipFile

from django import forms
from django.conf import settings
from django.contrib.auth.forms import AuthenticationForm, PasswordChangeForm
from django.forms import inlineformset_factory
from django.utils import timezone

from navapp.models import (
    Contact,
    Fund,
    FundParty,
    FundStrategyHighlight,
    FundTerm,
    NAVRecord,
    OrganizationSettings,
    QuarterlyReport,
    ShareClass,
    month_end,
)
from navapp.services.reports import REQUIRED_CUSTOM_PLACEHOLDERS

CHOICE_LABELS_ZH = {
    "FRED_DGS10": "FRED DGS10（美國聯邦儲備經濟數據）",
    "TREASURY_CMT10": "美國財政部 10 年期固定到期利率",
    "MANUAL": "手動覆寫",
    "PORTFOLIO_MANAGER": "投資組合經理",
    "GENERAL_PARTNER": "普通合夥人",
    "INVESTMENT_MANAGER": "投資經理",
    "ADMINISTRATOR": "基金行政管理人",
    "AUDITOR": "核數師",
    "LEGAL_ADVISER": "法律顧問",
    "CUSTODIAN": "託管人／主經紀商",
    "OTHER": "其他",
    "NET": "扣除費用後",
    "GROSS": "扣除費用前",
    "OFFICIAL": "正式",
    "INDICATIVE": "參考",
}


def translate_choices(field) -> None:
    field.choices = [
        (value, CHOICE_LABELS_ZH.get(str(value), label)) for value, label in field.choices
    ]


class DateInput(forms.DateInput):
    input_type = "date"


class ChineseAuthenticationForm(AuthenticationForm):
    username = forms.CharField(label="使用者名稱")
    password = forms.CharField(label="密碼", strip=False, widget=forms.PasswordInput)
    error_messages = {
        "invalid_login": "使用者名稱或密碼不正確，請重新輸入。",
        "inactive": "此帳戶已停用。",
    }


class ChinesePasswordChangeForm(PasswordChangeForm):
    old_password = forms.CharField(
        label="目前密碼",
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "current-password"}),
    )
    new_password1 = forms.CharField(
        label="新密碼",
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
    )
    new_password2 = forms.CharField(
        label="確認新密碼",
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
    )
    error_messages = {
        **PasswordChangeForm.error_messages,
        "password_incorrect": "目前密碼不正確，請重新輸入。",
        "password_mismatch": "兩次輸入的新密碼不一致。",
    }


class OrganizationSettingsForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        translate_choices(self.fields["rfr_provider"])

    class Meta:
        model = OrganizationSettings
        exclude = ()
        labels = {
            "display_name": "系統顯示名稱",
            "default_logo": "預設標誌",
            "primary_brand_colour": "主要品牌顏色",
            "professional_investor_statement": "專業投資者聲明",
            "report_date_statement_template": "報告日期聲明範本",
            "default_disclaimer": "預設免責聲明",
            "disclaimer_version": "免責聲明版本",
            "disclaimer_effective_date": "免責聲明生效日期",
            "default_contact_information": "預設聯絡資料",
            "percentage_decimal_places": "百分比小數位數",
            "sharpe_decimal_places": "夏普比率小數位數",
            "report_language": "報告語言",
            "rfr_provider": "無風險利率資料來源",
            "rfr_series": "無風險利率數據系列",
            "nav_change_warning_threshold": "NAV 變動警告門檻",
        }
        widgets = {
            "disclaimer_effective_date": DateInput(),
            "default_disclaimer": forms.Textarea(attrs={"rows": 8}),
            "default_contact_information": forms.Textarea(attrs={"rows": 4}),
        }


class FundForm(forms.ModelForm):
    class Meta:
        model = Fund
        exclude = ("created_at", "updated_at")
        labels = {
            "legal_name": "法定名稱",
            "display_name": "顯示名稱",
            "short_code": "基金代碼",
            "structure": "法律架構",
            "domicile": "註冊地",
            "year_end_month": "財政年度結束月份",
            "year_end_day": "財政年度結束日期",
            "report_language": "報告語言",
            "is_active": "啟用基金",
            "investment_objective": "投資目標",
            "performance_note": "績效附註",
            "use_org_professional_statement": "使用機構的專業投資者聲明",
            "professional_investor_statement_override": "基金專業投資者聲明",
            "use_org_date_statement": "使用機構的報告日期聲明",
            "date_statement_override": "基金報告日期聲明",
            "use_org_disclaimer": "使用機構的免責聲明",
            "disclaimer_override": "基金免責聲明",
            "disclaimer_version_override": "基金免責聲明版本",
            "disclaimer_effective_date_override": "基金免責聲明生效日期",
            "logo_override": "基金標誌",
            "brand_colour_override": "基金品牌顏色",
            "header_text_override": "報告頁首文字",
            "custom_docx_template": "自訂 DOCX 範本",
        }
        widgets = {
            "investment_objective": forms.Textarea(attrs={"rows": 5}),
            "performance_note": forms.Textarea(attrs={"rows": 3}),
            "disclaimer_override": forms.Textarea(attrs={"rows": 7}),
            "disclaimer_effective_date_override": DateInput(),
        }

    def clean_custom_docx_template(self):
        uploaded = self.cleaned_data.get("custom_docx_template")
        if not uploaded or not hasattr(uploaded, "read"):
            return uploaded
        if not uploaded.name.lower().endswith(".docx"):
            raise forms.ValidationError("自訂報告範本必須是 .docx 檔案。")
        if uploaded.size > settings.MAX_UPLOAD_BYTES:
            raise forms.ValidationError("自訂報告範本超過上載大小限制。")
        content_type = getattr(uploaded, "content_type", "")
        if content_type and content_type not in {
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "application/octet-stream",
        }:
            raise forms.ValidationError("自訂報告範本的 MIME 類型無效。")
        try:
            uploaded.seek(0)
            with ZipFile(uploaded) as archive:
                members = archive.infolist()
                if sum(member.file_size for member in members) > settings.MAX_UPLOAD_BYTES * 10:
                    raise forms.ValidationError("解壓後的自訂範本超過安全大小限制。")
                required_members = {"[Content_Types].xml", "word/document.xml"}
                if not required_members.issubset(member.filename for member in members):
                    raise forms.ValidationError("自訂報告範本缺少必要的 DOCX 元件。")
                package_text = "".join(
                    archive.read(name).decode("utf-8", errors="ignore")
                    for name in archive.namelist()
                    if name.endswith((".xml", ".rels"))
                )
        except (BadZipFile, KeyError, OSError, RuntimeError) as exc:
            raise forms.ValidationError("自訂報告範本不是有效的 DOCX 封裝。") from exc
        finally:
            uploaded.seek(0)
        missing = [name for name in REQUIRED_CUSTOM_PLACEHOLDERS if name not in package_text]
        if missing:
            raise forms.ValidationError("缺少必要的預留位置：" + ", ".join(sorted(missing)))
        lower = package_text.lower()
        if 'targetmode="external"' in lower and (".xlsx" in lower or "oleobject" in lower):
            raise forms.ValidationError("不允許外部 Excel 關聯。")
        return uploaded


StrategyFormSet = inlineformset_factory(
    Fund,
    FundStrategyHighlight,
    fields=("text", "sort_order"),
    labels={"text": "策略重點", "sort_order": "顯示次序"},
    extra=1,
    can_delete=True,
    min_num=1,
    validate_min=True,
)
PartyFormSet = inlineformset_factory(
    Fund,
    FundParty,
    fields=("party_type", "display_label", "value", "sort_order"),
    labels={
        "party_type": "機構類型",
        "display_label": "顯示標籤",
        "value": "名稱／內容",
        "sort_order": "顯示次序",
    },
    extra=1,
    can_delete=True,
)
TermFormSet = inlineformset_factory(
    Fund,
    FundTerm,
    fields=("key", "display_label", "value_text", "display_in_report", "sort_order"),
    labels={
        "key": "識別鍵",
        "display_label": "顯示標籤",
        "value_text": "內容",
        "display_in_report": "顯示於報告",
        "sort_order": "顯示次序",
    },
    extra=1,
    can_delete=True,
)
ContactFormSet = inlineformset_factory(
    Fund,
    Contact,
    fields=("role", "name", "email", "phone", "address", "display_in_report", "sort_order"),
    labels={
        "role": "角色",
        "name": "姓名／機構名稱",
        "email": "電郵",
        "phone": "電話",
        "address": "地址",
        "display_in_report": "顯示於報告",
        "sort_order": "顯示次序",
    },
    extra=1,
    can_delete=True,
)

translate_choices(PartyFormSet.form.base_fields["party_type"])


class ShareClassForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        translate_choices(self.fields["return_basis"])

    class Meta:
        model = ShareClass
        exclude = ("fund", "created_at", "updated_at")
        labels = {
            "name": "股份類別名稱",
            "code": "股份類別代碼",
            "inception_date": "成立日期",
            "inception_nav": "成立時 NAV",
            "currency": "貨幣",
            "return_basis": "回報基準",
            "management_fee_override": "管理費覆寫",
            "performance_fee_override": "績效費覆寫",
            "bloomberg_code_override": "Bloomberg 代碼覆寫",
            "is_active": "啟用股份類別",
            "display_in_quarterly_report": "顯示於季度報告",
        }
        widgets = {"inception_date": DateInput()}


class NAVRecordForm(forms.ModelForm):
    acknowledge_large_change = forms.BooleanField(
        label="確認異常 NAV 變動",
        required=False,
        help_text="當相對上月的變動超過設定門檻時必須確認。",
    )

    class Meta:
        model = NAVRecord
        fields = (
            "valuation_month",
            "valuation_date",
            "nav_per_share",
            "status",
            "note",
            "acknowledge_large_change",
        )
        labels = {
            "valuation_month": "估值月份",
            "valuation_date": "估值日期",
            "nav_per_share": "每股 NAV",
            "status": "狀態",
            "note": "備註",
        }
        widgets = {"valuation_month": DateInput(), "valuation_date": DateInput()}

    def __init__(self, *args, share_class: ShareClass | None = None, **kwargs):
        super().__init__(*args, **kwargs)
        self.share_class = share_class or getattr(self.instance, "share_class", None)
        translate_choices(self.fields["status"])

    def clean_valuation_month(self):
        value = self.cleaned_data["valuation_month"]
        return month_end(value)

    def clean(self):
        cleaned = super().clean()
        if (
            not self.share_class
            or not cleaned.get("valuation_month")
            or not cleaned.get("nav_per_share")
        ):
            return cleaned
        prior = (
            self.share_class.nav_records.filter(
                is_active=True,
                valuation_month__lt=cleaned["valuation_month"],
            )
            .exclude(pk=self.instance.pk)
            .order_by("-valuation_month")
            .first()
        )
        if prior:
            change = cleaned["nav_per_share"] / prior.nav_per_share - Decimal(1)
            threshold = OrganizationSettings.load().nav_change_warning_threshold
            if abs(change) > threshold and not cleaned.get("acknowledge_large_change"):
                self.add_error(
                    "acknowledge_large_change",
                    f"NAV 相對 {prior.valuation_month:%Y-%m} 變動 {change * 100:.2f}%。"
                    "請先檢查並確認，才可儲存。",
                )
        return cleaned

    def save(self, commit=True):
        item = super().save(commit=False)
        item.share_class = self.share_class
        item.change_acknowledged = bool(self.cleaned_data.get("acknowledge_large_change"))
        if commit:
            item.save()
        return item


class NAVEditReasonForm(forms.Form):
    reason = forms.CharField(label="修改原因", widget=forms.Textarea(attrs={"rows": 3}))


class BulkImportForm(forms.Form):
    file = forms.FileField(label="匯入檔案", help_text="支援 CSV 或 XLSX；上限 10 MB。")

    def clean_file(self):
        uploaded = self.cleaned_data["file"]
        if uploaded.size > settings.MAX_UPLOAD_BYTES:
            raise forms.ValidationError("上載檔案超過設定的大小限制。")
        suffix = uploaded.name.rsplit(".", 1)[-1].lower()
        if suffix not in {"csv", "xlsx"}:
            raise forms.ValidationError("只支援 CSV 及 XLSX 檔案。")
        expected_types = {
            "csv": {"text/csv", "application/csv", "text/plain", "application/octet-stream"},
            "xlsx": {
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                "application/octet-stream",
            },
        }
        content_type = getattr(uploaded, "content_type", "")
        if content_type and content_type not in expected_types[suffix]:
            raise forms.ValidationError("上載檔案的 MIME 類型與副檔名不符。")
        return uploaded


class ReportCreateForm(forms.Form):
    share_class = forms.ModelChoiceField(
        label="股份類別",
        queryset=ShareClass.objects.none(),
    )
    report_type = forms.ChoiceField(
        label="報告類型",
        choices=(
            (QuarterlyReport.ReportType.MONTHLY, "月報"),
            (QuarterlyReport.ReportType.QUARTERLY, "季報"),
        ),
    )
    year = forms.IntegerField(label="報告年度", min_value=1900, max_value=9999)
    month = forms.TypedChoiceField(
        label="截止月份",
        choices=((month, f"{month} 月") for month in range(1, 13)),
        coerce=int,
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["share_class"].queryset = ShareClass.objects.filter(
            is_active=True,
            fund__is_active=True,
        ).select_related("fund")
        completed = latest_completed_month()
        self.fields["year"].initial = completed.year
        self.fields["month"].initial = completed.month

    def clean(self):
        cleaned = super().clean()
        year = cleaned.get("year")
        month = cleaned.get("month")
        report_type = cleaned.get("report_type")
        share_class = cleaned.get("share_class")
        if year and month:
            report_date = month_end(date(year, month, 1))
            cleaned["report_date"] = report_date
            cleaned["quarter"] = (month - 1) // 3 + 1
            if report_date > latest_completed_month():
                self.add_error("month", "不可選擇尚未完成的月份。")
            if share_class and report_date < month_end(share_class.inception_date):
                self.add_error("month", "報告月份不可早於股份類別成立月份。")
            if report_type == QuarterlyReport.ReportType.QUARTERLY and month not in {
                3,
                6,
                9,
                12,
            }:
                self.add_error("month", "季報截止月份必須是 3、6、9 或 12 月。")
        return cleaned


class CommentaryForm(forms.ModelForm):
    class Meta:
        model = QuarterlyReport
        fields = (
            "commentary_title",
            "commentary_markdown",
            "commentary_author",
            "commentary_date",
        )
        labels = {
            "commentary_title": "評論標題",
            "commentary_markdown": "評論內容",
            "commentary_author": "作者",
            "commentary_date": "評論日期",
        }
        widgets = {
            "commentary_markdown": forms.Textarea(attrs={"rows": 14}),
            "commentary_date": DateInput(),
        }

    def clean_commentary_markdown(self):
        return validate_commentary_markdown(self.cleaned_data["commentary_markdown"])


def validate_commentary_markdown(value: str) -> str:
    value = value.strip()
    if re.search(r"<\s*/?\s*[a-zA-Z][^>]*>", value):
        raise forms.ValidationError("不支援原始 HTML，請使用安全的 Markdown 語法。")
    if not value:
        raise forms.ValidationError("必須填寫基金經理評論。")
    return value


class ReportHistoryCommentaryForm(forms.ModelForm):
    class Meta:
        model = QuarterlyReport
        fields = ("commentary_markdown",)
        labels = {"commentary_markdown": "基金經理評論"}
        widgets = {
            "commentary_markdown": forms.Textarea(
                attrs={
                    "rows": 6,
                    "placeholder": "輸入所選報告期間的基金經理評論……",
                }
            )
        }

    def clean_commentary_markdown(self):
        return validate_commentary_markdown(self.cleaned_data["commentary_markdown"])


def next_missing_nav_month(share_class: ShareClass, today: date | None = None) -> date | None:
    completed_month = latest_completed_month(today)
    candidate = month_end(share_class.inception_date)
    existing = set(
        share_class.nav_records.filter(
            is_active=True,
            valuation_month__lte=completed_month,
        ).values_list("valuation_month", flat=True)
    )
    while candidate <= completed_month:
        if candidate not in existing:
            return candidate
        candidate = month_end(candidate + timedelta(days=1))
    return None


def latest_completed_month(today: date | None = None) -> date:
    today = today or timezone.localdate()
    if today == month_end(today):
        return today
    return date(today.year, today.month, 1) - timedelta(days=1)


def _large_nav_change_warning(
    *,
    share_class: ShareClass,
    valuation_month: date,
    nav_value: Decimal,
    confirmed: bool,
) -> str:
    if confirmed:
        return ""
    prior = (
        share_class.nav_records.filter(
            is_active=True,
            valuation_month__lt=valuation_month,
        )
        .order_by("-valuation_month")
        .first()
    )
    if not prior:
        return ""
    change = nav_value / prior.nav_per_share - Decimal(1)
    threshold = OrganizationSettings.load().nav_change_warning_threshold
    if abs(change) <= threshold:
        return ""
    return (
        f"NAV 相對 {prior.valuation_month:%Y 年 %m 月} 變動 {change * 100:.2f}%。"
        "請檢查數值；如確認正確，再按一次儲存。"
    )


class SimpleEntryForm(forms.Form):
    valuation_month = forms.DateField(widget=forms.HiddenInput)
    nav_per_share = forms.DecimalField(
        label="每股 NAV",
        max_digits=38,
        decimal_places=2,
        min_value=Decimal("0.01"),
        help_text="請輸入該月份正式的每股 NAV（小數點後最多兩位）。",
        widget=forms.NumberInput(attrs={"step": "0.01", "inputmode": "decimal"}),
    )
    confirm_large_change = forms.BooleanField(required=False, widget=forms.HiddenInput)

    def __init__(self, *args, share_class: ShareClass, **kwargs):
        self.share_class = share_class
        self.system_date = timezone.localdate()
        self.default_period = latest_completed_month(self.system_date)
        self.next_period = next_missing_nav_month(self.share_class, self.system_date)
        self.large_change_warning = ""
        kwargs.setdefault("initial", {"valuation_month": self.next_period})
        super().__init__(*args, **kwargs)

    def clean(self):
        cleaned = super().clean()
        valuation_month = cleaned.get("valuation_month")
        nav_value = cleaned.get("nav_per_share")
        if not valuation_month:
            return cleaned
        valuation_month = month_end(valuation_month)
        cleaned["valuation_month"] = valuation_month
        if valuation_month > self.default_period:
            self.add_error("valuation_month", "估值月份不得晚於最近已完成月份。")
            return cleaned
        if valuation_month < month_end(self.share_class.inception_date):
            self.add_error("valuation_month", "估值月份不得早於股份類別成立月份。")
            return cleaned
        if self.share_class.nav_records.filter(
            valuation_month=valuation_month, is_active=True
        ).exists():
            self.add_error("valuation_month", "該月份已有 NAV 紀錄，為避免重複不會覆蓋原有資料。")
            return cleaned
        if nav_value is None:
            return cleaned
        self.large_change_warning = _large_nav_change_warning(
            share_class=self.share_class,
            valuation_month=valuation_month,
            nav_value=nav_value,
            confirmed=bool(cleaned.get("confirm_large_change")),
        )
        if self.large_change_warning:
            raise forms.ValidationError(self.large_change_warning)
        return cleaned


class InlineNAVUpdateForm(forms.Form):
    nav_per_share = forms.DecimalField(
        label="每股 NAV",
        max_digits=38,
        decimal_places=2,
        min_value=Decimal("0.01"),
        widget=forms.NumberInput(attrs={"step": "0.01", "inputmode": "decimal"}),
    )
    confirm_large_change = forms.BooleanField(required=False, widget=forms.HiddenInput)

    def __init__(self, *args, record: NAVRecord, **kwargs):
        self.record = record
        self.large_change_warning = ""
        kwargs.setdefault("initial", {"nav_per_share": record.nav_per_share})
        super().__init__(*args, **kwargs)

    def clean(self):
        cleaned = super().clean()
        nav_value = cleaned.get("nav_per_share")
        if nav_value is None:
            return cleaned
        if nav_value == self.record.nav_per_share:
            return cleaned
        self.large_change_warning = _large_nav_change_warning(
            share_class=self.record.share_class,
            valuation_month=self.record.valuation_month,
            nav_value=nav_value,
            confirmed=bool(cleaned.get("confirm_large_change")),
        )
        if self.large_change_warning:
            raise forms.ValidationError(self.large_change_warning)
        return cleaned


class ManualRFRForm(forms.Form):
    value_percent = forms.DecimalField(label="年度利率（百分比）", max_digits=12, decimal_places=8)
    reason = forms.CharField(label="覆寫原因", widget=forms.Textarea(attrs={"rows": 3}))
