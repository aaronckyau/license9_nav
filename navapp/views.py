from __future__ import annotations

import tempfile
from datetime import date
from decimal import Decimal
from pathlib import Path

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core import signing
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.db import connections, transaction
from django.db.models import Prefetch
from django.http import FileResponse, Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.safestring import mark_safe
from django.views.decorators.http import require_GET, require_POST

from navapp.forms import (
    BulkImportForm,
    CommentaryForm,
    ContactFormSet,
    FundForm,
    InlineNAVUpdateForm,
    ManualRFRForm,
    OrganizationSettingsForm,
    PartyFormSet,
    ReportCreateForm,
    ReportHistoryCommentaryForm,
    ShareClassForm,
    SimpleEntryForm,
    StrategyFormSet,
    TermFormSet,
    latest_completed_month,
)
from navapp.models import (
    AuditLog,
    Fund,
    GeneratedFile,
    NAVRecord,
    OrganizationSettings,
    QuarterlyReport,
    ShareClass,
    month_end,
)
from navapp.services.calculations import CalculationValidationError, calculate_for_report
from navapp.services.commentary import render_safe_html
from navapp.services.imports import (
    ImportRow,
    ImportValidationError,
    import_rows,
    parse_uploaded_nav,
)
from navapp.services.nav_dashboard import (
    DashboardYear,
    build_nav_dashboard_years,
    generate_nav_year_chart,
)
from navapp.services.reports import (
    ReportGenerationError,
    build_current_snapshot,
    finalize_report,
    generate_nav_chart,
    generate_report_files,
    mark_affected_reports_stale,
    mark_fund_reports_stale,
    mark_organization_reports_stale,
    mark_share_class_reports_stale,
    reset_affected_mutable_reports,
)
from navapp.services.rfr import (
    RFRProviderError,
    RFRValidationError,
    refresh_report_rfr,
    set_manual_snapshot,
)


@require_GET
def healthz(request):
    return JsonResponse({"status": "ok"})


@require_GET
def readyz(request):
    try:
        with connections["default"].cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except Exception:
        return JsonResponse({"status": "not-ready", "detail": "database unavailable"}, status=503)
    return JsonResponse({"status": "ready"})


@login_required
def dashboard(request):
    classes = ShareClass.objects.filter(fund__is_active=True, is_active=True).select_related("fund")
    cards = []
    for share_class in classes:
        latest_nav = (
            share_class.nav_records.filter(is_active=True).order_by("-valuation_month").first()
        )
        latest_report = share_class.reports.order_by(
            "-report_date", "-updated_at", "-version"
        ).first()
        cards.append(
            {
                "share_class": share_class,
                "latest_nav": latest_nav,
                "latest_report": latest_report,
                "status": latest_report.status if latest_report else "COMMENTARY_REQUIRED",
            }
        )
    return render(request, "navapp/dashboard.html", {"cards": cards})


@login_required
def fund_list(request):
    return render(request, "navapp/fund_list.html", {"funds": Fund.objects.all()})


@login_required
def fund_edit(request, pk=None):
    instance = get_object_or_404(Fund, pk=pk) if pk else Fund()
    formsets = [
        ("strategies", "策略重點", StrategyFormSet),
        ("parties", "基金相關機構", PartyFormSet),
        ("terms", "基金條款", TermFormSet),
        ("contacts", "報告聯絡資料", ContactFormSet),
    ]
    if request.method == "POST":
        form = FundForm(request.POST, request.FILES, instance=instance)
        bound = [
            (label, factory(request.POST, instance=instance, prefix=prefix))
            for prefix, label, factory in formsets
        ]
        if form.is_valid() and all(item.is_valid() for _, item in bound):
            changed_fields = list(form.changed_data)
            related_changed = [item.prefix for _, item in bound if item.has_changed()]
            with transaction.atomic():
                fund = form.save()
                for _, item in bound:
                    item.instance = fund
                    item.save()
                AuditLog.objects.create(
                    actor=request.user,
                    entity_type="Fund",
                    entity_id=str(fund.pk),
                    action="UPDATE" if pk else "CREATE",
                    after_json={
                        "short_code": fund.short_code,
                        "display_name": fund.display_name,
                        "changed_fields": changed_fields,
                        "related_changed": related_changed,
                    },
                )
                if pk and (changed_fields or related_changed):
                    stale_count = mark_fund_reports_stale(
                        fund,
                        request.user,
                        "基金設定已變更：" + "、".join(changed_fields + related_changed),
                    )
                    if stale_count:
                        messages.warning(
                            request,
                            f"已有 {stale_count} 份已定稿報告被標示為需要重新產生。",
                        )
            messages.success(request, "基金設定已儲存。")
            return redirect("fund-edit", pk=fund.pk)
    else:
        form = FundForm(instance=instance)
        bound = [
            (label, factory(instance=instance, prefix=prefix))
            for prefix, label, factory in formsets
        ]
    return render(
        request,
        "navapp/fund_form.html",
        {
            "form": form,
            "fund": instance,
            "formsets": [{"label": label, "formset": formset} for label, formset in bound],
        },
    )


