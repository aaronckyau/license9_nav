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
        assert reverse("nav-year-chart", args=[1, 2026]) == "/nav/classes/1/nav/chart/2026/"
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
    assert "輸入每股 NAV" in dashboard
    assert "評論及產生報告" in dashboard
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
        inception_date=date(2024, 3, 1),
        inception_nav=Decimal("100"),
        currency="USD",
    )

    dashboard = client.get(reverse("dashboard"))
    dashboard_text = dashboard.content.decode()
    assert reverse("simple-entry", args=[share.pk]) in dashboard_text
    assert "選擇基金" in dashboard_text
    assert "輸入每股 NAV" in dashboard_text
    assert "評論及產生報告" in dashboard_text
    assert "檢視績效" not in dashboard_text

    entry = client.get(reverse("simple-entry", args=[share.pk]))
    assert entry.status_code == 200
    assert entry.context["form"]["valuation_month"].value() == date(2024, 3, 31)
    assert entry.context["next_period"] == date(2024, 3, 31)
    assert "系統日期：2026 年 7 月 20 日" in entry.content.decode()
    assert "最近已完成月份：2026 年 6 月" in entry.content.decode()
    assert "2024" in entry.content.decode()
    assert "3 月" in entry.content.decode()
    assert 'name="commentary_markdown"' not in entry.content.decode()

    future = client.post(
        reverse("simple-entry", args=[share.pk]),
        {
            "valuation_month": "2026-07-31",
            "nav_per_share": "105",
        },
    )
    assert future.status_code == 200
    assert "估值月份不得晚於最近已完成月份" in future.content.decode()
    assert not NAVRecord.objects.filter(share_class=share).exists()

    response = client.post(
        reverse("simple-entry", args=[share.pk]),
        {
            "valuation_month": "2024-03-31",
            "nav_per_share": "105.123456",
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
    assert report.commentary_markdown == ""
    assert report.commentary_date == date(2024, 3, 31)
    assert response.url == f"{reverse('report-history')}?report={report.pk}"
    assert AuditLog.objects.filter(action="SIMPLE_ENTRY", entity_id=str(report.pk)).exists()
    history = client.get(response.url)
    assert history.status_code == 200
    assert "系統會自動取得美國財政部 10 年期利率" in history.content.decode()
    assert "基金經理評論" in history.content.decode()
    assert "僅儲存評論" in history.content.decode()
    assert reverse("report-generate", args=[report.pk]) in history.content.decode()
    assert reverse("simple-entry", args=[share.pk]) in history.content.decode()

    duplicate = client.post(
        reverse("simple-entry", args=[share.pk]),
        {
            "valuation_month": "2024-03-31",
            "nav_per_share": "106",
        },
    )
    assert duplicate.status_code == 200
    assert "該月份已有 NAV 紀錄" in duplicate.content.decode()
    assert NAVRecord.objects.filter(share_class=share).count() == 1

    abnormal_payload = {
        "valuation_month": "2024-04-30",
        "nav_per_share": "200",
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
    assert confirmed.url == reverse("simple-entry", args=[share.pk])
    assert NAVRecord.objects.filter(share_class=share).count() == 2
    assert NAVRecord.objects.get(valuation_month=date(2024, 4, 30)).change_acknowledged is True
    q2_report = QuarterlyReport.objects.get(share_class=share, year=2024, quarter=2)
    assert q2_report.commentary_date == date(2024, 6, 30)


@pytest.mark.django_db
def test_simple_nav_entry_lists_existing_months_and_next_missing_month(
    client, django_user_model, monkeypatch
):
    monkeypatch.setattr("navapp.forms.timezone.localdate", lambda: date(2025, 4, 20))
    user = django_user_model.objects.create_user("monthly-user", password="safe-password")
    client.force_login(user)
    fund = Fund.objects.create(
        legal_name="Monthly Fund LPF",
        display_name="Monthly Fund",
        short_code="monthly-fund",
        structure="LPF",
        domicile="Hong Kong",
        investment_objective="Monthly objective",
    )
    share = ShareClass.objects.create(
        fund=fund,
        name="Class A",
        code="monthly-a",
        inception_date=date(2025, 1, 1),
        inception_nav=Decimal("100"),
        currency="USD",
    )
    for month, value in ((1, "40"), (2, "69")):
        NAVRecord.objects.create(
            share_class=share,
            valuation_month=date(2025, month, 28 if month == 2 else 31),
            valuation_date=date(2025, month, 28 if month == 2 else 31),
            nav_per_share=Decimal(value),
            created_by=user,
            updated_by=user,
        )

    response = client.get(reverse("simple-entry", args=[share.pk]))
    content = response.content.decode()
    assert response.status_code == 200
    assert response.context["next_period"] == date(2025, 3, 31)
    assert response.context["form"]["valuation_month"].value() == date(2025, 3, 31)
    assert "2025" in content
    assert "1 月" in content and "40" in content
    assert "2 月" in content and "69" in content
    assert "3 月" in content and "新增月份" in content


@pytest.mark.django_db
def test_simple_nav_entry_keeps_latest_months_visible_and_editable(
    client, django_user_model, monkeypatch
):
    monkeypatch.setattr("navapp.forms.timezone.localdate", lambda: date(2025, 4, 20))
    user = django_user_model.objects.create_user("latest-user", password="safe-password")
    client.force_login(user)
    fund = Fund.objects.create(
        legal_name="Latest Fund LPF",
        display_name="Latest Fund",
        short_code="latest-fund",
        structure="LPF",
        domicile="Hong Kong",
        investment_objective="Latest objective",
    )
    share = ShareClass.objects.create(
        fund=fund,
        name="Class A",
        code="latest-a",
        inception_date=date(2025, 1, 1),
        inception_nav=Decimal("100"),
        currency="USD",
    )
    records = []
    for month, day, value in ((1, 31, "40"), (2, 28, "69"), (3, 31, "75")):
        records.append(
            NAVRecord.objects.create(
                share_class=share,
                valuation_month=date(2025, month, day),
                valuation_date=date(2025, month, day),
                nav_per_share=Decimal(value),
                created_by=user,
                updated_by=user,
            )
        )

    response = client.get(reverse("simple-entry", args=[share.pk]))
    content = response.content.decode()

    assert response.status_code == 200
    assert response.context["next_period"] is None
    assert "每月 NAV 已是最新" in content
    assert "2025" in content
    for record in records:
        assert f"{record.valuation_month.month} 月" in content
        assert reverse("nav-edit", args=[share.pk, record.pk]) in content
    assert "40.000000" in content
    assert "69.000000" in content
    assert "75.000000" in content


@pytest.mark.django_db
def test_nav_dashboard_renders_yearly_metrics_returns_charts_and_all_months(
    client, django_user_model, monkeypatch
):
    monkeypatch.setattr("navapp.forms.timezone.localdate", lambda: date(2026, 3, 20))
    user = django_user_model.objects.create_user("dashboard-user", password="safe-password")
    client.force_login(user)
    fund = Fund.objects.create(
        legal_name="Dashboard Fund LPF",
        display_name="Dashboard Fund",
        short_code="dashboard-fund",
        structure="LPF",
        domicile="Hong Kong",
        investment_objective="Dashboard objective",
    )
    share = ShareClass.objects.create(
        fund=fund,
        name="Class A",
        code="dashboard-a",
        inception_date=date(2024, 12, 1),
        inception_nav=Decimal("80"),
        currency="USD",
    )
    values = [(2024, 12, "80")]
    values.extend((2025, month, str(80 + month)) for month in range(1, 13))
    values.extend(((2026, 1, "90"), (2026, 2, "99")))
    records = []
    for year, month, value in values:
        valuation_month = date(
            year,
            month,
            28 if month == 2 else 30 if month in {4, 6, 9, 11} else 31,
        )
        records.append(
            NAVRecord.objects.create(
                share_class=share,
                valuation_month=valuation_month,
                valuation_date=valuation_month,
                nav_per_share=Decimal(value),
                created_by=user,
                updated_by=user,
            )
        )

    response = client.get(reverse("simple-entry", args=[share.pk]))
    content = response.content.decode()

    assert response.status_code == 200
    assert response.context["next_period"] is None
    assert "最新 NAV（2026 年 2 月）" in content
    assert "年初至今回報（YTD）" in content
    assert "+7.61%" in content
    assert "全年度回報（FY）" in content
    assert "+15.00%" in content
    assert "-2.17%" in content
    assert "+10.00%" in content
    assert "nav-return-positive" in content
    assert "nav-return-negative" in content
    assert 'data-year="2025"' in content
    assert content.count('data-year="2025" data-month-row') == 12
    assert "99.000000" in content
    assert reverse("nav-year-chart", args=[share.pk, 2025]) in content
    assert reverse("nav-year-chart", args=[share.pk, 2026]) in content
    for record in records:
        assert reverse("nav-edit", args=[share.pk, record.pk]) in content


@pytest.mark.django_db
def test_nav_dashboard_documents_first_record_fallback_without_fake_initial_return(
    client, django_user_model, monkeypatch
):
    monkeypatch.setattr("navapp.forms.timezone.localdate", lambda: date(2025, 4, 20))
    user = django_user_model.objects.create_user("fallback-user", password="safe-password")
    client.force_login(user)
    fund = Fund.objects.create(
        legal_name="Fallback Fund LPF",
        display_name="Fallback Fund",
        short_code="fallback-fund",
        structure="LPF",
        domicile="Hong Kong",
        investment_objective="Fallback objective",
    )
    share = ShareClass.objects.create(
        fund=fund,
        name="Class A",
        code="fallback-a",
        inception_date=date(2025, 1, 1),
        inception_nav=Decimal("100"),
        currency="USD",
    )
    for month, day, value in ((1, 31, "100"), (2, 28, "110"), (4, 30, "99")):
        NAVRecord.objects.create(
            share_class=share,
            valuation_month=date(2025, month, day),
            valuation_date=date(2025, month, day),
            nav_per_share=Decimal(value),
            created_by=user,
            updated_by=user,
        )

    response = client.get(reverse("simple-entry", args=[share.pk]))
    year = response.context["nav_years"][0]

    assert response.status_code == 200
    assert year.baseline_note == "無上一年度末 NAV；以 2025 年首筆 NAV 為基準"
    assert year.period_return == Decimal("-0.01")
    assert year.period_return_display == "-1.00%"
    assert year.months[0].monthly_return is None
    assert year.months[0].cumulative_return is None
    assert year.months[0].monthly_return_display == "—"
    assert year.months[1].monthly_return == Decimal("0.1")
    assert year.months[1].cumulative_return == Decimal("0.1")
    assert [month.month for month in year.months] == [1, 2, 3, 4]
    assert year.months[2].is_next is True
    assert year.months[3].monthly_return is None
    assert year.months[3].monthly_return_display == "—"
    assert year.months[3].cumulative_return == Decimal("-0.01")
    assert "無上一年度末 NAV；以 2025 年首筆 NAV 為基準" in response.content.decode()


@pytest.mark.django_db
def test_nav_year_chart_and_existing_edit_form_remain_authenticated(client, django_user_model):
    user = django_user_model.objects.create_user("chart-user", password="safe-password")
    fund = Fund.objects.create(
        legal_name="Chart Fund LPF",
        display_name="Chart Fund",
        short_code="chart-fund",
        structure="LPF",
        domicile="Hong Kong",
        investment_objective="Chart objective",
    )
    share = ShareClass.objects.create(
        fund=fund,
        name="Class A",
        code="chart-a",
        inception_date=date(2025, 1, 1),
        inception_nav=Decimal("100"),
        currency="USD",
    )
    record = NAVRecord.objects.create(
        share_class=share,
        valuation_month=date(2025, 1, 31),
        valuation_date=date(2025, 1, 31),
        nav_per_share=Decimal("101.123456789"),
        created_by=user,
        updated_by=user,
    )
    chart_url = reverse("nav-year-chart", args=[share.pk, 2025])

    unauthenticated_page = client.get(reverse("simple-entry", args=[share.pk]))
    assert unauthenticated_page.status_code == 302
    assert reverse("login") in unauthenticated_page.url
    unauthenticated = client.get(chart_url)
    assert unauthenticated.status_code == 302
    assert reverse("login") in unauthenticated.url

    client.force_login(user)
    chart = client.get(chart_url)
    mobile_chart = client.get(f"{chart_url}?layout=mobile")
    assert chart.status_code == 200
    assert chart["Content-Type"] == "image/png"
    assert chart["Cache-Control"] == "private, no-store"
    assert chart.content.startswith(b"\x89PNG\r\n\x1a\n")
    assert mobile_chart.status_code == 200
    assert mobile_chart.content.startswith(b"\x89PNG\r\n\x1a\n")
    assert mobile_chart.content != chart.content
    assert client.get(reverse("nav-year-chart", args=[share.pk, 2024])).status_code == 404

    edit = client.get(reverse("nav-edit", args=[share.pk, record.pk]))
    assert edit.status_code == 200
    assert edit.context["form"].instance == record
    assert edit.context["form"]["nav_per_share"].value() == Decimal("101.123456789")
    assert edit.context["reason_form"] is not None


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

    response = client.post(
        reverse("report-generate", args=[report.pk]),
        {
            "inline_commentary": "1",
            "commentary_markdown": "本季維持審慎的風險管理。",
        },
    )
    assert response.status_code == 302
    assert response.url == f"{reverse('report-history')}?report={report.pk}"
    assert calls == [("calculate", report.pk), report.pk, (report.pk, user.pk)]
    report.refresh_from_db()
    assert report.commentary_markdown == "本季維持審慎的風險管理。"

    report.commentary_markdown = ""
    report.save(update_fields=["commentary_markdown", "updated_at"])
    missing_commentary = client.post(
        reverse("report-generate", args=[report.pk]),
        {"inline_commentary": "1", "commentary_markdown": ""},
    )
    assert missing_commentary.status_code == 200
    assert "必須填寫基金經理評論" in missing_commentary.content.decode()

    calls.clear()
    report.commentary_markdown = "Commentary"
    report.save(update_fields=["commentary_markdown", "updated_at"])

    def reject_incomplete_quarter(item):
        calls.append(("calculate", item.pk))
        raise CalculationValidationError(["缺少估值月份：2024-02"])

    monkeypatch.setattr("navapp.views.calculate_for_report", reject_incomplete_quarter)
    incomplete = client.post(reverse("report-generate", args=[report.pk]), follow=True)
    assert incomplete.status_code == 200
    assert "缺少估值月份：2024-02" in incomplete.content.decode()
    assert calls == [("calculate", report.pk)]


@pytest.mark.django_db
def test_ready_report_commentary_edit_creates_a_new_version(client, django_user_model):
    user = django_user_model.objects.create_user("version-user", password="safe-password")
    client.force_login(user)
    fund = Fund.objects.create(
        legal_name="Version Fund LPF",
        display_name="Version Fund",
        short_code="version-fund",
        structure="LPF",
        domicile="Hong Kong",
        investment_objective="Version objective",
    )
    share = ShareClass.objects.create(
        fund=fund,
        name="Class A",
        code="version-a",
        inception_date=date(2024, 1, 1),
        inception_nav=Decimal("100"),
        currency="USD",
    )
    original = QuarterlyReport.objects.create(
        fund=fund,
        share_class=share,
        year=2024,
        quarter=1,
        version=1,
        report_date=date(2024, 3, 31),
        status=QuarterlyReport.Status.READY,
        commentary_markdown="Original commentary",
        snapshot={"identity": {"report_id": 1}},
        created_by=user,
    )

    history = client.get(f"{reverse('report-history')}?report={original.pk}")
    assert "另存評論為新版本" in history.content.decode()
    assert "建立新版本並重新產生" in history.content.decode()

    response = client.post(
        reverse("report-generate", args=[original.pk]),
        {
            "inline_commentary": "1",
            "commentary_markdown": "Revised commentary",
            "action": "save_commentary",
        },
    )

    assert response.status_code == 302
    original.refresh_from_db()
    revised = QuarterlyReport.objects.get(share_class=share, version=2)
    assert original.status == QuarterlyReport.Status.READY
    assert original.commentary_markdown == "Original commentary"
    assert original.snapshot == {"identity": {"report_id": 1}}
    assert revised.status == QuarterlyReport.Status.DRAFT
    assert revised.commentary_markdown == "Revised commentary"
    assert response.url == f"{reverse('report-history')}?report={revised.pk}"
    assert AuditLog.objects.filter(
        entity_id=str(revised.pk), action="CREATE_VERSION_FROM_READY"
    ).exists()


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
