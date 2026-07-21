from __future__ import annotations

import hashlib
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
    reset_affected_mutable_reports,
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
    assert "Fund Performance (Net Quarterly Returns)" in text
    assert "Fund Performance (Graph)" in text
    assert "Manager Commentary" in text
    assert "Fund-specific legal disclaimer" in text
    assert "Professional investors only - fund override" in text
    assert "Calculation and provenance:" not in text
    section_positions = [
        text.index(label)
        for label in (
            "Investment Objective",
            "Strategy Highlights and Characteristics",
            "Fund Performance (Net Quarterly Returns)",
            "Fund Performance (Graph)",
            "Manager Commentary",
            "General Information",
            "Contacts",
            "Disclaimer",
        )
    ]
    assert section_positions == sorted(section_positions)
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
    assert package_audit["footer_texts"] == ["Page 1", "Page 1", "Page 1"]


@pytest.mark.django_db
def test_xsq_report_uses_the_packaged_aureum_logo_and_omits_legacy_fee_note(report_fixture):
    report, _, tmp_path = report_fixture
    report.fund.short_code = "xsq"
    report.fund.performance_note = (
        "Note: Please refer to the fund offering documents for a detailed fee structure."
    )
    report.fund.save(update_fields=["short_code", "performance_note", "updated_at"])

    _, output = _build_docx(report, tmp_path)
    document = Document(output)
    text = "\n".join(paragraph.text for paragraph in document.paragraphs)
    asset = Path(reports.AUREUM_INFINITY_LOGO_PATH)

    assert "detailed fee structure" not in text
    with ZipFile(output) as package:
        embedded_hashes = {
            hashlib.sha256(package.read(name)).hexdigest()
            for name in package.namelist()
            if name.startswith("word/media/")
        }
    assert hashlib.sha256(asset.read_bytes()).hexdigest() in embedded_hashes


@pytest.mark.django_db
def test_monthly_docx_uses_monthly_period_and_return_table(report_fixture):
    report, _, tmp_path = report_fixture
    report.report_type = QuarterlyReport.ReportType.MONTHLY
    report.report_month = 2
    report.report_date = date(2024, 2, 29)
    report.commentary_date = report.report_date
    report.save(
        update_fields=[
            "report_type",
            "report_month",
            "report_date",
            "commentary_date",
            "updated_at",
        ]
    )

    snapshot, output = _build_docx(report, tmp_path)
    document = Document(output)
    paragraph_text = "\n".join(paragraph.text for paragraph in document.paragraphs)
    table_text = "\n".join(
        cell.text for table in document.tables for row in table.rows for cell in row.cells
    )

    assert snapshot["identity"]["report_type"] == "MONTHLY"
    assert snapshot["identity"]["period_label"] == "2024 年 2 月月報"
    assert snapshot["calculation"]["report_type"] == "MONTHLY"
    assert "February 2024 Monthly Report" in paragraph_text
    assert "Fund Performance (Monthly Returns)" in paragraph_text
    assert "2024-02" in table_text
    assert "103.00" in table_text
    assert "1.98%" in table_text
    assert all("Version" not in footer.text for footer in document.sections[0].footer.paragraphs)


@pytest.mark.django_db
def test_monthly_generation_uses_builtin_layout_when_quarterly_custom_template_is_configured(
    report_fixture, monkeypatch
):
    report, user, _ = report_fixture
    report.report_type = QuarterlyReport.ReportType.MONTHLY
    report.report_month = 3
    report.save(update_fields=["report_type", "report_month", "updated_at"])
    report.fund.custom_docx_template.name = "funds/templates/quarterly-only.docx"
    report.fund.save(update_fields=["custom_docx_template", "updated_at"])
    custom_calls = []

    def reject_custom(*args, **kwargs):
        custom_calls.append((args, kwargs))
        raise AssertionError("monthly reports must not use a quarterly-only custom template")

    def fake_convert(docx_path, output_dir):
        pdf = output_dir / f"{docx_path.stem}.pdf"
        pdf.write_bytes(b"%PDF-1.4\n% monthly fallback test\n")
        return pdf

    monkeypatch.setattr(reports, "build_custom_docx", reject_custom)
    monkeypatch.setattr(reports, "convert_docx_to_pdf", fake_convert)
    generated = generate_report_files(report, user)

    assert custom_calls == []
    assert {item.file_type for item in generated} == {"DOCX", "PDF"}
    monthly_docx = next(item.absolute_path for item in generated if item.file_type == "DOCX")
    assert "Fund Performance (Monthly Returns)" in "\n".join(
        paragraph.text for paragraph in Document(monthly_docx).paragraphs
    )


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
    with pytest.raises(ValidationError, match="不可修改"):
        report.save()
    report.refresh_from_db()
    report.status = QuarterlyReport.Status.DRAFT
    with pytest.raises(ValidationError, match="狀態只可"):
        report.save()
    generated = report.files.first()
    generated.sha256 = "0" * 64
    with pytest.raises(ValidationError, match="檔案不可修改"):
        generated.save()
    rfr = report.rfr_snapshot
    rfr.override_reason = "Attempted mutation"
    with pytest.raises(ValidationError, match="無風險利率快照不可修改"):
        rfr.save()
    record = report.share_class.nav_records.get(valuation_month=date(2024, 2, 29))
    assert mark_affected_reports_stale(record, user, "NAV correction") == 1
    report.refresh_from_db()
    assert report.status == QuarterlyReport.Status.STALE


@pytest.mark.django_db
def test_nav_change_resets_mutable_report_snapshot_and_downloads(report_fixture, monkeypatch):
    report, user, _ = report_fixture

    def fake_convert(docx_path, output_dir):
        pdf = output_dir / f"{docx_path.stem}.pdf"
        pdf.write_bytes(b"%PDF-1.4\n% mutable fixture\n")
        return pdf

    monkeypatch.setattr(reports, "convert_docx_to_pdf", fake_convert)
    generate_report_files(report, user)
    report.refresh_from_db()
    assert report.status == QuarterlyReport.Status.READY
    assert report.snapshot
    assert report.files.count() == 2

    record = report.share_class.nav_records.get(valuation_month=date(2024, 2, 29))
    assert reset_affected_mutable_reports(record, user, "NAV correction") == 1
    report.refresh_from_db()
    assert report.status == QuarterlyReport.Status.DRAFT
    assert report.snapshot == {}
    assert report.generation_error == ""
    assert not report.files.exists()


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
