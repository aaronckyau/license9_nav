from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from navapp.models import ShareClass
from navapp.services.imports import ImportValidationError, import_rows, parse_legacy_xsq


class Command(BaseCommand):
    help = "Safely preview or import the supplied legacy XSQ NAV workbook."

    def add_arguments(self, parser):
        parser.add_argument("--file", required=True, type=Path)
        parser.add_argument("--share-class-code", default="MANU")
        parser.add_argument("--fund-code", default="xsq")
        parser.add_argument("--sheet", default="2026 Mar (monthly)")
        mode = parser.add_mutually_exclusive_group(required=True)
        mode.add_argument("--dry-run", action="store_true")
        mode.add_argument("--commit", action="store_true")
        parser.add_argument("--confirm-first-period", action="store_true")

    def handle(self, *args, **options):
        path = options["file"]
        if not path.is_file():
            raise CommandError(f"Workbook not found: {path}")
        try:
            share_class = ShareClass.objects.get(
                fund__short_code=options["fund_code"], code=options["share_class_code"]
            )
            rows = parse_legacy_xsq(path, options["sheet"])
            result = import_rows(
                share_class=share_class,
                rows=rows,
                commit=options["commit"],
                acknowledge_first_period=options["confirm_first_period"],
            )
        except ShareClass.DoesNotExist as exc:
            raise CommandError(
                "Share class not found; run seed_demo first or provide --fund-code and "
                "--share-class-code."
            ) from exc
        except ImportValidationError as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(
            self.style.SUCCESS(
                f"{result['mode']}: proposed={result['proposed']} "
                f"created={result['created']} skipped={result['skipped']}"
            )
        )
        for row in rows:
            for warning in row.warnings:
                self.stdout.write(self.style.WARNING(f"{row.valuation_month}: {warning}"))
