from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.urls import get_script_prefix, reverse, set_script_prefix

from navapp.models import AuditLog, Fund, NAVRecord, QuarterlyReport, ShareClass
from navapp.services import reports
from navapp.services.calculations import CalculationValidationError
from navapp.services.imports import ImportValidationError, parse_legacy_xsq, validate_sequence
from navapp.templatetags.nav_tags import choice_label, zh_date, zh_text


def test_nav_subpath_reverse_and_cookie_settings(settings):
    previous_prefix = get_script_prefix()
    try:
        set_script_prefix("/nav/")
        assert reverse("dashboard") == "/nav/"
        assert reverse("login") == "/nav/accounts/login/"
        assert reverse("report-history") == "/nav/reports/"
    finally:
        set_script_prefix(previous_prefix)
    assert settings.SESSION_COOKIE_NAME == "nav_sessionid"
    assert settings.CSRF_COOKIE_NAME == "nav_csrftoken"


@pytest.mark.django_db
def test_legacy_import_is_complete_normalized_and_idempotent(django_user_model):
    rows = parse_legacy_xsq(Path("reference/xsq_nav_history.xlsx"))
    assert len(rows) == 45
    assert rows[0].valuation_month == date(2022, 7, 31)
    assert rows[-1].valuation_month == date(2026, 3, 31)
    assert rows[-1].source_cell == "E47"
    assert rows[0].warnings


def test_import_sequence_rejects_duplicate_and_missing_months():
    rows = parse_legacy_xsq(Path("reference/xsq_nav_history.xlsx"))
    with pytest.raises(ImportValidationError, match="重複月份"):
        validate_sequence([rows[0], rows[0]])
    with pytest.raises(ImportValidationError, match="缺少月份"):
        validate_sequence([rows[0], rows[2]])


@pytest.mark.django_db
def test_required_fund_fields_and_duplicate_nav_are_rejected():
    invalid = Fund(short_code="invalid")
    with pytest.raises(ValidationError):
        invalid.full_clean()
    fund = Fund.objects.create(
        legal_name="One",
        display_name="One",
        short_code="one",
        structure="LPF",
        domicile="Hong Kong",
        investment_objective="Objective",
    )
    share = ShareClass.objects.create(
        fund=fund,
        name="A",
        code="a",
        inception_date=date(2024, 1, 1),
        inception_nav=Decimal("100"),
        currency="USD",
    )
    NAVRecord.objects.create(
        share_class=share,
        valuation_month=date(2024, 1, 31),
        valuation_date=date(2024, 1, 31),
        nav_per_share=Decimal("101"),
    )
    duplicate = NAVRecord(
        share_class=share,
        valuation_month=date(2024, 1, 31),
        valuation_date=date(2024, 1, 31),
        nav_per_share=Decimal("102"),
    )
    with pytest.raises(ValidationError):
        duplicate.full_clean()
    non_positive = NAVRecord(
        share_class=share,
        valuation_month=date(2024, 2, 29),
        valuation_date=date(2024, 2, 29),
        nav_per_share=Decimal("0"),
    )
    with pytest.raises(ValidationError):
        non_positive.full_clean()