@login_required
def share_class_edit(request, fund_pk, pk=None):
    fund = get_object_or_404(Fund, pk=fund_pk)
    instance = get_object_or_404(ShareClass, pk=pk, fund=fund) if pk else ShareClass(fund=fund)
    if request.method == "POST":
        form = ShareClassForm(request.POST, instance=instance)
        if form.is_valid():
            changed_fields = list(form.changed_data)
            with transaction.atomic():
                share_class = form.save()
                AuditLog.objects.create(
                    actor=request.user,
                    entity_type="ShareClass",
                    entity_id=str(share_class.pk),
                    action="UPDATE" if pk else "CREATE",
                    after_json={
                        "code": share_class.code,
                        "name": share_class.name,
                        "changed_fields": changed_fields,
                    },
                )
                if pk and changed_fields:
                    stale_count = mark_share_class_reports_stale(
                        share_class,
                        request.user,
                        "股份類別設定已變更：" + "、".join(changed_fields),
                    )
                    if stale_count:
                        messages.warning(
                            request,
                            f"已有 {stale_count} 份已定稿報告被標示為需要重新產生。",
                        )
            messages.success(request, "股份類別已儲存。")
            return redirect("nav-history", pk=share_class.pk)
    else:
        form = ShareClassForm(instance=instance)
    return render(
        request,
        "navapp/generic_form.html",
        {"form": form, "title": "股份類別", "subtitle": fund.display_name},
    )


@login_required
def nav_history(request, pk):
    share_class = get_object_or_404(ShareClass.objects.select_related("fund"), pk=pk)
    records = share_class.nav_records.filter(is_active=True).order_by("-valuation_month")
    return render(
        request,
        "navapp/nav_history.html",
        {"share_class": share_class, "records": records},
    )


def _portfolio_manager_name(share_class: ShareClass) -> str:
    portfolio_manager = share_class.fund.parties.filter(party_type="PORTFOLIO_MANAGER").first()
    return portfolio_manager.value if portfolio_manager else ""


def _draft_report_for_period(
    share_class: ShareClass, year: int, quarter: int, user
) -> tuple[QuarterlyReport, bool]:
    latest = (
        QuarterlyReport.objects.filter(
            share_class=share_class,
            report_type=QuarterlyReport.ReportType.QUARTERLY,
            year=year,
            quarter=quarter,
        )
        .order_by("-version")
        .first()
    )
    if latest and latest.status not in {
        QuarterlyReport.Status.FINAL,
        QuarterlyReport.Status.STALE,
    }:
        return latest, False
    version = latest.version + 1 if latest else 1
    report_date = month_end(date(year, quarter * 3, 1))
    report = QuarterlyReport(
        fund=share_class.fund,
        share_class=share_class,
        report_type=QuarterlyReport.ReportType.QUARTERLY,
        year=year,
        report_month=quarter * 3,
        quarter=quarter,
        version=version,
        report_date=report_date,
        commentary_author=_portfolio_manager_name(share_class),
        commentary_date=report_date,
        created_by=user,
    )
    report.full_clean()
    report.save()
    return report, True


