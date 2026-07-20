from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django  # noqa: E402

django.setup()

from navapp.services.reports import audit_docx_package  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit a generated NAV report DOCX package.")
    parser.add_argument("path", type=Path)
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    result = audit_docx_package(arguments.path)
    rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
    print(rendered, end="")
    if arguments.output:
        arguments.output.parent.mkdir(parents=True, exist_ok=True)
        arguments.output.write_text(rendered, encoding="utf-8")
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    sys.exit(main())
