from __future__ import annotations

import calendar
import hashlib
import json
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Protocol
from xml.etree import ElementTree

import requests
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from navapp.models import (
    QuarterlyReport,
    ReportRFRObservation,
    RFRObservation,
    RFRSnapshot,
)


class RFRProviderError(RuntimeError):
    pass


class RFRValidationError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class Observation:
    observation_date: date
    value_percent: Decimal


@dataclass(frozen=True, slots=True)
class FetchResult:
    provider: str
    series: str
    observations: list[Observation]
    raw_checksum: str
    fetched_at: datetime


class RiskFreeRateProvider(Protocol):
    provider_code: str
    series: str

    def fetch_observations(self, start_date: date, end_date: date) -> FetchResult: ...


def _session() -> requests.Session:
    session = requests.Session()
    retry = Retry(
        total=2,
        connect=2,
        read=2,
        backoff_factor=0.4,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset({"GET"}),
    )
    session.mount("https://", HTTPAdapter(max_retries=retry))
    session.headers.update({"User-Agent": "NAVQuarterlyReport/1.0 (internal reporting)"})
    return session


class FREDProvider:
    provider_code = "FRED_DGS10"
    series = "DGS10"
    endpoint = "https://api.stlouisfed.org/fred/series/observations"

    def __init__(self, api_key: str | None = None, session: requests.Session | None = None):
        self.api_key = api_key if api_key is not None else settings.FRED_API_KEY
        self.session = session or _session()

    @staticmethod
    def parse_payload(payload: dict[str, object], end_date: date) -> list[Observation]:
        parsed: list[Observation] = []
        for row in payload.get("observations", []):
            if not isinstance(row, dict):
                continue
            raw_date = row.get("date")
            raw_value = row.get("value")
            if not raw_date or raw_value in {None, "", "."}:
                continue
            try:
                observed = date.fromisoformat(str(raw_date))
                value = Decimal(str(raw_value))
            except (ValueError, ArithmeticError):
                continue
            if observed <= end_date:
                parsed.append(Observation(observed, value))
        return sorted(parsed, key=lambda item: item.observation_date)

    def fetch_observations(self, start_date: date, end_date: date) -> FetchResult:
        if not self.api_key:
            raise RFRProviderError("尚未設定 FRED_API_KEY。")
        params = {
            "series_id": self.series,
            "api_key": self.api_key,
            "file_type": "json",
            "observation_start": start_date.isoformat(),
            "observation_end": end_date.isoformat(),
            "sort_order": "asc",
        }
        try:
            response = self.session.get(
                self.endpoint, params=params, timeout=settings.RFR_HTTP_TIMEOUT
            )
            response.raise_for_status()
            payload = response.json()
        except (requests.RequestException, json.JSONDecodeError) as exc:
            raise RFRProviderError(f"FRED 請求失敗：{exc}") from exc
        raw = response.content
        return FetchResult(
            provider=self.provider_code,
            series=self.series,
            observations=self.parse_payload(payload, end_date),
            raw_checksum=hashlib.sha256(raw).hexdigest(),
            fetched_at=timezone.now(),
        )