def _simple_nav_years(
    share_class: ShareClass, selected_year: int, default_period: date
) -> list[DashboardYear]:
    records = share_class.nav_records.filter(is_active=True).order_by("valuation_month")
    return build_nav_dashboard_years(
        records,
        next_period=date(selected_year, 1, 1),
        default_period=default_period,
        inception_month=month_end(share_class.inception_date),
    )


@login_required
def simple_entry(request, share_class_pk):
    share_class = get_object_or_404(
        ShareClass.objects.select_related("fund"),
        pk=share_class_pk,
        is_active=True,
        fund__is_active=True,
    )
    action = request.POST.get("action", "create_nav") if request.method == "POST" else ""
    form = SimpleEntryForm(
        request.POST if action == "create_nav" else None,
        share_class=share_class,
    )
    selected_year_raw = request.POST.get("return_year") or request.GET.get("year")
    try:
        selected_year = int(selected_year_raw) if selected_year_raw else form.default_period.year
    except (TypeError, ValueError):
        selected_year = form.default_period.year
    selected_year = min(
        max(selected_year, share_class.inception_date.year),
        form.default_period.year + 1,
    )
    inline_update_form = None
    inline_update_record = None
    if request.method == "POST" and action == "update_nav":
        inline_update_record = get_object_or_404(
            NAVRecord,
            pk=request.POST.get("record_id"),
            share_class=share_class,
            is_active=True,
        )
        inline_update_form = InlineNAVUpdateForm(
            request.POST,
            record=inline_update_record,
        )
        if inline_update_form.is_valid():
            reason = "由年度 NAV 表直接修改。"
            new_nav_value = inline_update_form.cleaned_data["nav_per_share"]
            with transaction.atomic():
                locked_record = NAVRecord.objects.select_for_update().get(
                    pk=inline_update_record.pk
                )
                if locked_record.nav_per_share == new_nav_value:
                    changed = False
                    stale_count = 0
                else:
                    changed = True
                    before = _nav_json(locked_record)
                    locked_record.nav_per_share = new_nav_value
                    locked_record.change_acknowledged = bool(
                        inline_update_form.cleaned_data.get("confirm_large_change")
                    )
                    locked_record.revision += 1
                    locked_record.updated_by = request.user
                    locked_record.full_clean()
                    locked_record.save()
                    AuditLog.objects.create(
                        actor=request.user,
                        entity_type="NAVRecord",
                        entity_id=str(locked_record.pk),
                        action="UPDATE",
                        before_json=before,
                        after_json=_nav_json(locked_record),
                        reason=reason,
                    )
                    stale_count = mark_affected_reports_stale(
                        locked_record,
                        request.user,
                        reason,
                    )
                    reset_affected_mutable_reports(
                        locked_record,
                        request.user,
                        reason,
                    )
            if not changed:
                messages.info(request, "NAV 數值沒有變更。")
            elif stale_count:
                messages.warning(
                    request,
                    f"NAV 已更新；{stale_count} 份受影響的定稿報告已標示為需重新產生。",
                )
            else:
                messages.success(request, "NAV 已更新。")
            return redirect(
                f"{reverse('simple-entry', args=[share_class.pk])}?year={selected_year}"
            )
    elif request.method == "POST" and form.is_valid():
        valuation_month = form.cleaned_data["valuation_month"]
        quarter = (valuation_month.month - 1) // 3 + 1
        with transaction.atomic():
            nav = NAVRecord(
                share_class=share_class,
                valuation_month=valuation_month,
                valuation_date=valuation_month,
                nav_per_share=form.cleaned_data["nav_per_share"],
                status=NAVRecord.Status.OFFICIAL,
                change_acknowledged=bool(form.cleaned_data.get("confirm_large_change")),
                created_by=request.user,
                updated_by=request.user,
            )
            nav.full_clean()
            nav.save()
            report, created = _draft_report_for_period(
                share_class,
                valuation_month.year,
                quarter,
                request.user,
            )
            report.status = QuarterlyReport.Status.DRAFT
            report.snapshot = {}
            report.generation_error = ""
            report.save(
                update_fields=[
                    "status",
                    "snapshot",
                    "generation_error",
                    "updated_at",
                ]
            )
            mark_affected_reports_stale(
                nav,
                request.user,
                "新增月份 NAV。",
            )
            reset_affected_mutable_reports(
                nav,
                request.user,
                "新增月份 NAV。",
            )
            AuditLog.objects.create(
                actor=request.user,
                entity_type="NAVRecord",
                entity_id=str(nav.pk),
                action="CREATE",
                after_json=_nav_json(nav),
            )
            AuditLog.objects.create(
                actor=request.user,
                entity_type="QuarterlyReport",
                entity_id=str(report.pk),
                action="SIMPLE_ENTRY",
                after_json={
                    "created": created,
                    "share_class_id": share_class.pk,
                    "valuation_month": valuation_month.isoformat(),
                    "nav_record_id": nav.pk,
                    "report_period": f"{report.year} Q{report.quarter}",
                },
            )
        messages.success(
            request,
            f"{valuation_month:%Y 年 %m 月} NAV 已儲存；月度及累積回報已自動更新。",
        )
        return redirect(f"{reverse('simple-entry', args=[share_class.pk])}?year={selected_year}")
    return render(
        request,
        "navapp/simple_entry.html",
        {
            "form": form,
            "share_class": share_class,
            "system_date": form.system_date,
            "default_period": form.default_period,
            "next_period": form.next_period,
            "nav_years": _simple_nav_years(
                share_class,
                selected_year,
                form.default_period,
            ),
            "selected_year": selected_year,
            "entry_years": range(
                form.default_period.year + 1,
                share_class.inception_date.year - 1,
                -1,
            ),
            "create_error_period": (
                request.POST.get("valuation_month", "")
                if request.method == "POST" and action == "create_nav"
                else ""
            ),
            "inline_update_form": inline_update_form,
            "inline_update_record": inline_update_record,
        },
    )


