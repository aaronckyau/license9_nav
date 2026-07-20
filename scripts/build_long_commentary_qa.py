from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django  # noqa: E402

django.setup()

from navapp.models import QuarterlyReport  # noqa: E402
from navapp.services.reports import build_builtin_docx, build_current_snapshot  # noqa: E402


def main() -> None:
    report = QuarterlyReport.objects.select_related("fund", "share_class").get(pk=1)
    snapshot = build_current_snapshot(report)
    paragraph = (
        "During the quarter, portfolio positioning was actively adjusted as volatility "
        "moved across asset classes. Risk limits, liquidity, and concentration were reviewed "
        "continuously, while exposures were sized with regard to the strategy's medium-term "
        "objectives. The manager remains focused on disciplined implementation, drawdown "
        "control, and preserving flexibility as market conditions evolve."
    )
    snapshot["commentary"]["markdown"] = "\n\n".join(
        f"Quarterly review {index}. {paragraph}" for index in range(1, 19)
    )
    snapshot["commentary"]["author"] = "Archie Ma, Portfolio Manager"
    output_path = ROOT / "artifacts" / "report-render" / "XSQ_Long_Commentary_QA.docx"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    build_builtin_docx(
        snapshot,
        ROOT / "media" / "reports" / "1" / "v1" / "nav-chart.png",
        output_path,
    )
    print(output_path)


if __name__ == "__main__":
    main()