class TreasuryProvider:
    provider_code = "TREASURY_CMT10"
    series = "BC_10YEAR"
    endpoint = (
        "https://home.treasury.gov/resource-center/data-chart-center/interest-rates/pages/xml"
    )

    def __init__(self, session: requests.Session | None = None):
        self.session = session or _session()

    @staticmethod
    def parse_payload(payload: bytes, end_date: date) -> list[Observation]:
        try:
            root = ElementTree.fromstring(payload)
        except ElementTree.ParseError as exc:
            raise RFRProviderError(f"美國財政部 XML 解析失敗：{exc}") from exc
        parsed: list[Observation] = []
        for entry in root.iter():
            if not entry.tag.endswith("properties"):
                continue
            values: dict[str, str] = {}
            for child in entry:
                tag = child.tag.rsplit("}", 1)[-1]
                values[tag] = (child.text or "").strip()
            raw_date = values.get("NEW_DATE") or values.get("Date")
            raw_value = values.get("BC_10YEAR")
            if not raw_date or not raw_value:
                continue
            try:
                observed = date.fromisoformat(raw_date[:10])
                value = Decimal(raw_value)
            except (ValueError, ArithmeticError):
                continue
            if observed <= end_date:
                parsed.append(Observation(observed, value))
        return sorted(parsed, key=lambda item: item.observation_date)

    def fetch_observations(self, start_date: date, end_date: date) -> FetchResult:
        all_observations: list[Observation] = []
        checksums: list[str] = []
        for year in range(start_date.year, end_date.year + 1):
            params = {
                "data": "daily_treasury_yield_curve",
                "field_tdr_date_value": str(year),
            }
            try:
                response = self.session.get(
                    self.endpoint, params=params, timeout=settings.RFR_HTTP_TIMEOUT
                )
                response.raise_for_status()
            except requests.RequestException as exc:
                raise RFRProviderError(f"美國財政部 {year} 年資料請求失敗：{exc}") from exc
            checksums.append(hashlib.sha256(response.content).hexdigest())
            all_observations.extend(self.parse_payload(response.content, end_date))
        observations = [
            item for item in all_observations if start_date <= item.observation_date <= end_date
        ]
        return FetchResult(
            provider=self.provider_code,
            series=self.series,
            observations=sorted(observations, key=lambda item: item.observation_date),
            raw_checksum=hashlib.sha256("".join(checksums).encode()).hexdigest(),
            fetched_at=timezone.now(),
        )


def _previous_month(year: int, month: int) -> tuple[int, int]:
    return (year - 1, 12) if month == 1 else (year, month - 1)


def required_months(report_end: date, count: int = 12) -> list[tuple[int, int]]:
    cursor = (report_end.year, report_end.month)
    values: list[tuple[int, int]] = []
    for _ in range(count):
        values.append(cursor)
        cursor = _previous_month(*cursor)
    return list(reversed(values))


def select_month_end_observations(
    observations: list[Observation], report_end: date, count: int = 12
) -> list[Observation]:
    grouped: dict[tuple[int, int], Observation] = {}
    for item in observations:
        if item.observation_date > report_end:
            continue
        key = (item.observation_date.year, item.observation_date.month)
        current = grouped.get(key)
        if current is None or item.observation_date > current.observation_date:
            grouped[key] = item
    expected = required_months(report_end, count)
    missing = [
        f"{year:04d}-{month:02d}" for year, month in expected if (year, month) not in grouped
    ]
    if missing:
        raise RFRValidationError("缺少月底無風險利率觀察值：" + ", ".join(missing))
    selected = [grouped[key] for key in expected]
    if any(item.observation_date > report_end for item in selected):
        raise RFRValidationError("無風險利率觀察日期不得超過報告截止日。")
    return selected


@transaction.atomic
def cache_fetch_result(result: FetchResult) -> list[RFRObservation]:
    cached: list[RFRObservation] = []
    for item in result.observations:
        obj, _ = RFRObservation.objects.update_or_create(
            provider=result.provider,
            series=result.series,
            observation_date=item.observation_date,
            defaults={
                "value_percent": item.value_percent,
                "fetched_at": result.fetched_at,
                "raw_checksum": result.raw_checksum,
            },
        )
        cached.append(obj)
    return cached


