"""Run every analysis module and write analysis/output/computed_findings.md.

Usage:
    python -m ecommerce_intel.analysis.run_all
"""

from __future__ import annotations

import logging
import sys
from datetime import datetime

from ..config import REPO_ROOT
from . import categories, delivery, payments, retention, revenue, reviews, sellers
from ._common import get_conn

log = logging.getLogger("ecommerce_intel.analysis")

MODULES = [
    revenue,
    categories,
    sellers,
    delivery,
    payments,
    reviews,
    retention,
]

OUTPUT_PATH = REPO_ROOT / "analysis" / "output" / "computed_findings.md"


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    del argv
    conn = get_conn()
    try:
        sections = [module.run(conn) for module in MODULES]
    finally:
        conn.close()

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    body = "\n\n".join(sections)
    OUTPUT_PATH.write_text(
        "# Computed findings (generated — do not edit by hand)\n\n"
        f"Generated {datetime.now():%Y-%m-%d %H:%M:%S} by "
        "`python -m ecommerce_intel.analysis.run_all`.\n\n" + body + "\n",
        encoding="utf-8",
    )
    log.info("wrote %s", OUTPUT_PATH.relative_to(REPO_ROOT))
    print(body)
    return 0


if __name__ == "__main__":
    sys.exit(main())
