from __future__ import annotations

import tempfile
from datetime import date
from decimal import Decimal
from pathlib import Path

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core import signing
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.db import IntegrityError, connections, transaction
from django.db.models import Max, Prefetch
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
    ManualRFRForm,
    NAVEditReasonForm,
    NAVRecordForm,
    OrganizationSettingsForm,
    PartyFormSet,
    ReportCreateForm,
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
        latest_report = share_class.reports.order_by("-year", "-quarter", "-version").first()
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
    report = QuarterlyReport(
        fund=share_class.fund,
        share_class=share_class,
        year=year,
        quarter=quarter,
        version=version,
        report_date=month_end(date(year, quarter * 3, 1)),
        commentary_author=_portfolio_manager_name(share_class),
        created_by=user,
    )
    report.full_clean()
    report.save()
    return report, True


@login_required
def simple_entry(request, share_class_pk):
    share_class = get_object_or_404(
        ShareClass.objects.select_related("fund"),
        pk=share_class_pk,
        is_active=True,
        fund__is_active=True,
    )
    form = SimpleEntryForm(request.POST or None, share_class=share_class)
    if request.method == "POST" and form.is_valid():
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
            report.commentary_markdown = form.cleaned_data["commentary_markdown"]
            report.commentary_date = valuation_month
            report.status = QuarterlyReport.Status.DRAFT
            report.snapshot = {}
            report.generation_error = ""
            report.save(
                update_fields=[
                    "commentary_markdown",
                    "commentary_date",
                    "status",
                    "snapshot",
                    "generation_error",
                    "updated_at",
                ]
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
        if valuation_month.month not in {3, 6, 9, 12}:
            messages.success(
                request,
                f"NAV 及基金經理評論已儲存；本季報告會在 {report.report_date.month} 月 NAV 齊全後產生。",
            )
            return redirect("dashboard")
        messages.success(request, "NAV 及基金經理評論已儲存，現在可以產生報告。")
        return redirect(f"{reverse('report-history')}?report={report.pk}")
    return render(
        request,
        "navapp/simple_entry.html",
        {
            "form": form,
            "share_class": share_class,
            "system_date": form.system_date,
            "default_period": form.default_period,
        },
    )


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
def nav_edit(request, share_class_pk, pk=None):
    share_class = get_object_or_404(ShareClass, pk=share_class_pk)
    instance = (
        get_object_or_404(NAVRecord, pk=pk, share_class=share_class)
        if pk
        else NAVRecord(share_class=share_class)
    )
    before = _nav_json(instance) if pk else {}
    if request.method == "POST":
        form = NAVRecordForm(request.POST, instance=instance, share_class=share_class)
        reason_form = NAVEditReasonForm(request.POST) if pk else None
        if form.is_valid() and (reason_form is None or reason_form.is_valid()):
            item = form.save(commit=False)
            item.updated_by = request.user
            if not pk:
                item.created_by = request.user
            else:
                item.revision += 1
            try:
                item.full_clean()
                with transaction.atomic():
                    item.save()
                    reason = reason_form.cleaned_data["reason"] if reason_form else ""
                    AuditLog.objects.create(
                        actor=request.user,
                        entity_type="NAVRecord",
                        entity_id=str(item.pk),
                        action="UPDATE" if pk else "CREATE",
                        before_json=before,
                        after_json=_nav_json(item),
                        reason=reason,
                    )
                    if pk:
                        stale_count = mark_affected_reports_stale(item, request.user, reason)
                        if stale_count:
                            messages.warning(
                                request,
                                f"已有 {stale_count} 份已定稿報告被標示為需要重新產生。",
                            )
            except ValidationError as exc:
                detail = "; ".join(exc.messages)
                if "unique_active_nav_month" in detail:
                    detail = "此股份類別在該月份已存在一筆有效 NAV 紀錄。"
                form.add_error(None, detail)
            except IntegrityError:
                form.add_error(
                    None,
                    "此股份類別在該月份已存在一筆有效 NAV 紀錄。",
                )
            else:
                messages.success(request, "NAV 紀錄已儲存。")
                return redirect("nav-history", pk=share_class.pk)
    else:
        form = NAVRecordForm(instance=instance, share_class=share_class)
        reason_form = NAVEditReasonForm() if pk else None
    return render(
        request,
        "navapp/nav_form.html",
        {"form": form, "reason_form": reason_form, "share_class": share_class, "editing": bool(pk)},
    )


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
            quarter = form.cleaned_data["quarter"]
            version = (
                QuarterlyReport.objects.filter(
                    share_class=share_class, year=year, quarter=quarter
                ).aggregate(Max("version"))["version__max"]
                or 0
            ) + 1
            report = QuarterlyReport(
                fund=share_class.fund,
                share_class=share_class,
                year=year,
                quarter=quarter,
                version=version,
                report_date=form.cleaned_data["report_date"],
                commentary_date=form.cleaned_data["report_date"],
                created_by=request.user,
            )
            portfolio_manager = share_class.fund.parties.filter(
                party_type="PORTFOLIO_MANAGER"
            ).first()
            if portfolio_manager:
                report.commentary_author = portfolio_manager.value
            report.full_clean()
            report.save()
            return redirect("report-review", pk=report.pk)
    else:
        form = ReportCreateForm()
    return render(request, "navapp/generic_form.html", {"form": form, "title": "建立季度報告"})


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
        messages.error(request, "已定稿報告的評論不可修改；請建立新版本。")
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


@login_required
@require_POST
def report_generate(request, pk):
    report = get_object_or_404(QuarterlyReport, pk=pk)
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
    reports = list(
        QuarterlyReport.objects.select_related("fund", "share_class").prefetch_related("files")
    )
    completed_month = latest_completed_month()
    for item in reports:
        item.simple_period_complete = item.report_date <= completed_month
    selected_report = request.GET.get("report", "")
    active_report = (
        next((item for item in reports if item.pk == int(selected_report)), None)
        if selected_report.isdigit()
        else None
    )
    return render(
        request,
        "navapp/report_history.html",
        {
            "reports": reports,
            "selected_report": selected_report,
            "report": active_report,
        },
    )


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
