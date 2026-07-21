import django.core.validators
from django.db import migrations, models


def populate_report_month(apps, schema_editor):
    report_model = apps.get_model("navapp", "QuarterlyReport")
    for report in report_model.objects.only("pk", "quarter").iterator():
        report.report_month = report.quarter * 3
        report.save(update_fields=["report_month"])


class Migration(migrations.Migration):
    dependencies = [
        ("navapp", "0004_alter_fund_brand_colour_override_and_more"),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name="quarterlyreport",
            name="unique_report_version",
        ),
        migrations.RemoveIndex(
            model_name="quarterlyreport",
            name="navapp_quar_share_c_53d5bd_idx",
        ),
        migrations.AddField(
            model_name="quarterlyreport",
            name="report_type",
            field=models.CharField(
                choices=[("MONTHLY", "Monthly"), ("QUARTERLY", "Quarterly")],
                default="QUARTERLY",
                max_length=12,
            ),
        ),
        migrations.AddField(
            model_name="quarterlyreport",
            name="report_month",
            field=models.PositiveSmallIntegerField(null=True),
        ),
        migrations.RunPython(populate_report_month, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="quarterlyreport",
            name="report_month",
            field=models.PositiveSmallIntegerField(
                validators=[
                    django.core.validators.MinValueValidator(1),
                    django.core.validators.MaxValueValidator(12),
                ]
            ),
        ),
        migrations.AlterModelOptions(
            name="quarterlyreport",
            options={"ordering": ["-report_date", "-version"]},
        ),
        migrations.AddIndex(
            model_name="quarterlyreport",
            index=models.Index(
                fields=["share_class", "report_type", "report_date", "status"],
                name="navapp_report_period_idx",
            ),
        ),
        migrations.AddConstraint(
            model_name="quarterlyreport",
            constraint=models.UniqueConstraint(
                fields=("share_class", "report_type", "report_date", "version"),
                name="unique_report_period_version",
            ),
        ),
    ]
