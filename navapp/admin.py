from django.contrib import admin

from .models import (
    AuditLog,
    Contact,
    Fund,
    FundParty,
    FundStrategyHighlight,
    FundTerm,
    GeneratedFile,
    NAVRecord,
    OrganizationSettings,
    QuarterlyReport,
    ReportRFRObservation,
    RFRObservation,
    RFRSnapshot,
    ShareClass,
)


class StrategyInline(admin.TabularInline):
    model = FundStrategyHighlight
    extra = 0


class PartyInline(admin.TabularInline):
    model = FundParty
    extra = 0


class TermInline(admin.TabularInline):
    model = FundTerm
    extra = 0


class ContactInline(admin.TabularInline):
    model = Contact
    extra = 0


@admin.register(Fund)
class FundAdmin(admin.ModelAdmin):
    list_display = ("short_code", "display_name", "domicile", "is_active")
    search_fields = ("short_code", "display_name", "legal_name")
    inlines = [StrategyInline, PartyInline, TermInline, ContactInline]


@admin.register(ShareClass)
class ShareClassAdmin(admin.ModelAdmin):
    list_display = ("fund", "code", "name", "inception_date", "currency", "is_active")
    list_filter = ("fund", "is_active")


@admin.register(NAVRecord)
class NAVRecordAdmin(admin.ModelAdmin):
    list_display = (
        "share_class",
        "valuation_month",
        "valuation_date",
        "nav_per_share",
        "status",
        "revision",
    )
    list_filter = ("share_class", "status")
    date_hierarchy = "valuation_month"


@admin.register(QuarterlyReport)
class QuarterlyReportAdmin(admin.ModelAdmin):
    list_display = ("share_class", "year", "quarter", "version", "status", "report_date")
    list_filter = ("status", "fund")


@admin.register(GeneratedFile)
class GeneratedFileAdmin(admin.ModelAdmin):
    list_display = ("report", "file_type", "size", "generated_at")
    readonly_fields = ("report", "file_type", "storage_path", "sha256", "size", "generated_at")

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ("created_at", "entity_type", "entity_id", "action", "actor")
    readonly_fields = (
        "actor",
        "entity_type",
        "entity_id",
        "action",
        "before_json",
        "after_json",
        "reason",
        "created_at",
    )

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(RFRSnapshot)
class RFRSnapshotAdmin(admin.ModelAdmin):
    list_display = ("report", "provider", "series", "annual_value_decimal", "is_manual")

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(ReportRFRObservation)
class ReportRFRObservationAdmin(admin.ModelAdmin):
    list_display = ("snapshot", "position", "observation_date", "value_percent")

    def has_delete_permission(self, request, obj=None):
        return False


admin.site.register(OrganizationSettings)
admin.site.register(RFRObservation)