@login_required
@require_GET
def nav_year_chart(request, share_class_pk, year):
    share_class = get_object_or_404(
        ShareClass,
        pk=share_class_pk,
        is_active=True,
        fund__is_active=True,
    )
    records = list(
        share_class.nav_records.filter(
            is_active=True,
            valuation_month__year=year,
        ).order_by("valuation_month")
    )
    if not records:
        raise Http404("該年度沒有 NAV 紀錄。")
    response = HttpResponse(
        generate_nav_year_chart(records, mobile=request.GET.get("layout") == "mobile"),
        content_type="image/png",
    )
    response["Cache-Control"] = "private, no-store"
    return response


def _nav_json(item: NAVRecord) -> dict[str, str | int]:
    return {
        "valuation_month": item.valuation_month.isoformat(),
        "valuation_date": item.valuation_date.isoformat(),
        "nav_per_share": str(item.nav_per_share),
        "status": item.status,
        "note": item.note,
        "revision": item.revision,
    }


@login_required
@require_GET
def nav_edit(request, share_class_pk, pk=None):
    share_class = get_object_or_404(ShareClass, pk=share_class_pk)
    if pk:
        get_object_or_404(NAVRecord, pk=pk, share_class=share_class)
    messages.info(request, "請在年度 NAV 表直接輸入或修改數值。")
    return redirect("simple-entry", share_class_pk=share_class.pk)


@login_required
@require_POST
def nav_delete(request, share_class_pk, pk):
    share_class = get_object_or_404(ShareClass, pk=share_class_pk, is_active=True)
    with transaction.atomic():
        record = get_object_or_404(
            NAVRecord.objects.select_for_update(),
            pk=pk,
            share_class=share_class,
            is_active=True,
        )
        before = _nav_json(record)
        record.is_active = False
        record.revision += 1
        record.updated_by = request.user
        record.save(update_fields=["is_active", "revision", "updated_by", "updated_at"])
        AuditLog.objects.create(
            actor=request.user,
            entity_type="NAVRecord",
            entity_id=str(record.pk),
            action="DELETE",
            before_json=before,
            reason="使用者於每月 NAV 表格刪除紀錄",
        )
        stale_count = mark_affected_reports_stale(
            record,
            request.user,
            "NAV 紀錄已刪除",
        )
        reset_affected_mutable_reports(record, request.user, "NAV 紀錄已刪除")
    if stale_count:
        messages.warning(request, f"NAV 已刪除；{stale_count} 份定稿報告需要重新產生。")
    else:
        messages.success(request, "NAV 已刪除。")
    return_year = request.POST.get("return_year", "")
    suffix = f"?year={return_year}" if return_year.isdigit() else ""
    return redirect(f"{reverse('simple-entry', args=[share_class.pk])}{suffix}")


