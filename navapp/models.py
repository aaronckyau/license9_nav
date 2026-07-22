from __future__ import annotations

import calendar
from datetime import date
from decimal import Decimal
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator, RegexValidator
from django.db import models
from django.db.models import Q
from django.urls import reverse

User = get_user_model()


def month_end(value: date) -> date:
    return value.replace(day=calendar.monthrange(value.year, value.month)[1])


def validate_month_end(value: date) -> None:
    if value != month_end(value):
        raise ValidationError("估值月份必須是該月最後一個日曆日。")


class OrganizationSettings(models.Model):
    class RFRProvider(models.TextChoices):
        FRED = "FRED_DGS10", "FRED DGS10"
        TREASURY = "TREASURY_CMT10", "U.S. Treasury CMT 10-Year"
        MANUAL = "MANUAL", "Manual override"

    display_name = models.CharField(max_length=200, default="NAV Quarterly Reporting")
    default_logo = models.ImageField(upload_to="organization/", blank=True)
    primary_brand_colour = models.CharField(
        max_length=7,
        default="#183B73",
        validators=[RegexValidator(r"^#[0-9A-Fa-f]{6}$", "請輸入六位數的十六進位色碼。")],
    )
    professional_investor_statement = models.CharField(
        max_length=300, default="For Professional Investors only"
    )
    report_date_statement_template = models.CharField(
        max_length=300,
        default="All data as on {report_date} unless stated otherwise",
    )
    default_disclaimer = models.TextField(
        default="This document is prepared for informational purposes only."
    )
    disclaimer_version = models.CharField(max_length=50, default="1.0")
    disclaimer_effective_date = models.DateField(null=True, blank=True)
    default_contact_information = models.TextField(blank=True)
    percentage_decimal_places = models.PositiveSmallIntegerField(default=2)
    sharpe_decimal_places = models.PositiveSmallIntegerField(default=3)
    report_language = models.CharField(max_length=10, default="en")
    rfr_provider = models.CharField(
        max_length=30, choices=RFRProvider.choices, default=RFRProvider.FRED
    )
    rfr_series = models.CharField(max_length=50, default="DGS10")
    nav_change_warning_threshold = models.DecimalField(
        max_digits=8,
        decimal_places=6,
        default=Decimal("0.25"),
        validators=[MinValueValidator(Decimal("0"))],
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "organization settings"

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def load(cls) -> OrganizationSettings:
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    def __str__(self) -> str:
        return self.display_name


class Fund(models.Model):
    legal_name = models.CharField(max_length=255)
    display_name = models.CharField(max_length=255)
    short_code = models.SlugField(max_length=30, unique=True)
    structure = models.CharField(max_length=255)
    domicile = models.CharField(max_length=120)
    year_end_month = models.PositiveSmallIntegerField(
        default=12, validators=[MinValueValidator(1), MaxValueValidator(12)]
    )
    year_end_day = models.PositiveSmallIntegerField(
        default=31, validators=[MinValueValidator(1), MaxValueValidator(31)]
    )
    report_language = models.CharField(max_length=10, default="en")
    is_active = models.BooleanField(default=True)
    investment_objective = models.TextField()
    performance_note = models.TextField(blank=True)

    use_org_professional_statement = models.BooleanField(default=True)
    professional_investor_statement_override = models.CharField(max_length=300, blank=True)
    use_org_date_statement = models.BooleanField(default=True)
    date_statement_override = models.CharField(max_length=300, blank=True)
    use_org_disclaimer = models.BooleanField(default=True)
    disclaimer_override = models.TextField(blank=True)
    disclaimer_version_override = models.CharField(max_length=50, blank=True)
    disclaimer_effective_date_override = models.DateField(null=True, blank=True)
    logo_override = models.ImageField(upload_to="funds/logos/", blank=True)
    brand_colour_override = models.CharField(
        max_length=7,
        blank=True,
        validators=[RegexValidator(r"^#[0-9A-Fa-f]{6}$", "請輸入六位數的十六進位色碼。")],
    )
    header_text_override = models.CharField(max_length=300, blank=True)
    custom_docx_template = models.FileField(upload_to="funds/templates/", blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["display_name"]

    def clean(self) -> None:
        super().clean()
        try:
            date(2024, self.year_end_month, self.year_end_day)
        except ValueError as exc:
            raise ValidationError({"year_end_day": "財政年度結束日期無效。"}) from exc
        override_pairs = [
            (self.use_org_professional_statement, self.professional_investor_statement_override),
            (self.use_org_date_statement, self.date_statement_override),
            (self.use_org_disclaimer, self.disclaimer_override),
        ]
        if any(use_org is False and not value.strip() for use_org, value in override_pairs):
            raise ValidationError("停用任何機構預設值時，都必須提供相應的基金覆寫內容。")

    def get_absolute_url(self) -> str:
        return reverse("fund-edit", args=[self.pk])

    def resolved(self) -> dict[str, object]:
        org = OrganizationSettings.load()
        return {
            "professional_statement": (
                org.professional_investor_statement
                if self.use_org_professional_statement
                else self.professional_investor_statement_override
            ),
            "date_statement_template": (
                org.report_date_statement_template
                if self.use_org_date_statement
                else self.date_statement_override
            ),
            "disclaimer": (
                org.default_disclaimer if self.use_org_disclaimer else self.disclaimer_override
            ),
            "disclaimer_version": (
                org.disclaimer_version
                if self.use_org_disclaimer
                else self.disclaimer_version_override
            ),
            "brand_colour": self.brand_colour_override or org.primary_brand_colour,
            "logo_path": (
                self.logo_override.path
                if self.logo_override
                else (org.default_logo.path if org.default_logo else "")
            ),
            "percentage_decimal_places": org.percentage_decimal_places,
            "sharpe_decimal_places": org.sharpe_decimal_places,
        }

    def __str__(self) -> str:
        return self.display_name


class FundStrategyHighlight(models.Model):
    fund = models.ForeignKey(Fund, on_delete=models.CASCADE, related_name="strategy_highlights")
    text = models.TextField()
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "pk"]

    def __str__(self) -> str:
        return self.text[:80]


class FundParty(models.Model):
    class PartyType(models.TextChoices):
        PORTFOLIO_MANAGER = "PORTFOLIO_MANAGER", "Portfolio Manager"
        GENERAL_PARTNER = "GENERAL_PARTNER", "General Partner"
        INVESTMENT_MANAGER = "INVESTMENT_MANAGER", "Investment Manager"
        ADMINISTRATOR = "ADMINISTRATOR", "Fund Administrator"
        AUDITOR = "AUDITOR", "Auditor"
        LEGAL_ADVISER = "LEGAL_ADVISER", "Legal Adviser"
        CUSTODIAN = "CUSTODIAN", "Custodian / Prime Broker"
        OTHER = "OTHER", "Other"

    fund = models.ForeignKey(Fund, on_delete=models.CASCADE, related_name="parties")
    party_type = models.CharField(max_length=40, choices=PartyType.choices)
    display_label = models.CharField(max_length=100)
    value = models.CharField(max_length=255)
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "pk"]

    def __str__(self) -> str:
        return f"{self.display_label}: {self.value}"


