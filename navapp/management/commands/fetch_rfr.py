from django.core.management.base import BaseCommand, CommandError

from navapp.models import QuarterlyReport
from navapp.services.rfr import RFRProviderError, RFRValidationError, refresh_report_rfr


class Command(BaseCommand):
    help = "Fetch/cache official RFR data and attach a 12-month snapshot to a report."

    def add_arguments(self, parser):
        parser.add_argument("--report-id", required=True, type=int)
        parser.add_argument("--provider", choices=("FRED_DGS10", "TREASURY_CMT10"))

    def handle(self, *args, **options):
        try:
            report = QuarterlyReport.objects.get(pk=options["report_id"])
            snapshot = refresh_report_rfr(report, options["provider"])
        except QuarterlyReport.DoesNotExist as exc:
            raise CommandError("Report not found.") from exc
        except (RFRProviderError, RFRValidationError) as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(
            self.style.SUCCESS(
                f"{snapshot.provider}/{snapshot.series}: "
                f"{snapshot.annual_value_decimal} from {snapshot.observations.count()} observations"
            )
        )
