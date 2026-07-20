from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db.models import Max

from navapp.models import QuarterlyReport, ShareClass
from navapp.services.reports import ReportGenerationError, finalize_report, generate_report_files
from navapp.services.rfr import set_manual_snapshot


class Command(BaseCommand):
    help = "Generate the deterministic XSQ 2026 Q1 DOCX/PDF report smoke fixture."

    def add_arguments(self, parser):
        parser.add_argument("--username")
        parser.add_argument("--finalize", action="store_true")

    def handle(self, *args, **options):
        call_command("seed_demo")
        share_class = ShareClass.objects.get(fund__short_code="xsq", code="MANU")
        report = QuarterlyReport.objects.filter(
            share_class=share_class,
            year=2026,
            quarter=1,
            status__in=(
                QuarterlyReport.Status.DRAFT,
                QuarterlyReport.Status.READY,
                QuarterlyReport.Status.GENERATION_FAILED,
            ),
        ).first()
        user = None
        if options["username"]:
            user = get_user_model().objects.filter(username=options["username"]).first()
            if user is None:
                raise CommandError("Requested user does not exist.")
        if report is None:
            version = (
                QuarterlyReport.objects.filter(
                    share_class=share_class, year=2026, quarter=1
                ).aggregate(Max("version"))["version__max"]
                or 0
            ) + 1
            report = QuarterlyReport.objects.create(
                fund=share_class.fund,
                share_class=share_class,
                year=2026,
                quarter=1,
                version=version,
                report_date=date(2026, 3, 31),
                commentary_date=date(2026, 3, 31),
                created_by=user,
            )
        report.commentary_title = "2026 Q1 Portfolio Review"
        report.commentary_author = "Archie Ma"
        report.commentary_markdown = (
            "The first quarter was shaped by elevated cross-asset volatility.\n\n"
            "- Risk limits remained the primary portfolio constraint.\n"
            "- Gross exposure was reduced as correlations increased.\n"
            "- The strategy continues to seek asymmetric opportunities across asset classes."
        )
        report.save()
        set_manual_snapshot(
            report,
            Decimal("4.190858333333334"),
            "Deterministic legacy workbook fixture for the 2026 Q1 smoke report.",
            user,
        )
        try:
            files = generate_report_files(report, user)
            if options["finalize"]:
                finalize_report(report, user)
        except ReportGenerationError as exc:
            raise CommandError(str(exc)) from exc
        for generated in files:
            self.stdout.write(
                f"{generated.file_type}: {generated.absolute_path} ({generated.sha256})"
            )
        self.stdout.write(self.style.SUCCESS(f"Generated {report} status={report.status}"))