class FundTerm(models.Model):
    fund = models.ForeignKey(Fund, on_delete=models.CASCADE, related_name="terms")
    key = models.SlugField(max_length=60)
    display_label = models.CharField(max_length=100)
    value_text = models.CharField(max_length=255)
    display_in_report = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "pk"]
        constraints = [models.UniqueConstraint(fields=["fund", "key"], name="unique_fund_term_key")]

    def __str__(self) -> str:
        return f"{self.display_label}: {self.value_text}"


class Contact(models.Model):
    fund = models.ForeignKey(Fund, on_delete=models.CASCADE, related_name="contacts")
    role = models.CharField(max_length=100)
    name = models.CharField(max_length=150)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=80, blank=True)
    address = models.TextField(blank=True)
    display_in_report = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "pk"]

    def __str__(self) -> str:
        return f"{self.role}: {self.name}"


class ShareClass(models.Model):
    class ReturnBasis(models.TextChoices):
        NET = "NET", "Net"
        GROSS = "GROSS", "Gross"

    fund = models.ForeignKey(Fund, on_delete=models.PROTECT, related_name="share_classes")
    name = models.CharField(max_length=150)
    code = models.SlugField(max_length=40)
    inception_date = models.DateField()
    inception_nav = models.DecimalField(
        max_digits=38,
        decimal_places=18,
        validators=[MinValueValidator(Decimal("0.000000000000000001"))],
    )
    currency = models.CharField(max_length=3)
    return_basis = models.CharField(
        max_length=10, choices=ReturnBasis.choices, default=ReturnBasis.NET
    )
    management_fee_override = models.CharField(max_length=100, blank=True)
    performance_fee_override = models.CharField(max_length=100, blank=True)
    bloomberg_code_override = models.CharField(max_length=100, blank=True)
    is_active = models.BooleanField(default=True)
    display_in_quarterly_report = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["fund__display_name", "name"]
        constraints = [
            models.UniqueConstraint(fields=["fund", "code"], name="unique_share_class_code")
        ]

    def clean(self) -> None:
        super().clean()
        self.currency = self.currency.upper()

    def get_absolute_url(self) -> str:
        return reverse("nav-history", args=[self.pk])

    def __str__(self) -> str:
        return f"{self.fund.short_code} / {self.name}"


