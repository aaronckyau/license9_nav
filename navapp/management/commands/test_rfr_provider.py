from datetime import date, timedelta

from django.core.management.base import BaseCommand, CommandError

from navapp.services.rfr import (
    RFRProviderError,
    RFRValidationError,
    get_provider,
    select_month_end_observations,
)


class Command(BaseCommand):
    help = "Live connectivity and cutoff test for an official RFR provider."

    def add_arguments(self, parser):
        parser.add_argument(
            "--provider",
            default="FRED_DGS10",
            choices=("FRED_DGS10", "TREASURY_CMT10"),
        )
        parser.add_argument("--report-end", required=True, type=date.fromisoformat)

    def handle(self, *args, **options):
        provider = get_provider(options["provider"])
        report_end = options["report_end"]
        try:
            result = provider.fetch_observations(report_end - timedelta(days=450), report_end)
            selected = select_month_end_observations(result.observations, report_end)
        except (RFRProviderError, RFRValidationError) as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(
            self.style.SUCCESS(
                f"provider={result.provider} series={result.series} observations={len(selected)} "
                f"cutoff={selected[-1].observation_date} checksum={result.raw_checksum}"
            )
        )
