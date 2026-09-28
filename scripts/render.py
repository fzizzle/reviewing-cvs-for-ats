#!/usr/bin/env python3
"""Render an HTML CV to PDF with headless Chrome and print the page count.

Usage: cvats render CV.html [OUT.pdf]      (default OUT: CV.pdf next to the HTML)
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from cvlib import cli, page_count, render_pdf  # noqa: E402


@cli
def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("html")
    ap.add_argument("pdf", nargs="?")
    a = ap.parse_args(argv)
    out = Path(a.pdf) if a.pdf else Path(a.html).with_suffix(".pdf")
    render_pdf(a.html, out)
    print(f"{out}  pages={page_count(out)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