class NAVRecord(models.Model):
    class Status(models.TextChoices):
        OFFICIAL = "OFFICIAL", "Official"
        INDICATIVE = "INDICATIVE", "Indicative"

    share_class = models.ForeignKey(
        ShareClass, on_delete=models.PROTECT, related_name="nav_records"
    )
    valuation_month = models.DateField(validators=[validate_month_end])
    valuation_date = models.DateField()
    nav_per_share = models.DecimalField(
        max_digits=38,
        decimal_places=18,
        validators=[MinValueValidator(Decimal("0.000000000000000001"))],
    )
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.OFFICIAL)
    note = models.TextField(blank=True)
    raw_source_date = models.CharField(max_length=100, blank=True)
    source_sheet = models.CharField(max_length=150, blank=True)
    source_cell = models.CharField(max_length=30, blank=True)
    is_active = models.BooleanField(default=True)
    revision = models.PositiveIntegerField(default=1)
    change_acknowledged = models.BooleanField(default=False)
    created_by = models.ForeignKey(
        User, on_delete=models.PROTECT, related_name="nav_records_created", null=True, blank=True
    )
    updated_by = models.ForeignKey(
        User, on_delete=models.PROTECT, related_name="nav_records_updated", null=True, blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["share_class", "valuation_month"]
        indexes = [models.Index(fields=["share_class", "valuation_month"])]
        constraints = [
            models.UniqueConstraint(
                fields=["share_class", "valuation_month"],
                condition=Q(is_active=True),
                name="unique_active_nav_month",
            )
        ]

    def clean(self) -> None:
        super().clean()
        if self.valuation_date < self.share_class.inception_date:
            raise ValidationError({"valuation_date": "估值日期不得早於股份類別成立日期。"})
        if self.valuation_month < month_end(self.share_class.inception_date):
            raise ValidationError({"valuation_month": "估值月份不得早於股份類別成立月份。"})

    def __str__(self) -> str:
        return f"{self.share_class} {self.valuation_month:%Y-%m}: {self.nav_per_share}"


class RFRObservation(models.Model):
    provider = models.CharField(max_length=30)
    series = models.CharField(max_length=50)
    observation_date = models.DateField()
    value_percent = models.DecimalField(max_digits=12, decimal_places=8)
    fetched_at = models.DateTimeField()
    raw_checksum = models.CharField(max_length=64)

    class Meta:
        ordering = ["observation_date"]
        indexes = [models.Index(fields=["provider", "series", "observation_date"])]
        constraints = [
            models.UniqueConstraint(
                fields=["provider", "series", "observation_date"],
                name="unique_rfr_observation",
            )
        ]

    def __str__(self) -> str:
        return f"{self.provider} {self.observation_date}: {self.value_percent}%"


class QuarterlyReport(models.Model):
    class ReportLanguage(models.TextChoices):
        TRADITIONAL_CHINESE = "zh-Hant", "繁體中文"
        SIMPLIFIED_CHINESE = "zh-Hans", "簡體中文"

    class ReportType(models.TextChoices):
        MONTHLY = "MONTHLY", "Monthly"
        QUARTERLY = "QUARTERLY", "Quarterly"

    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        READY = "READY", "Ready"
        FINAL = "FINAL", "Final"
        STALE = "STALE", "Stale / Regeneration Required"
        GENERATION_FAILED = "GENERATION_FAILED", "Generation failed"

    fund = models.ForeignKey(Fund, on_delete=models.PROTECT, related_name="reports")
    share_class = models.ForeignKey(ShareClass, on_delete=models.PROTECT, related_name="reports")
    report_type = models.CharField(
        max_length=12,
        choices=ReportType.choices,
        default=ReportType.QUARTERLY,
    )
    report_language = models.CharField(
        max_length=10,
        choices=ReportLanguage.choices,
        default=ReportLanguage.TRADITIONAL_CHINESE,
    )
    year = models.PositiveIntegerField()
    report_month = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(12)]
    )
    quarter = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(4)]
    )
    version = models.PositiveIntegerField(default=1)
    report_date = models.DateField()
    status = models.CharField(max_length=30, choices=Status.choices, default=Status.DRAFT)
    commentary_title = models.CharField(max_length=200, blank=True)
    commentary_markdown = models.TextField(blank=True)
    commentary_author = models.CharField(max_length=150, blank=True)
    commentary_date = models.DateField(null=True, blank=True)
    formula_version = models.CharField(max_length=50, default="legacy_excel_v1")
    snapshot = models.JSONField(default=dict, blank=True)
    generation_error = models.TextField(blank=True)
    created_by = models.ForeignKey(
        User, on_delete=models.PROTECT, related_name="reports_created", null=True, blank=True
    )
    finalized_by = models.ForeignKey(
        User, on_delete=models.PROTECT, related_name="reports_finalized", null=True, blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    finalized_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-report_date", "-version"]
        indexes = [
            models.Index(
                fields=["share_class", "report_type", "report_date", "status"],
                name="navapp_report_period_idx",
            )
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["share_class", "report_type", "report_date", "version"],
                name="unique_report_period_version",
            )
        ]

    def clean(self) -> None:
        super().clean()
        if self.share_class_id and self.fund_id and self.share_class.fund_id != self.fund_id:
            raise ValidationError({"share_class": "股份類別必須屬於所選基金。"})
        if not self.report_date:
            return
        if self.report_date != month_end(self.report_date):
            raise ValidationError({"report_date": "報告日期必須是日曆月底。"})
        if self.year != self.report_date.year:
            raise ValidationError({"year": "報告年度必須與報告日期一致。"})
        if self.report_month != self.report_date.month:
            raise ValidationError({"report_month": "報告月份必須與報告日期一致。"})
        expected_quarter = (self.report_date.month - 1) // 3 + 1
        if self.quarter != expected_quarter:
            raise ValidationError({"quarter": "季度必須與報告月份一致。"})
        if self.report_type == self.ReportType.QUARTERLY and self.report_date != self.quarter_end:
            raise ValidationError({"report_date": "報告日期必須是該季度的日曆季末。"})

    def save(self, *args, **kwargs):
        if self.report_date:
            if not self.report_month:
                self.report_month = self.report_date.month
            if not self.year:
                self.year = self.report_date.year
            if not self.quarter:
                self.quarter = (self.report_date.month - 1) // 3 + 1
        if self.pk:
            old = QuarterlyReport.objects.filter(pk=self.pk).first()
            if old and old.status in {self.Status.FINAL, self.Status.STALE}:
                if self.status != old.status and not (
                    old.status == self.Status.FINAL and self.status == self.Status.STALE
                ):
                    raise ValidationError("已定稿報告的狀態只可由「已定稿」轉為「需重新產生」。")
                immutable = (
                    "fund_id",
                    "share_class_id",
                    "report_type",
                    "report_language",
                    "year",
                    "report_month",
                    "quarter",
                    "version",
                    "report_date",
                    "commentary_title",
                    "commentary_markdown",
                    "commentary_author",
                    "commentary_date",
                    "formula_version",
                    "snapshot",
                    "created_by_id",
                    "finalized_by_id",
                    "finalized_at",
                )
                if any(getattr(old, field) != getattr(self, field) for field in immutable):
                    raise ValidationError("已定稿報告的內容及快照不可修改。")
        super().save(*args, **kwargs)

    @property
    def quarter_end(self) -> date:
        month = self.quarter * 3
        return date(self.year, month, calendar.monthrange(self.year, month)[1])

    @property
    def label(self) -> str:
        return self.period_label

    @property
    def period_label(self) -> str:
        if self.report_type == self.ReportType.MONTHLY:
            return f"{self.year} 年 {self.report_month} 月月報"
        return f"{self.year} 年第 {self.quarter} 季季報"

    @property
    def period_label_en(self) -> str:
        if self.report_type == self.ReportType.MONTHLY:
            return f"{self.report_date:%B %Y} Monthly Report"
        return f"{self.year} Q{self.quarter} Quarterly Report"

    def get_absolute_url(self) -> str:
        return reverse("report-review", args=[self.pk])

    def __str__(self) -> str:
        return f"{self.share_class} {self.label}"