@pytest.mark.django_db
def test_anonymous_pages_and_downloads_require_login(client, settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    assert client.get(reverse("dashboard")).status_code == 302
    assert client.get(reverse("report-history")).status_code == 302
    assert client.get("/reports/999/download/pdf/").status_code == 302
    assert client.get(reverse("healthz")).status_code == 200


@pytest.mark.django_db
def test_user_interface_uses_traditional_chinese(client, django_user_model):
    login = client.get(reverse("login"))
    assert '<html lang="zh-Hant">' in login.content.decode()
    assert "登入" in login.content.decode()
    assert "內部系統" in login.content.decode()

    user = django_user_model.objects.create_user("zh-user", password="safe-password")
    client.force_login(user)
    dashboard = client.get(reverse("dashboard")).content.decode()
    assert "選擇基金" in dashboard
    assert "輸入 NAV 及基金經理評論" in dashboard
    assert "基金經理評論" in dashboard
    assert "Dashboard" not in dashboard
    assert "Select Fund" not in dashboard


def test_dynamic_user_interface_text_uses_traditional_chinese():
    assert choice_label("GENERATE_DOCX") == "產生 Word 報告"
    assert (
        zh_text("Quarter-end NAV / previous quarter-end NAV - 1")
        == "季度末 NAV ÷ 上一季度末 NAV − 1"
    )
    assert "工作簿" in zh_text("Intentional correction from the workbook fixed-cell result.")
    assert zh_text("Report end must be a calendar quarter end.") == "報告截止日必須為日曆季度末日。"
    assert zh_date("2026-03-31") == "2026 年 3 月 31 日"
    assert zh_text("Fund settings changed: short_code") == "基金設定已變更： short_code"


@pytest.mark.django_db
def test_simple_three_step_workflow_defaults_saves_and_prevents_duplicates(
    client, django_user_model, monkeypatch
):
    monkeypatch.setattr("navapp.forms.timezone.localdate", lambda: date(2026, 7, 20))
    user = django_user_model.objects.create_user("simple-user", password="safe-password")
    client.force_login(user)
    fund = Fund.objects.create(
        legal_name="Simple Fund LPF",
        display_name="Simple Fund",
        short_code="simple-fund",
        structure="LPF",
        domicile="Hong Kong",
        investment_objective="Simple objective",
    )
    share = ShareClass.objects.create(
        fund=fund,
        name="Class A",
        code="simple-a",
        inception_date=date(2024, 1, 1),
        inception_nav=Decimal("100"),
        currency="USD",
    )

    dashboard = client.get(reverse("dashboard"))
    dashboard_text = dashboard.content.decode()
    assert reverse("simple-entry", args=[share.pk]) in dashboard_text
    assert "選擇基金" in dashboard_text
    assert "輸入 NAV 及基金經理評論" in dashboard_text
    assert "產生報告" in dashboard_text
    assert "檢視績效" not in dashboard_text

    entry = client.get(reverse("simple-entry", args=[share.pk]))
    assert entry.status_code == 200
    assert entry.context["form"]["year"].value() == 2026
    assert entry.context["form"]["month"].value() == 6
    assert "系統日期：2026 年 7 月 20 日" in entry.content.decode()
    assert "預設為最近已完成月份：2026 年 6 月" in entry.content.decode()

    future = client.post(
        reverse("simple-entry", args=[share.pk]),
        {
            "year": "2026",
            "month": "7",
            "nav_per_share": "105",
            "commentary_markdown": "未完成月份不可輸入。",
        },
    )
    assert future.status_code == 200
    assert "估值月份不得晚於最近已完成月份" in future.content.decode()
    assert not NAVRecord.objects.filter(share_class=share).exists()

    response = client.post(
        reverse("simple-entry", args=[share.pk]),
        {
            "year": "2024",
            "month": "3",
            "nav_per_share": "105.123456",
            "commentary_markdown": "本季維持嚴謹的風險管理。",
        },
    )
    assert response.status_code == 302
    nav = NAVRecord.objects.get(share_class=share)
    assert nav.valuation_month == date(2024, 3, 31)
    assert nav.valuation_date == date(2024, 3, 31)
    assert nav.nav_per_share == Decimal("105.123456")
    report = QuarterlyReport.objects.get(share_class=share)
    assert report.year == 2024
    assert report.quarter == 1
    assert report.report_date == date(2024, 3, 31)
    assert report.commentary_markdown == "本季維持嚴謹的風險管理。"
    assert response.url == f"{reverse('report-history')}?report={report.pk}"
    assert AuditLog.objects.filter(action="SIMPLE_ENTRY", entity_id=str(report.pk)).exists()
    history = client.get(response.url)
    assert history.status_code == 200
    assert "系統會自動取得無風險利率" in history.content.decode()
    assert reverse("report-generate", args=[report.pk]) in history.content.decode()
    assert reverse("simple-entry", args=[share.pk]) in history.content.decode()

    duplicate = client.post(
        reverse("simple-entry", args=[share.pk]),
        {
            "year": "2024",
            "month": "3",
            "nav_per_share": "106",
            "commentary_markdown": "不可覆蓋原有 NAV。",
        },
    )
    assert duplicate.status_code == 200
    assert "該月份已有 NAV 紀錄" in duplicate.content.decode()
    assert NAVRecord.objects.filter(share_class=share).count() == 1

    abnormal_payload = {
        "year": "2024",
        "month": "4",
        "nav_per_share": "200",
        "commentary_markdown": "四月市場回顧。",
    }
    abnormal = client.post(reverse("simple-entry", args=[share.pk]), abnormal_payload)
    assert abnormal.status_code == 200
    assert "請檢查數值；如確認正確，再按一次儲存" in abnormal.content.decode()
    assert NAVRecord.objects.filter(share_class=share).count() == 1
    confirmed = client.post(
        reverse("simple-entry", args=[share.pk]),
        abnormal_payload | {"confirm_large_change": "1"},
    )
    assert confirmed.status_code == 302
    assert confirmed.url == reverse("dashboard")
    assert NAVRecord.objects.filter(share_class=share).count() == 2
    assert NAVRecord.objects.get(valuation_month=date(2024, 4, 30)).change_acknowledged is True
    q2_report = QuarterlyReport.objects.get(share_class=share, year=2024, quarter=2)
    assert q2_report.commentary_date == date(2024, 4, 30)


@pytest.mark.django_db
def test_simple_generate_refreshes_rfr_and_returns_to_report_history(
    client, django_user_model, monkeypatch
):
    user = django_user_model.objects.create_user("generate-user", password="safe-password")
    client.force_login(user)
    fund = Fund.objects.create(
        legal_name="Generate Fund LPF",
        display_name="Generate Fund",
        short_code="generate-fund",
        structure="LPF",
        domicile="Hong Kong",
        investment_objective="Generate objective",
    )
    share = ShareClass.objects.create(
        fund=fund,
        name="Class A",
        code="generate-a",
        inception_date=date(2024, 1, 1),
        inception_nav=Decimal("100"),
        currency="USD",
    )
    report = QuarterlyReport.objects.create(
        fund=fund,
        share_class=share,
        year=2024,
        quarter=1,
        report_date=date(2024, 3, 31),
        commentary_markdown="Commentary",
        created_by=user,
    )
    calls = []
    monkeypatch.setattr(
        "navapp.views.calculate_for_report", lambda item: calls.append(("calculate", item.pk))
    )
    monkeypatch.setattr("navapp.views.refresh_report_rfr", lambda item: calls.append(item.pk))
    monkeypatch.setattr(
        "navapp.views.generate_report_files", lambda item, actor: calls.append((item.pk, actor.pk))
    )

    response = client.post(reverse("report-generate", args=[report.pk]))
    assert response.status_code == 302
    assert response.url == f"{reverse('report-history')}?report={report.pk}"
    assert calls == [("calculate", report.pk), report.pk, (report.pk, user.pk)]

    calls.clear()

    def reject_incomplete_quarter(item):
        calls.append(("calculate", item.pk))
        raise CalculationValidationError(["缺少估值月份：2024-02"])

    monkeypatch.setattr("navapp.views.calculate_for_report", reject_incomplete_quarter)
    incomplete = client.post(reverse("report-generate", args=[report.pk]), follow=True)
    assert incomplete.status_code == 200
    assert "缺少估值月份：2024-02" in incomplete.content.decode()
    assert calls == [("calculate", report.pk)]


@pytest.mark.django_db
def test_full_authenticated_web_workflow_and_fund_isolation(
    client, settings, tmp_path, monkeypatch
):
    settings.MEDIA_ROOT = tmp_path / "media"
    user = get_user_model().objects.create_user("operator", password="safe-password")
    client.force_login(user)
    fund_payload = {
        "legal_name": "Web Fund LPF",
        "display_name": "Web Fund",
        "short_code": "web-fund",
        "structure": "LPF",
        "domicile": "Hong Kong",
        "year_end_month": "12",
        "year_end_day": "31",
        "report_language": "en",
        "is_active": "on",
        "investment_objective": "Web-created objective",
        "use_org_professional_statement": "on",
        "use_org_date_statement": "on",
        "use_org_disclaimer": "on",
        "strategies-TOTAL_FORMS": "1",
        "strategies-INITIAL_FORMS": "0",
        "strategies-MIN_NUM_FORMS": "1",
        "strategies-MAX_NUM_FORMS": "1000",
        "strategies-0-text": "Disciplined strategy",
        "strategies-0-sort_order": "0",
    }
    for prefix in ("parties", "terms", "contacts"):
        fund_payload |= {
            f"{prefix}-TOTAL_FORMS": "0",
            f"{prefix}-INITIAL_FORMS": "0",
            f"{prefix}-MIN_NUM_FORMS": "0",
            f"{prefix}-MAX_NUM_FORMS": "1000",
        }
    response = client.post(reverse("fund-create"), fund_payload)
    assert response.status_code == 302
    fund = Fund.objects.get(short_code="web-fund")
    response = client.post(
        reverse("share-class-create", args=[fund.pk]),
        {
            "name": "Class A",
            "code": "a",
            "inception_date": "2024-01-01",
            "inception_nav": "100",
            "currency": "USD",
            "return_basis": "NET",
            "is_active": "on",
            "display_in_quarterly_report": "on",
        },
    )
    assert response.status_code == 302
    share = ShareClass.objects.get(fund=fund, code="a")
    for month, day, nav in ((1, 31, "101"), (2, 29, "102"), (3, 31, "103")):
        response = client.post(
            reverse("nav-create", args=[share.pk]),
            {
                "valuation_month": f"2024-{month:02d}-{day}",
                "valuation_date": f"2024-{month:02d}-{day}",
                "nav_per_share": nav,
                "status": "OFFICIAL",
                "note": "",
            },
        )
        assert response.status_code == 302
    duplicate_response = client.post(
        reverse("nav-create", args=[share.pk]),
        {
            "valuation_month": "2024-01-31",
            "valuation_date": "2024-01-31",
            "nav_per_share": "104",
            "status": "OFFICIAL",
            "note": "duplicate attempt",
        },
    )
    assert duplicate_response.status_code == 200
    assert "已存在一筆有效 NAV 紀錄" in duplicate_response.content.decode()
    response = client.post(
        reverse("report-create"), {"share_class": share.pk, "year": "2024", "quarter": "1"}
    )
    assert response.status_code == 302
    report = QuarterlyReport.objects.get(share_class=share)
    response = client.post(
        reverse("report-manual-rfr", args=[report.pk]),
        {"value_percent": "4.25", "reason": "Approved manual fixture"},
    )
    assert response.status_code == 302
    response = client.post(
        reverse("report-commentary", args=[report.pk]),
        {
            "commentary_title": "Q1 review",
            "commentary_markdown": "Performance remained within the risk budget.",
            "commentary_author": "Operator",
            "commentary_date": "2024-03-31",
        },
    )
    assert response.status_code == 302

    def fake_convert(docx_path, output_dir):
        pdf = output_dir / f"{docx_path.stem}.pdf"
        pdf.write_bytes(b"%PDF-1.4\n% web test\n")
        return pdf

    monkeypatch.setattr(reports, "convert_docx_to_pdf", fake_convert)
    response = client.post(reverse("report-generate", args=[report.pk]))
    assert response.status_code == 302
    report.refresh_from_db()
    assert report.status == QuarterlyReport.Status.READY
    assert report.files.count() == 2
    assert client.get(reverse("report-preview", args=[report.pk])).status_code == 200
    assert client.get(reverse("report-chart", args=[report.pk])).status_code == 200
    assert client.get(reverse("report-download", args=[report.pk, "pdf"])).status_code == 200

    original_commentary = report.commentary_markdown
    response = client.post(reverse("report-finalize", args=[report.pk]))
    assert response.status_code == 302
    report.refresh_from_db()
    assert report.status == QuarterlyReport.Status.FINAL
    assert report.finalized_at is not None

    response = client.post(
        reverse("report-commentary", args=[report.pk]),
        {
            "commentary_title": "Should not persist",
            "commentary_markdown": "Finalized content must remain immutable.",
            "commentary_author": "Operator",
            "commentary_date": "2024-03-31",
        },
    )
    assert response.status_code == 302
    report.refresh_from_db()
    assert report.commentary_markdown == original_commentary

    february = NAVRecord.objects.get(share_class=share, valuation_month=date(2024, 2, 29))
    response = client.post(
        reverse("nav-edit", args=[share.pk, february.pk]),
        {
            "valuation_month": "2024-02-29",
            "valuation_date": "2024-02-29",
            "nav_per_share": "102.5",
            "status": "OFFICIAL",
            "note": "Audited correction",
            "reason": "Administrator-approved source correction",
        },
    )
    assert response.status_code == 302
    report.refresh_from_db()
    assert report.status == QuarterlyReport.Status.STALE
    assert AuditLog.objects.filter(entity_type="NAVRecord", action="MARK_REPORTS_STALE").exists()
    preview = client.get(reverse("report-preview", args=[report.pk]))
    review = client.get(reverse("report-review", args=[report.pk]))
    assert preview.context["snapshot"] == report.snapshot
    assert review.context["calculation"] == report.snapshot["calculation"]
    assert client.get(reverse("report-chart", args=[report.pk])).status_code == 200

    other_fund = Fund.objects.create(
        legal_name="Other",
        display_name="Other",
        short_code="other",
        structure="LPF",
        domicile="Hong Kong",
        investment_objective="Other objective",
    )
    ShareClass.objects.create(
        fund=other_fund,
        name="Other Class",
        code="other",
        inception_date=date(2024, 1, 1),
        inception_nav=Decimal("200"),
        currency="USD",
    )
    assert report.snapshot["identity"]["fund_id"] == fund.pk
    assert AuditLog.objects.filter(entity_type="QuarterlyReport", action="GENERATE").exists()

    response = client.post(reverse("logout"))
    assert response.status_code == 302
    assert client.get(reverse("dashboard")).status_code == 302
