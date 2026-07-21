from datetime import date
from decimal import Decimal
from pathlib import Path

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from navapp.models import (
    Contact,
    Fund,
    FundParty,
    FundStrategyHighlight,
    FundTerm,
    OrganizationSettings,
    ShareClass,
)
from navapp.services.imports import ImportValidationError, import_rows, parse_legacy_xsq

DISCLAIMER = """This document is prepared for general communication for informational purposes only.

X Squared Capital Management LPF (the “Fund”) is a limited partnership fund registered under the laws of Hong Kong.

This document has not been reviewed by any Hong Kong authority or the Securities and Futures Commission of Hong Kong (“HKSFC”). ARC Partners Limited is the General Partner of the Fund. Solomon Capital Management Limited (“Solomon”), the Investment Manager of the Fund, is regulated by the HKSFC to conduct Type 1, Type 4 and Type 9 regulated activities. The Type 9 regulated activity is subject to the condition that Solomon shall only provide services to professional investors.

Different fee structures and terms are applicable subject to the respective series of interests. Potential investors should read the offering documents carefully before deciding whether to invest.

While reasonable care has been exercised in preparing this document, Solomon does not warrant its completeness or accuracy and is not responsible for damages arising from reliance upon this information.

This document is for information only and is not an offer, solicitation or recommendation. Past performance and forecasts are not necessarily indicative of future performance.

Investing in equities, fixed income, commodities, FX and derivatives involves a high degree of risk. Investors should consider their circumstances and seek professional advice.

All opinions, projections and estimates are as of the publication date and may change without notice. Forward-looking statements involve risks and uncertainties. This information is confidential and intended only for the recipient."""


class Command(BaseCommand):
    help = "Create or update the idempotent X Squared demo and import its legacy NAVs."

    def add_arguments(self, parser):
        parser.add_argument(
            "--workbook",
            type=Path,
            default=Path(settings.BASE_DIR) / "reference" / "xsq_nav_history.xlsx",
        )
        parser.add_argument(
            "--newsletter",
            type=Path,
            default=Path(settings.BASE_DIR) / "reference" / "xsq_2026_q1_newsletter.docx",
        )
        parser.add_argument("--skip-nav", action="store_true")

    @transaction.atomic
    def handle(self, *args, **options):
        org = OrganizationSettings.load()
        org.default_disclaimer = DISCLAIMER
        org.disclaimer_version = "XSQ reference 2026-Q1"
        org.save()
        logo_path = Path(settings.BASE_DIR) / "navapp" / "assets" / "aureum-infinity-logo.png"
        if logo_path.is_file():
            org.default_logo.save(
                logo_path.name,
                ContentFile(logo_path.read_bytes()),
                save=True,
            )
        fund, _ = Fund.objects.update_or_create(
            short_code="xsq",
            defaults={
                "legal_name": "X Squared Capital Management LPF",
                "display_name": "X Squared Capital Management LPF",
                "structure": "Hong Kong Limited Partnership Fund",
                "domicile": "Hong Kong",
                "year_end_month": 12,
                "year_end_day": 31,
                "report_language": "en",
                "investment_objective": (
                    "A unique long-short trading strategy across various asset classes to "
                    "achieve medium-term risk-adjusted returns."
                ),
                "performance_note": "",
            },
        )
        strategies = [
            "Diversified portfolio taking both long and short positions including equities, fixed income, currencies, and commodities.",
            "Deploys an algorithmic-assisted approach that analyses data to identify trading opportunities and optimize the risk-reward ratio of each position.",
            "The algorithm considers historical price trends, market volatility and economic indicators to support trading decisions.",
        ]
        FundStrategyHighlight.objects.filter(fund=fund).delete()
        FundStrategyHighlight.objects.bulk_create(
            [
                FundStrategyHighlight(fund=fund, text=text, sort_order=index)
                for index, text in enumerate(strategies)
            ]
        )
        parties = [
            (FundParty.PartyType.PORTFOLIO_MANAGER, "Portfolio Manager", "Archie Ma"),
            (FundParty.PartyType.GENERAL_PARTNER, "General Partner", "ARC Partners Limited"),
            (
                FundParty.PartyType.INVESTMENT_MANAGER,
                "Investment Manager",
                "Solomon Capital Management Limited",
            ),
            (
                FundParty.PartyType.ADMINISTRATOR,
                "Fund Administrator",
                "HKB Fund Services (Hong Kong) Limited",
            ),
        ]
        FundParty.objects.filter(fund=fund).delete()
        FundParty.objects.bulk_create(
            [
                FundParty(
                    fund=fund,
                    party_type=kind,
                    display_label=label,
                    value=value,
                    sort_order=index,
                )
                for index, (kind, label, value) in enumerate(parties)
            ]
        )
        terms = [
            ("minimum-contribution", "Minimum Contribution", "USD100,000"),
            ("valuation-frequency", "Valuation Frequency", "Monthly"),
            ("base-currency", "Base Currency", "USD"),
            ("bloomberg-code", "Bloomberg Code", "XSQMANU HK Equity"),
            ("year-end", "Year End Date", "December 31st"),
            ("management-fee", "Management Fee", "2% per annum"),
            ("lock-up", "Lock-up Period", "36 months"),
            ("carried-interest", "Carried Interest", "20%"),
        ]
        FundTerm.objects.filter(fund=fund).delete()
        FundTerm.objects.bulk_create(
            [
                FundTerm(
                    fund=fund,
                    key=key,
                    display_label=label,
                    value_text=value,
                    sort_order=index,
                )
                for index, (key, label, value) in enumerate(terms)
            ]
        )
        Contact.objects.update_or_create(
            fund=fund,
            role="Portfolio Manager",
            defaults={"name": "Archie Ma", "email": "archie.ma@xsquaredcapital.com"},
        )
        share_class, _ = ShareClass.objects.update_or_create(
            fund=fund,
            code="MANU",
            defaults={
                "name": "MANU",
                "inception_date": date(2022, 7, 29),
                "inception_nav": Decimal("100"),
                "currency": "USD",
                "return_basis": ShareClass.ReturnBasis.NET,
            },
        )
        if not options["skip_nav"]:
            workbook = options["workbook"]
            if not workbook.is_file():
                raise CommandError(f"Workbook not found: {workbook}")
            try:
                result = import_rows(
                    share_class=share_class,
                    rows=parse_legacy_xsq(workbook),
                    commit=True,
                    acknowledge_first_period=True,
                )
            except ImportValidationError as exc:
                raise CommandError(str(exc)) from exc
            self.stdout.write(
                f"NAV import: created={result['created']} skipped={result['skipped']}"
            )
        self.stdout.write(self.style.SUCCESS(f"Demo ready: {fund} / {share_class.name}"))
