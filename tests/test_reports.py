from __future__ import annotations

import shutil
from datetime import date
from decimal import Decimal
from pathlib import Path
from zipfile import ZipFile

import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from docx import Document

from navapp.models import (
    Fund,
    GeneratedFile,
    NAVRecord,
    OrganizationSettings,
    QuarterlyReport,
    ShareClass,
)
from navapp.services import reports
from navapp.services.reports import (
    ReportGenerationError,
    audit_docx_package,
    build_builtin_docx,
    build_current_snapshot,
    external_excel_relationships,
    finalize_report,
    generate_nav_chart,
    generate_report_files,
    mark_affected_reports_stale,
    mark_fund_reports_stale,
    mark_organization_reports_stale,
    mark_share_class_reports_stale,
    sha256_file,
)
from navapp.services.rfr import set_manual_snapshot


@pytest.fixture
def report_fixture(db, settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path / "media"
    org = OrganizationSettings.load()
    org.default_disclaimer = "Organization disclaimer"
    org.save()
    user = get_user_model().objects.create_user("reporter", password="safe-password")
    fund = Fund.objects.create(
        legal_name="Example Fund LPF",
        display_name="Example Fund",
        short_code="example",
        structure="Limited Partnership Fund",
        domicile="Hong Kong",
        investment_objective="Preserve capital and compound returns.",
        performance_note="Returns are net of applicable fees.",
        use_org_professional_statement=False,
        professional_investor_statement_override="Professional investors only - fund override",
        use_org_disclaimer=False,
        disclaimer_override="Fund-specific legal disclaimer.",
        disclaimer_version_override="FUND-1",
    )
    share = ShareClass.objects.create(
        fund=fund,
        name="Class A",
        code="a",
        inception_date=date(2024, 1, 1),
        inception_nav=Decimal("100"),
        currency="USD",
    )
    records = []
    for month, nav in ((1, "101"), (2, "103"), (3, "105")):
        day = 31 if month in {1, 3} else 29
        records.append(
            NAVRecord(
                share_class=share,
                valuation_month=date(2024, month, day),
                valuation_date=date(2024, month, day),
                nav_per_share=Decimal(nav),
            )
        )
    NAVRecord.objects.bulk_create(records)
    report = QuarterlyReport.objects.create(
        fund=fund,
        share_class=share,
        year=2024,
        quarter=1,
        report_date=date(2024, 3, 31),
        commentary_title="Quarterly review",
        commentary_markdown="**Disciplined execution** remained central.\n\n- Managed risk\n- Preserved liquidity",
        commentary_author="Portfolio Manager",
        commentary_date=date(2024, 3, 31),
        created_by=user,
    )
    set_manual_snapshot(report, Decimal("4.25"), "Approved legacy reconciliation", user)
    return report, user, tmp_path


def _build_docx(report, tmp_path: Path) -> tuple[dict[str, object], Path]:
    snapshot = build_current_snapshot(report)
    chart = tmp_path / "chart.png"
    output = tmp_path / "report.docx"
    generate_nav_chart(snapshot, chart)
    build_builtin_docx(snapshot, chart, output)
    return snapshot, output


@pytest.mark.django_db
def test_docx_package_contains_sections_table_values_chart_and_no_excel_links(report_fixture):
    report, _, tmp_path = report_fixture
    snapshot, output = _build_docx(report, tmp_path)
    document = Document(output)
    text = "\n".join(paragraph.text for paragraph in document.paragraphs)
    assert "Investment Objective" in text
    assert "Manager Commentary" in text
    assert "Fund-specific legal disclaimer" in text
    assert "Professional investors only - fund override" in text
    assert snapshot["calculation"]["quarterly_matrix"]["2024"]["q1"]["display"] == "5.00%"
    assert any(
        "5.00%" in cell.text
        for table in document.tables
        for row in table.rows
        for cell in row.cells
    )
    with ZipFile(output) as package:
        assert any(name.startswith("word/media/") for name in package.namelist())
        assert package.testzip() is None
    assert external_excel_relationships(output) == []
    package_audit = audit_docx_package(output)
    assert package_audit["valid"] is True
    assert package_audit["external_relationships"] == []
    assert package_audit["missing_relationship_targets"] == []
    assert package_audit["embedded_spreadsheets"] == []
    assert len(package_audit["footer_texts"]) == 3


@pytest.mark.django_db
def test_long_commentary_flows_and_snapshot_survives_fund_edit(report_fixture):
    report, _, tmp_path = report_fixture
    report.commentary_markdown = "\n\n".join(
        f"Paragraph {index}: " + ("Long-form portfolio commentary. " * 20) for index in range(1, 35)
    )
    report.save()
    snapshot, output = _build_docx(report, tmp_path)
    assert output.stat().st_size > 10_000
    assert "Paragraph 34" in "\n".join(item.text for item in Document(output).paragraphs)
    report.snapshot = snapshot
    report.save(update_fields=["snapshot", "updated_at"])
    captured = report.snapshot
    report.fund.display_name = "Renamed after capture"
    report.fund.disclaimer_override = "Changed later"
    report.fund.save()
    report.refresh_from_db()
    assert report.snapshot == captured
    assert report.snapshot["identity"]["fund_display_name"] == "Example Fund"


@pytest.mark.django_db
def test_generation_stores_hashes_and_failure_state_persists(report_fixture, monkeypatch):
    report, user, tmp_path = report_fixture

    def fake_convert(docx_path, output_dir):
        pdf = output_dir / f"{docx_path.stem}.pdf"
        pdf.write_bytes(b"%PDF-1.4\n% deterministic test\n")
        return pdf

    monkeypatch.setattr(reports, "convert_docx_to_pdf", fake_convert)
    generated = generate_report_files(report, user)
    report.refresh_from_db()
    assert report.status == QuarterlyReport.Status.READY
    assert {item.file_type for item in generated} == {"DOCX", "PDF"}
    assert all(item.sha256 == sha256_file(item.absolute_path) for item in generated)

    def broken_convert(docx_path, output_dir):
        raise ReportGenerationError("converter deliberately unavailable")

    monkeypatch.setattr(reports, "convert_docx_to_pdf", broken_convert)
    with pytest.raises(ReportGenerationError, match="deliberately unavailable"):
        generate_report_files(report, user)
    report.refresh_from_db()
    assert report.status == QuarterlyReport.Status.GENERATION_FAILED
    assert "deliberately unavailable" in report.generation_error
    assert report.files.filter(file_type=GeneratedFile.FileType.DOCX).exists()


@pytest.mark.django_db
def test_finalized_report_is_immutable_and_nav_edit_marks_it_stale(report_fixture, monkeypatch):
    report, user, _ = report_fixture

    def fake_convert(docx_path, output_dir):
        pdf = output_dir / f"{docx_path.stem}.pdf"
        pdf.write_bytes(b"%PDF-1.4\n% final fixture\n")
        return pdf

    monkeypatch.setattr(reports, "convert_docx_to_pdf", fake_convert)
    generate_report_files(report, user)
    finalize_report(report, user)
    assert report.status == QuarterlyReport.Status.FINAL
    report.commentary_markdown = "Attempted mutation"
    with pytest.raises(ValidationError, match="immutable"):
        report.save()
    report.refresh_from_db()
    report.status = QuarterlyReport.Status.DRAFT
    with pytest.raises(ValidationError, match="only transition"):
        report.save()
    generated = report.files.first()
    generated.sha256 = "0" * 64
    with pytest.raises(ValidationError, match="files are immutable"):
        generated.save()
    rfr = report.rfr_snapshot
    rfr.override_reason = "Attempted mutation"
    with pytest.raises(ValidationError, match="RFR snapshot is immutable"):
        rfr.save()
    record = report.share_class.nav_records.get(valuation_month=date(2024, 2, 29))
    assert mark_affected_reports_stale(record, user, "NAV correction") == 1
    report.refresh_from_db()
    assert report.status == QuarterlyReport.Status.STALE


@pytest.mark.django_db
def test_reportable_fund_change_marks_final_report_stale(report_fixture, monkeypatch):
    report, user, _ = report_fixture

    def fake_convert(docx_path, output_dir):
        pdf = output_dir / f"{docx_path.stem}.pdf"
        pdf.write_bytes(b"%PDF-1.4\n% fund-change fixture\n")
        return pdf

    monkeypatch.setattr(reports, "convert_docx_to_pdf", fake_convert)
    generate_report_files(report, user)
    finalize_report(report, user)
    report.fund.display_name = "Updated display name"
    report.fund.save(update_fields=["display_name", "updated_at"])
    assert mark_fund_reports_stale(report.fund, user, "Fund display name changed") == 1
    report.refresh_from_db()
    assert report.status == QuarterlyReport.Status.STALE
    assert report.snapshot["identity"]["fund_display_name"] == "Example Fund"


@pytest.mark.django_db
def test_reportable_share_class_change_marks_final_report_stale(report_fixture, monkeypatch):
    report, user, _ = report_fixture

    def fake_convert(docx_path, output_dir):
        pdf = output_dir / f"{docx_path.stem}.pdf"
        pdf.write_bytes(b"%PDF-1.4\n% share-change fixture\n")
        return pdf

    monkeypatch.setattr(reports, "convert_docx_to_pdf", fake_convert)
    generate_report_files(report, user)
    finalize_report(report, user)
    report.share_class.name = "Class A Updated"
    report.share_class.save(update_fields=["name", "updated_at"])
    assert mark_share_class_reports_stale(report.share_class, user, "Share-class name changed") == 1
    report.refresh_from_db()
    assert report.status == QuarterlyReport.Status.STALE
    assert report.snapshot["identity"]["share_class_name"] == "Class A"


@pytest.mark.django_db
def test_organization_change_marks_final_report_stale(report_fixture, monkeypatch):
    report, user, _ = report_fixture

    def fake_convert(docx_path, output_dir):
        pdf = output_dir / f"{docx_path.stem}.pdf"
        pdf.write_bytes(b"%PDF-1.4\n% organization-change fixture\n")
        return pdf

    monkeypatch.setattr(reports, "convert_docx_to_pdf", fake_convert)
    generate_report_files(report, user)
    finalize_report(report, user)
    organization = report.fund.resolved()
    settings = OrganizationSettings.load()
    settings.percentage_decimal_places = 3
    settings.save(update_fields=["percentage_decimal_places", "updated_at"])
    assert mark_organization_reports_stale(settings, user, "Presentation precision changed") == 1
    report.refresh_from_db()
    assert report.status == QuarterlyReport.Status.STALE
    assert organization["percentage_decimal_places"] == 2


@pytest.mark.integration
@pytest.mark.django_db
@pytest.mark.skipif(shutil.which("soffice") is None, reason="LibreOffice is not installed")
def test_real_libreoffice_pdf_conversion(report_fixture):
    report, user, _ = report_fixture
    files = generate_report_files(report, user)
    pdf = next(item for item in files if item.file_type == GeneratedFile.FileType.PDF)
    assert pdf.absolute_path.read_bytes().startswith(b"%PDF")
    assert pdf.size > 1_000
