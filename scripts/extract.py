#!/usr/bin/env python3
"""Show what different ATS parsers 'see': extract a CV's text with every available parser.

Usage: cvats extract CV.(pdf|html|docx|txt|md) [--out DIR]
Without --out, prints word counts and the first parser's text. With --out, writes <parser>.txt files.
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from cvlib import cli, docx_header_footer_text, docx_textbox_text, extract_all  # noqa: E402


@cli
def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cv")
    ap.add_argument("--out")
    a = ap.parse_args(argv)
    texts, pages = extract_all(a.cv)
    print(f"pages: {pages if pages is not None else 'n/a'}")
    for name, text in texts.items():
        print(f"{name:12} {len(text.split()):5} words")
        if a.out:
            Path(a.out).mkdir(parents=True, exist_ok=True)
            (Path(a.out) / f"{name}.txt").write_text(text, encoding="utf-8")
    if a.cv.lower().endswith(".docx") and docx_header_footer_text(a.cv):
        print("WARNING: text in the Word header/footer (many ATS skip it):", docx_header_footer_text(a.cv))
    if a.cv.lower().endswith(".docx") and docx_textbox_text(a.cv):
        print("WARNING: text in Word text boxes (many ATS skip it):", docx_textbox_text(a.cv))
    if not a.out:
        name, text = next(iter(texts.items()))
        print(f"\n--- {name} ---\n{text}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