@login_required
def bulk_import(request, pk):
    share_class = get_object_or_404(ShareClass, pk=pk)
    preview_rows = None
    token = None
    form = BulkImportForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and request.POST.get("action") == "preview" and form.is_valid():
        try:
            rows = parse_uploaded_nav(form.cleaned_data["file"], form.cleaned_data["file"].name)
            preview_rows = rows
            token = signing.dumps([row.serializable() for row in rows], salt="nav-import")
        except ImportValidationError as exc:
            form.add_error("file", str(exc))
    if request.method == "POST" and request.POST.get("action") == "confirm":
        try:
            payload = signing.loads(request.POST["token"], salt="nav-import", max_age=3600)
            rows = [
                ImportRow(
                    valuation_month=date.fromisoformat(row["valuation_month"]),
                    valuation_date=date.fromisoformat(row["valuation_date"]),
                    nav_per_share=Decimal(row["nav_per_share"]),
                    status=row["status"],
                    note=row["note"],
                    raw_source_date=row["raw_source_date"],
                    source_sheet=row["source_sheet"],
                    source_cell=row["source_cell"],
                    warnings=row["warnings"],
                )
                for row in payload
            ]
            result = import_rows(
                share_class=share_class,
                rows=rows,
                user=request.user,
                commit=True,
                acknowledge_first_period=True,
            )
            AuditLog.objects.create(
                actor=request.user,
                entity_type="ShareClass",
                entity_id=str(share_class.pk),
                action="BULK_NAV_IMPORT",
                after_json=result,
            )
            messages.success(request, f"已匯入 {result['created']} 筆 NAV 紀錄。")
            return redirect("nav-history", pk=share_class.pk)
        except (KeyError, signing.BadSignature, ImportValidationError) as exc:
            messages.error(request, f"確認匯入失敗：{exc}")
    return render(
        request,
        "navapp/bulk_import.html",
        {"form": form, "share_class": share_class, "preview_rows": preview_rows, "token": token},
    )


@login_required
def report_create(request):
    if request.method == "POST":
        form = ReportCreateForm(request.POST)
        if form.is_valid():
            share_class = form.cleaned_data["share_class"]
            year = form.cleaned_data["year"]
            report_type = form.cleaned_data["report_type"]
            report_date = form.cleaned_data["report_date"]
            existing = (
                QuarterlyReport.objects.filter(
                    share_class=share_class,
                    report_type=report_type,
                    report_date=report_date,
                )
                .order_by("-version")
                .first()
            )
            if existing:
                return redirect(f"{reverse('report-history')}?report={existing.pk}")
            report = QuarterlyReport(
                fund=share_class.fund,
                share_class=share_class,
                report_type=report_type,
                year=year,
                report_month=form.cleaned_data["month"],
                quarter=form.cleaned_data["quarter"],
                version=1,
                report_date=report_date,
                commentary_date=report_date,
                created_by=request.user,
            )
            portfolio_manager = share_class.fund.parties.filter(
                party_type="PORTFOLIO_MANAGER"
            ).first()
            if portfolio_manager:
                report.commentary_author = portfolio_manager.value
            report.full_clean()
            report.save()
            return redirect(f"{reverse('report-history')}?report={report.pk}")
        return _render_report_history(request, report_create_form=form)
    else:
        form = ReportCreateForm()
    return render(request, "navapp/generic_form.html", {"form": form, "title": "選擇報告期間"})