@transaction.atomic
def attach_cached_snapshot(report: QuarterlyReport, provider: str, series: str) -> RFRSnapshot:
    if report.status in {QuarterlyReport.Status.FINAL, QuarterlyReport.Status.STALE}:
        raise RFRValidationError("已定稿報告的無風險利率快照不可修改。")
    rows = list(
        RFRObservation.objects.filter(
            provider=provider,
            series=series,
            observation_date__lte=report.report_date,
        ).order_by("observation_date")
    )
    selected_values = select_month_end_observations(
        [Observation(row.observation_date, row.value_percent) for row in rows], report.report_date
    )
    by_key = {(row.observation_date, row.value_percent): row for row in rows}
    average_percent = sum((item.value_percent for item in selected_values), Decimal(0)) / Decimal(
        len(selected_values)
    )
    checksum = hashlib.sha256(
        "".join(
            by_key[(item.observation_date, item.value_percent)].raw_checksum
            for item in selected_values
        ).encode()
    ).hexdigest()
    snapshot, _ = RFRSnapshot.objects.update_or_create(
        report=report,
        defaults={
            "provider": provider,
            "series": series,
            "annual_value_decimal": average_percent / Decimal(100),
            "is_manual": False,
            "override_reason": "",
            "override_by": None,
            "override_at": None,
            "raw_checksum": checksum,
        },
    )
    snapshot.observations.all().delete()
    for position, item in enumerate(selected_values, start=1):
        source = by_key[(item.observation_date, item.value_percent)]
        ReportRFRObservation.objects.create(
            snapshot=snapshot,
            source_observation=source,
            position=position,
            observation_date=item.observation_date,
            value_percent=item.value_percent,
        )
    return snapshot


@transaction.atomic
def set_manual_snapshot(
    report: QuarterlyReport, value_percent: Decimal, reason: str, user
) -> RFRSnapshot:
    if report.status in {QuarterlyReport.Status.FINAL, QuarterlyReport.Status.STALE}:
        raise RFRValidationError("已定稿報告的無風險利率快照不可修改。")
    if not reason.strip():
        raise RFRValidationError("手動覆寫無風險利率必須填寫原因。")
    snapshot, _ = RFRSnapshot.objects.update_or_create(
        report=report,
        defaults={
            "provider": "MANUAL",
            "series": "MANUAL",
            "annual_value_decimal": Decimal(value_percent) / Decimal(100),
            "is_manual": True,
            "override_reason": reason.strip(),
            "override_by": user,
            "override_at": timezone.now(),
            "raw_checksum": hashlib.sha256(
                f"{value_percent}|{reason.strip()}".encode()
            ).hexdigest(),
        },
    )
    snapshot.observations.all().delete()
    snapshot.full_clean()
    snapshot.save()
    return snapshot


def get_provider(provider_code: str) -> RiskFreeRateProvider:
    if provider_code == FREDProvider.provider_code:
        return FREDProvider()
    if provider_code == TreasuryProvider.provider_code:
        return TreasuryProvider()
    raise RFRProviderError(f"不支援的線上無風險利率來源：{provider_code}")


def refresh_report_rfr(report: QuarterlyReport, provider_code: str | None = None) -> RFRSnapshot:
    if report.status in {QuarterlyReport.Status.FINAL, QuarterlyReport.Status.STALE}:
        raise RFRValidationError("已定稿報告的無風險利率快照不可修改。")
    provider_was_explicit = provider_code is not None
    provider_code = provider_code or report.fund.resolved().get("rfr_provider")
    if not provider_code:
        from navapp.models import OrganizationSettings

        provider_code = OrganizationSettings.load().rfr_provider
    if (
        not provider_was_explicit
        and provider_code == FREDProvider.provider_code
        and not settings.FRED_API_KEY
    ):
        provider_code = TreasuryProvider.provider_code
    provider = get_provider(str(provider_code))
    start = report.report_date - timedelta(days=450)
    cached = list(
        RFRObservation.objects.filter(
            provider=provider.provider_code,
            series=provider.series,
            observation_date__gte=start,
            observation_date__lte=report.report_date,
        )
    )
    try:
        select_month_end_observations(
            [Observation(item.observation_date, item.value_percent) for item in cached],
            report.report_date,
        )
    except RFRValidationError:
        result = provider.fetch_observations(start, report.report_date)
        cache_fetch_result(result)
    return attach_cached_snapshot(report, provider.provider_code, provider.series)


def calendar_month_end(year: int, month: int) -> date:
    return date(year, month, calendar.monthrange(year, month)[1])
