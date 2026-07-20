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
from navapp.services.imports import ImportValidationError, parse_legacy_xsq, validate_sequence


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
    with pytest.raises(ImportValidationError, match="Duplicate"):
        validate_sequence([rows[0], rows[0]])
    with pytest.raises(ImportValidationError, match="Missing month"):
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
    assert b"active NAV record already exists" in duplicate_response.content
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