def _report_snapshot_for_display(report: QuarterlyReport) -> dict[str, object]:
    if (
        report.status in {QuarterlyReport.Status.FINAL, QuarterlyReport.Status.STALE}
        and report.snapshot
    ):
        return report.snapshot
    return build_current_snapshot(report)


@login_required
def report_review(request, pk):
    report = get_object_or_404(
        QuarterlyReport.objects.select_related("fund", "share_class").prefetch_related(
            Prefetch("files", queryset=GeneratedFile.objects.all())
        ),
        pk=pk,
    )
    calculation = None
    validation_issues = []
    try:
        if (
            report.status in {QuarterlyReport.Status.FINAL, QuarterlyReport.Status.STALE}
            and report.snapshot
        ):
            calculation = report.snapshot["calculation"]
        else:
            calculation = calculate_for_report(report)
    except CalculationValidationError as exc:
        validation_issues = exc.issues
    if (
        report.status in {QuarterlyReport.Status.FINAL, QuarterlyReport.Status.STALE}
        and report.snapshot
    ):
        rfr_snapshot = report.snapshot.get("rfr")
        rfr_observations = [
            {
                "position": item["position"],
                "observation_date": item["date"],
                "value_percent": item["value_percent"],
            }
            for item in (rfr_snapshot or {}).get("observations", [])
        ]
    else:
        try:
            rfr_snapshot = report.rfr_snapshot
            rfr_observations = rfr_snapshot.observations.all()
        except ObjectDoesNotExist:
            rfr_snapshot = None
            rfr_observations = []
    return render(
        request,
        "navapp/report_review.html",
        {
            "report": report,
            "calculation": calculation,
            "validation_issues": validation_issues,
            "rfr_snapshot": rfr_snapshot,
            "rfr_observations": rfr_observations,
            "manual_rfr_form": ManualRFRForm(),
        },
    )


@login_required
@require_POST
def report_refresh_rfr(request, pk):
    report = get_object_or_404(QuarterlyReport, pk=pk)
    try:
        refresh_report_rfr(report)
        messages.success(request, "無風險利率觀察值已更新。")
    except (RFRProviderError, RFRValidationError) as exc:
        messages.error(request, str(exc))
    return redirect("report-review", pk=pk)


@login_required
@require_POST
def report_manual_rfr(request, pk):
    report = get_object_or_404(QuarterlyReport, pk=pk)
    form = ManualRFRForm(request.POST)
    if form.is_valid():
        try:
            snapshot = set_manual_snapshot(
                report,
                form.cleaned_data["value_percent"],
                form.cleaned_data["reason"],
                request.user,
            )
            AuditLog.objects.create(
                actor=request.user,
                entity_type="QuarterlyReport",
                entity_id=str(report.pk),
                action="MANUAL_RFR_OVERRIDE",
                after_json={"annual_value_decimal": str(snapshot.annual_value_decimal)},
                reason=snapshot.override_reason,
            )
            messages.warning(request, "已記錄手動無風險利率覆寫。")
        except RFRValidationError as exc:
            messages.error(request, str(exc))
    else:
        messages.error(request, "必須填寫手動無風險利率及覆寫原因。")
    return redirect("report-review", pk=pk)


@login_required
def report_commentary(request, pk):
    report = get_object_or_404(QuarterlyReport, pk=pk)
    if report.status in {QuarterlyReport.Status.FINAL, QuarterlyReport.Status.STALE}:
        messages.error(request, "已定稿報告的評論不可修改。")
        return redirect("report-review", pk=pk)
    if request.method == "POST":
        form = CommentaryForm(request.POST, instance=report)
        if form.is_valid():
            form.save()
            messages.success(request, "基金經理評論已儲存。")
            return redirect("report-preview", pk=pk)
    else:
        form = CommentaryForm(instance=report)
    return render(
        request,
        "navapp/commentary_form.html",
        {"form": form, "report": report},
    )


