from __future__ import annotations

import re
from datetime import date
from decimal import Decimal
from zipfile import BadZipFile, ZipFile

from django import forms
from django.conf import settings
from django.forms import inlineformset_factory

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


class DateInput(forms.DateInput):
    input_type = "date"


class OrganizationSettingsForm(forms.ModelForm):
    class Meta:
        model = OrganizationSettings
        exclude = ()
        widgets = {
            "disclaimer_effective_date": DateInput(),
            "default_disclaimer": forms.Textarea(attrs={"rows": 8}),
            "default_contact_information": forms.Textarea(attrs={"rows": 4}),
        }


class FundForm(forms.ModelForm):
    class Meta:
        model = Fund
        exclude = ("created_at", "updated_at")
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
            raise forms.ValidationError("Custom report template must be a .docx file.")
        if uploaded.size > settings.MAX_UPLOAD_BYTES:
            raise forms.ValidationError("Custom report template exceeds the upload limit.")
        content_type = getattr(uploaded, "content_type", "")
        if content_type and content_type not in {
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "application/octet-stream",
        }:
            raise forms.ValidationError("Custom report template has an invalid MIME type.")
        try:
            uploaded.seek(0)
            with ZipFile(uploaded) as archive:
                members = archive.infolist()
                if sum(member.file_size for member in members) > settings.MAX_UPLOAD_BYTES * 10:
                    raise forms.ValidationError(
                        "The uncompressed custom template exceeds the safety limit."
                    )
                required_members = {"[Content_Types].xml", "word/document.xml"}
                if not required_members.issubset(member.filename for member in members):
                    raise forms.ValidationError(
                        "The custom report template is missing required DOCX members."
                    )
                package_text = "".join(
                    archive.read(name).decode("utf-8", errors="ignore")
                    for name in archive.namelist()
                    if name.endswith((".xml", ".rels"))
                )
        except (BadZipFile, KeyError, OSError, RuntimeError) as exc:
            raise forms.ValidationError(
                "The custom report template is not a valid DOCX package."
            ) from exc
        finally:
            uploaded.seek(0)
        missing = [name for name in REQUIRED_CUSTOM_PLACEHOLDERS if name not in package_text]
        if missing:
            raise forms.ValidationError(
                "Missing required placeholders: " + ", ".join(sorted(missing))
            )
        lower = package_text.lower()
        if 'targetmode="external"' in lower and (".xlsx" in lower or "oleobject" in lower):
            raise forms.ValidationError("External Excel relationships are not allowed.")
        return uploaded


StrategyFormSet = inlineformset_factory(
    Fund,
    FundStrategyHighlight,
    fields=("text", "sort_order"),
    extra=1,
    can_delete=True,
    min_num=1,
    validate_min=True,
)
PartyFormSet = inlineformset_factory(
    Fund,
    FundParty,
    fields=("party_type", "display_label", "value", "sort_order"),
    extra=1,
    can_delete=True,
)
TermFormSet = inlineformset_factory(
    Fund,
    FundTerm,
    fields=("key", "display_label", "value_text", "display_in_report", "sort_order"),
    extra=1,
    can_delete=True,
)
ContactFormSet = inlineformset_factory(
    Fund,
    Contact,
    fields=("role", "name", "email", "phone", "address", "display_in_report", "sort_order"),
    extra=1,
    can_delete=True,
)


class ShareClassForm(forms.ModelForm):
    class Meta:
        model = ShareClass
        exclude = ("fund", "created_at", "updated_at")
        widgets = {"inception_date": DateInput()}


class NAVRecordForm(forms.ModelForm):
    acknowledge_large_change = forms.BooleanField(
        required=False,
        help_text="Required when the change from the preceding month exceeds the configured threshold.",
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
        widgets = {"valuation_month": DateInput(), "valuation_date": DateInput()}

    def __init__(self, *args, share_class: ShareClass | None = None, **kwargs):
        super().__init__(*args, **kwargs)
        self.share_class = share_class or getattr(self.instance, "share_class", None)

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
                    f"NAV changes by {change * 100:.2f}% from {prior.valuation_month:%Y-%m}. "
                    "Review and acknowledge before saving.",
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
    reason = forms.CharField(widget=forms.Textarea(attrs={"rows": 3}))


class BulkImportForm(forms.Form):
    file = forms.FileField(help_text="CSV or XLSX; maximum 10 MB.")

    def clean_file(self):
        uploaded = self.cleaned_data["file"]
        if uploaded.size > settings.MAX_UPLOAD_BYTES:
            raise forms.ValidationError("Upload exceeds the configured size limit.")
        suffix = uploaded.name.rsplit(".", 1)[-1].lower()
        if suffix not in {"csv", "xlsx"}:
            raise forms.ValidationError("Only CSV and XLSX files are supported.")
        expected_types = {
            "csv": {"text/csv", "application/csv", "text/plain", "application/octet-stream"},
            "xlsx": {
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                "application/octet-stream",
            },
        }
        content_type = getattr(uploaded, "content_type", "")
        if content_type and content_type not in expected_types[suffix]:
            raise forms.ValidationError("The upload MIME type does not match its extension.")
        return uploaded


class ReportCreateForm(forms.ModelForm):
    class Meta:
        model = QuarterlyReport
        fields = ("share_class", "year", "quarter")

    def clean(self):
        cleaned = super().clean()
        year = cleaned.get("year")
        quarter = cleaned.get("quarter")
        if year and quarter:
            month = quarter * 3
            report_date = month_end(date(year, month, 1))
            cleaned["report_date"] = report_date
            self.instance.report_date = report_date
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
        widgets = {
            "commentary_markdown": forms.Textarea(attrs={"rows": 14}),
            "commentary_date": DateInput(),
        }

    def clean_commentary_markdown(self):
        value = self.cleaned_data["commentary_markdown"]
        if re.search(r"<\s*/?\s*[a-zA-Z][^>]*>", value):
            raise forms.ValidationError("Raw HTML is not supported. Use the safe Markdown subset.")
        if not value.strip():
            raise forms.ValidationError("Manager Commentary is required.")
        return value


class ManualRFRForm(forms.Form):
    value_percent = forms.DecimalField(max_digits=12, decimal_places=8)
    reason = forms.CharField(widget=forms.Textarea(attrs={"rows": 3}))
