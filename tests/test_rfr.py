from __future__ import annotations

import calendar
from datetime import date
from decimal import Decimal

import pytest
import requests
from django.contrib.auth import get_user_model
from django.utils import timezone as django_timezone

from navapp.models import Fund, QuarterlyReport, RFRObservation, ShareClass
from navapp.services import rfr
from navapp.services.rfr import (
    FREDProvider,
    Observation,
    RFRProviderError,
    RFRValidationError,
    TreasuryProvider,
    required_months,
    select_month_end_observations,
    set_manual_snapshot,
)


def end_of_month(year: int, month: int) -> date:
    return date(year, month, calendar.monthrange(year, month)[1])


@pytest.fixture
def report(db):
    user = get_user_model().objects.create_user(username="owner", password="safe-password")
    fund = Fund.objects.create(
        legal_name="Example Fund LPF",
        display_name="Example Fund",
        short_code="example",
        structure="Limited Partnership Fund",
        domicile="Hong Kong",
        investment_objective="Test objective",
    )
    share = ShareClass.objects.create(
        fund=fund,
        name="Class A",
        code="a",
        inception_date=date(2025, 4, 1),
        inception_nav=Decimal("100"),
        currency="USD",
    )
    item = QuarterlyReport.objects.create(
        fund=fund,
        share_class=share,
        year=2026,
        quarter=1,
        report_date=date(2026, 3, 31),
        created_by=user,
    )
    return item, user


def test_fred_parsing_ignores_nulls_invalid_values_and_future_dates():
    payload = {
        "observations": [
            {"date": "2026-03-30", "value": "4.21"},
            {"date": "2026-03-31", "value": "."},
            {"date": "bad", "value": "4.22"},
            {"date": "2026-04-01", "value": "4.30"},
        ]
    }
    assert FREDProvider.parse_payload(payload, date(2026, 3, 31)) == [
        Observation(date(2026, 3, 30), Decimal("4.21"))
    ]


def test_treasury_xml_parsing_extracts_ten_year_and_ignores_future():
    payload = b"""<?xml version='1.0'?>
    <feed xmlns:m='http://schemas.microsoft.com/ado/2007/08/dataservices/metadata'
          xmlns:d='http://schemas.microsoft.com/ado/2007/08/dataservices'>
      <entry><content><m:properties><d:NEW_DATE>2026-03-30T00:00:00</d:NEW_DATE>
        <d:BC_10YEAR>4.25</d:BC_10YEAR></m:properties></content></entry>
      <entry><content><m:properties><d:NEW_DATE>2026-04-01T00:00:00</d:NEW_DATE>
        <d:BC_10YEAR>4.30</d:BC_10YEAR></m:properties></content></entry>
    </feed>"""
    assert TreasuryProvider.parse_payload(payload, date(2026, 3, 31)) == [
        Observation(date(2026, 3, 30), Decimal("4.25"))
    ]


def test_end_of_period_selection_uses_last_non_null_day_and_exact_twelve_months():
    observations: list[Observation] = []
    for year, month in required_months(date(2026, 3, 31)):
        observations.append(Observation(date(year, month, 15), Decimal("4.00")))
        observations.append(Observation(end_of_month(year, month), Decimal(f"4.{month:02d}")))
    observations.append(Observation(date(2026, 4, 1), Decimal("9.99")))
    selected = select_month_end_observations(observations, date(2026, 3, 31))
    assert len(selected) == 12
    assert selected[-1] == Observation(date(2026, 3, 31), Decimal("4.03"))
    assert all(item.observation_date <= date(2026, 3, 31) for item in selected)


def test_fewer_than_twelve_months_is_rejected():
    observations = [Observation(end_of_month(2026, month), Decimal("4")) for month in range(1, 4)]
    with pytest.raises(RFRValidationError, match="Missing month-end"):
        select_month_end_observations(observations, date(2026, 3, 31))


@pytest.mark.django_db
def test_cached_observations_are_reused_without_fetch(report, monkeypatch):
    item, _ = report
    fetched_at = django_timezone.now()
    for position, (year, month) in enumerate(required_months(item.report_date), start=1):
        RFRObservation.objects.create(
            provider="FRED_DGS10",
            series="DGS10",
            observation_date=end_of_month(year, month),
            value_percent=Decimal("4") + Decimal(position) / 100,
            fetched_at=fetched_at,
            raw_checksum=f"{position:064d}",
        )

    class NeverFetch:
        provider_code = "FRED_DGS10"
        series = "DGS10"

        def fetch_observations(self, start_date, end_date):
            raise AssertionError("cache should have been reused")

    monkeypatch.setattr(rfr, "get_provider", lambda provider_code: NeverFetch())
    snapshot = rfr.refresh_report_rfr(item, "FRED_DGS10")
    assert snapshot.observations.count() == 12
    assert snapshot.annual_value_decimal == Decimal("0.04065")


@pytest.mark.django_db
def test_manual_override_requires_reason_and_records_user(report):
    item, user = report
    with pytest.raises(RFRValidationError, match="requires a reason"):
        set_manual_snapshot(item, Decimal("4.19"), "", user)
    snapshot = set_manual_snapshot(item, Decimal("4.19"), "Legacy reconciliation", user)
    assert snapshot.is_manual is True
    assert snapshot.annual_value_decimal == Decimal("0.0419")
    assert snapshot.override_by == user


@pytest.mark.django_db
def test_online_refresh_cannot_modify_finalized_report(report, monkeypatch):
    item, _ = report
    QuarterlyReport.objects.filter(pk=item.pk).update(status=QuarterlyReport.Status.FINAL)
    item.refresh_from_db()

    def unexpected_provider(_provider_code):
        raise AssertionError("provider must not be called for a finalized report")

    monkeypatch.setattr(rfr, "get_provider", unexpected_provider)
    with pytest.raises(RFRValidationError, match="immutable"):
        rfr.refresh_report_rfr(item, "FRED_DGS10")


class TimeoutSession:
    headers: dict[str, str] = {}

    def get(self, *args, **kwargs):
        raise requests.Timeout("timed out")


def test_fred_timeout_is_wrapped_in_useful_error(settings):
    provider = FREDProvider(api_key="fake", session=TimeoutSession())
    with pytest.raises(RFRProviderError, match="FRED request failed"):
        provider.fetch_observations(date(2025, 1, 1), date(2026, 3, 31))