@login_required
def report_preview(request, pk):
    report = get_object_or_404(QuarterlyReport, pk=pk)
    try:
        snapshot = _report_snapshot_for_display(report)
        error = ""
    except CalculationValidationError as exc:
        snapshot = None
        error = "; ".join(exc.issues)
    commentary_html = mark_safe(render_safe_html(report.commentary_markdown))
    return render(
        request,
        "navapp/report_preview.html",
        {
            "report": report,
            "snapshot": snapshot,
            "error": error,
            "commentary_html": commentary_html,
        },
    )


@login_required
@require_GET
def report_chart(request, pk):
    report = get_object_or_404(QuarterlyReport, pk=pk)
    try:
        snapshot = _report_snapshot_for_display(report)
    except CalculationValidationError as exc:
        return HttpResponse("; ".join(exc.issues), status=400, content_type="text/plain")
    with tempfile.TemporaryDirectory(prefix="nav-preview-") as temp_dir:
        chart_path = Path(temp_dir) / "nav-chart.png"
        generate_nav_chart(snapshot, chart_path)
        response = HttpResponse(chart_path.read_bytes(), content_type="image/png")
    response["Cache-Control"] = "private, no-store"
    return response


def _report_history_context(
    selected_report: str = "",
    bound_commentary_form: ReportHistoryCommentaryForm | None = None,
    report_create_form: ReportCreateForm | None = None,
) -> dict[str, object]:
    all_reports = list(
        QuarterlyReport.objects.select_related("fund", "share_class").prefetch_related("files")
    )
    selected_item = (
        next((item for item in all_reports if item.pk == int(selected_report)), None)
        if selected_report.isdigit()
        else None
    )
    reports = []
    seen_periods = set()
    for item in all_reports:
        period_key = (item.share_class_id, item.report_type, item.report_date)
        if period_key in seen_periods:
            continue
        seen_periods.add(period_key)
        reports.append(item)
    completed_month = latest_completed_month()
    for item in reports:
        item.simple_period_complete = item.report_date <= completed_month
        if item.status not in {QuarterlyReport.Status.FINAL, QuarterlyReport.Status.STALE}:
            if bound_commentary_form and bound_commentary_form.instance.pk == item.pk:
                item.commentary_form = bound_commentary_form
            else:
                item.commentary_form = ReportHistoryCommentaryForm(
                    instance=item,
                    auto_id=f"id_report_{item.pk}_%s",
                )
    if selected_item:
        selected_key = (
            selected_item.share_class_id,
            selected_item.report_type,
            selected_item.report_date,
        )
        active_report = next(
            (
                item
                for item in reports
                if (item.share_class_id, item.report_type, item.report_date) == selected_key
            ),
            None,
        )
    else:
        active_report = reports[0] if reports else None
    period_initial = {}
    if active_report:
        period_initial = {
            "share_class": active_report.share_class_id,
            "report_type": active_report.report_type,
            "year": active_report.year,
            "month": active_report.report_month,
        }
    return {
        "reports": [active_report] if active_report else [],
        "selected_report": str(active_report.pk) if active_report else "",
        "report": active_report,
        "period_form": report_create_form or ReportCreateForm(initial=period_initial),
    }


def _render_report_history(
    request,
    selected_report: str = "",
    bound_commentary_form: ReportHistoryCommentaryForm | None = None,
    report_create_form: ReportCreateForm | None = None,
):
    return render(
        request,
        "navapp/report_history.html",
        _report_history_context(selected_report, bound_commentary_form, report_create_form),
    )