class RFRSnapshot(models.Model):
    report = models.OneToOneField(
        QuarterlyReport, on_delete=models.CASCADE, related_name="rfr_snapshot"
    )
    provider = models.CharField(max_length=30)
    series = models.CharField(max_length=50)
    annual_value_decimal = models.DecimalField(max_digits=24, decimal_places=18)
    is_manual = models.BooleanField(default=False)
    override_reason = models.TextField(blank=True)
    override_by = models.ForeignKey(User, on_delete=models.PROTECT, null=True, blank=True)
    override_at = models.DateTimeField(null=True, blank=True)
    raw_checksum = models.CharField(max_length=64, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def clean(self) -> None:
        super().clean()
        if self.is_manual and not self.override_reason.strip():
            raise ValidationError({"override_reason": "手動覆寫必須填寫原因。"})

    def save(self, *args, **kwargs):
        if (
            self.pk
            and QuarterlyReport.objects.filter(
                pk=self.report_id,
                status__in=(QuarterlyReport.Status.FINAL, QuarterlyReport.Status.STALE),
            ).exists()
        ):
            raise ValidationError("已定稿報告的無風險利率快照不可修改。")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if QuarterlyReport.objects.filter(
            pk=self.report_id,
            status__in=(QuarterlyReport.Status.FINAL, QuarterlyReport.Status.STALE),
        ).exists():
            raise ValidationError("已定稿報告的無風險利率快照不可修改。")
        return super().delete(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.report.label} {self.provider}: {self.annual_value_decimal}"


class ReportRFRObservation(models.Model):
    snapshot = models.ForeignKey(RFRSnapshot, on_delete=models.CASCADE, related_name="observations")
    source_observation = models.ForeignKey(
        RFRObservation, on_delete=models.PROTECT, null=True, blank=True
    )
    position = models.PositiveSmallIntegerField()
    observation_date = models.DateField()
    value_percent = models.DecimalField(max_digits=12, decimal_places=8)

    class Meta:
        ordering = ["position"]
        constraints = [
            models.UniqueConstraint(
                fields=["snapshot", "position"], name="unique_rfr_snapshot_position"
            ),
            models.UniqueConstraint(
                fields=["snapshot", "observation_date"], name="unique_rfr_snapshot_date"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.snapshot.report.label} #{self.position}: {self.value_percent}%"

    def save(self, *args, **kwargs):
        if (
            self.pk
            and QuarterlyReport.objects.filter(
                pk=self.snapshot.report_id,
                status__in=(QuarterlyReport.Status.FINAL, QuarterlyReport.Status.STALE),
            ).exists()
        ):
            raise ValidationError("已定稿報告的無風險利率觀察值不可修改。")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if QuarterlyReport.objects.filter(
            pk=self.snapshot.report_id,
            status__in=(QuarterlyReport.Status.FINAL, QuarterlyReport.Status.STALE),
        ).exists():
            raise ValidationError("已定稿報告的無風險利率觀察值不可修改。")
        return super().delete(*args, **kwargs)


class GeneratedFile(models.Model):
    class FileType(models.TextChoices):
        DOCX = "DOCX", "Word document"
        PDF = "PDF", "PDF document"

    report = models.ForeignKey(QuarterlyReport, on_delete=models.PROTECT, related_name="files")
    file_type = models.CharField(max_length=10, choices=FileType.choices)
    storage_path = models.CharField(max_length=500)
    sha256 = models.CharField(max_length=64)
    size = models.PositiveBigIntegerField()
    generated_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["file_type"]
        constraints = [
            models.UniqueConstraint(fields=["report", "file_type"], name="unique_report_file_type")
        ]

    @property
    def absolute_path(self) -> Path:
        path = (Path(settings.MEDIA_ROOT) / self.storage_path).resolve()
        media_root = Path(settings.MEDIA_ROOT).resolve()
        if path != media_root and media_root not in path.parents:
            raise ValueError("Generated file path escapes MEDIA_ROOT.")
        return path

    def save(self, *args, **kwargs):
        if (
            self.pk
            and QuarterlyReport.objects.filter(
                pk=self.report_id,
                status__in=(QuarterlyReport.Status.FINAL, QuarterlyReport.Status.STALE),
            ).exists()
        ):
            raise ValidationError("已定稿報告的檔案不可修改。")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if QuarterlyReport.objects.filter(
            pk=self.report_id,
            status__in=(QuarterlyReport.Status.FINAL, QuarterlyReport.Status.STALE),
        ).exists():
            raise ValidationError("已定稿報告的檔案不可修改。")
        return super().delete(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.report.label} {self.file_type}"


class AuditLog(models.Model):
    actor = models.ForeignKey(User, on_delete=models.PROTECT, null=True, blank=True)
    entity_type = models.CharField(max_length=100)
    entity_id = models.CharField(max_length=100)
    action = models.CharField(max_length=100)
    before_json = models.JSONField(default=dict, blank=True)
    after_json = models.JSONField(default=dict, blank=True)
    reason = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["entity_type", "entity_id", "created_at"])]

    def __str__(self) -> str:
        return f"{self.created_at:%Y-%m-%d %H:%M} {self.entity_type} {self.action}"

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValidationError("稽核紀錄只能新增，不可修改。")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("稽核紀錄只能新增，不可刪除。")