@login_required
@require_POST
def report_generate(request, pk):
    report = get_object_or_404(QuarterlyReport, pk=pk)
    if request.POST.get("inline_commentary") == "1":
        if report.status in {QuarterlyReport.Status.FINAL, QuarterlyReport.Status.STALE}:
            messages.error(request, "已定稿報告的評論不可修改。")
            return redirect(f"{reverse('report-history')}?report={report.pk}")
        commentary_form = ReportHistoryCommentaryForm(
            request.POST,
            instance=report,
            auto_id=f"id_report_{report.pk}_%s",
        )
        if not commentary_form.is_valid():
            return _render_report_history(request, str(report.pk), commentary_form)
        before_commentary = report.commentary_markdown
        with transaction.atomic():
            report = commentary_form.save(commit=False)
            if not report.commentary_author:
                report.commentary_author = _portfolio_manager_name(report.share_class)
            if not report.commentary_date:
                report.commentary_date = report.report_date
            report.snapshot = {}
            report.generation_error = ""
            report.status = QuarterlyReport.Status.DRAFT
            report.save()
            report.files.all().delete()
            AuditLog.objects.create(
                actor=request.user,
                entity_type="QuarterlyReport",
                entity_id=str(report.pk),
                action="UPDATE_COMMENTARY",
                before_json={"commentary_markdown": before_commentary},
                after_json={
                    "commentary_markdown": report.commentary_markdown,
                },
            )
        if request.POST.get("action") == "save_commentary":
            messages.success(request, "基金經理評論已儲存；所選期間 NAV 齊全後即可產生報告。")
            return redirect(f"{reverse('report-history')}?report={report.pk}")
    try:
        calculate_for_report(report)
        try:
            rfr_snapshot = report.rfr_snapshot
        except ObjectDoesNotExist:
            rfr_snapshot = None
        if rfr_snapshot is None or not rfr_snapshot.is_manual:
            refresh_report_rfr(report)
        generate_report_files(report, request.user)
        messages.success(request, "Word 及 PDF 報告已產生。")
    except (
        ReportGenerationError,
        CalculationValidationError,
        RFRProviderError,
        RFRValidationError,
    ) as exc:
        messages.error(request, f"產生報告失敗：{exc}")
    return redirect(f"{reverse('report-history')}?report={report.pk}")


@login_required
@require_POST
def report_finalize(request, pk):
    report = get_object_or_404(QuarterlyReport, pk=pk)
    try:
        finalize_report(report, request.user)
        messages.success(request, "報告已定稿，快照及檔案現已鎖定，不可修改。")
    except ValidationError as exc:
        messages.error(request, "無法定稿：" + "; ".join(exc.messages))
    return redirect("report-review", pk=pk)


@login_required
def report_history(request):
    selected_report = request.GET.get("report", "")
    return _render_report_history(request, selected_report)


@login_required
def report_download(request, pk, file_type):
    generated = get_object_or_404(
        GeneratedFile.objects.select_related("report"),
        report_id=pk,
        file_type=file_type.upper(),
    )
    try:
        path = generated.absolute_path
    except ValueError as exc:
        raise Http404 from exc
    if not path.is_file():
        raise Http404
    content_type = (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        if generated.file_type == GeneratedFile.FileType.DOCX
        else "application/pdf"
    )
    return FileResponse(
        path.open("rb"),
        as_attachment=True,
        filename=f"{generated.report.share_class.code}-{generated.report.label}.{file_type.lower()}",
        content_type=content_type,
    )


@login_required
def organization_settings(request):
    instance = OrganizationSettings.load()
    if request.method == "POST":
        form = OrganizationSettingsForm(request.POST, request.FILES, instance=instance)
        if form.is_valid():
            changed_fields = list(form.changed_data)
            with transaction.atomic():
                organization = form.save()
                AuditLog.objects.create(
                    actor=request.user,
                    entity_type="OrganizationSettings",
                    entity_id=str(organization.pk),
                    action="UPDATE",
                    after_json={"changed_fields": changed_fields},
                )
                if changed_fields:
                    stale_count = mark_organization_reports_stale(
                        organization,
                        request.user,
                        "機構設定已變更：" + "、".join(changed_fields),
                    )
                    if stale_count:
                        messages.warning(
                            request,
                            f"已有 {stale_count} 份已定稿報告被標示為需要重新產生。",
                        )
            messages.success(request, "機構設定已儲存。")
            return redirect("organization-settings")
    else:
        form = OrganizationSettingsForm(instance=instance)
    return render(
        request,
        "navapp/generic_form.html",
        {"form": form, "title": "機構設定"},
    )


@login_required
def audit_log(request):
    return render(
        request,
        "navapp/audit_log.html",
        {"logs": AuditLog.objects.select_related("actor")[:500]},
    )
