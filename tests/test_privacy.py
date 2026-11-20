"""Every tracked file must hold only fictional contact details.

Phones must sit in Ofcom/ARCEP drama ranges; emails must end @example.com.
"""
import pathlib
import re
import subprocess

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]

PHONE = re.compile(r"\+?\d[\d\s().-]{6,}\d")
EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
# Digit prefixes (no spaces or "+") of the fictional ranges; the rest of the number is free.
FICTIONAL = (
    "07700900", "447700900",      # UK mobile drama range 07700 900xxx
    "02079460", "442079460",      # UK London 020 7946 0xxx
    "01614960", "441614960",      # UK Manchester 0161 496 0xxx
    "3363998",                    # FR mobile +33 6 39 98 xx xx
    "019900",                     # FR Paris 01 99 00 xx xx
)
YEAR = re.compile(r"(?:19|20)\d{2}")


def is_date_like(s):
    """Pure year lists, ranges or ISO/numeric dates: 4-digit years plus at most 2-digit parts."""
    groups = re.findall(r"\d+", s)
    return any(YEAR.fullmatch(g) for g in groups) and all(YEAR.fullmatch(g) or len(g) <= 2 for g in groups)


def phone_problems(text):
    out = []
    for m in PHONE.finditer(text):
        digits = re.sub(r"\D", "", m.group())
        if len(digits) < 9 or is_date_like(m.group()):
            continue
        if not digits.startswith(FICTIONAL):
            out.append(m.group().strip())
    return out


def email_problems(text):
    return [e for e in EMAIL.findall(text) if not e.lower().endswith("@example.com")]


def tracked_files():
    try:
        out = subprocess.run(["git", "ls-files", "--cached", "--others", "--exclude-standard"],
                             cwd=ROOT, capture_output=True, text=True, check=True).stdout
    except (OSError, subprocess.CalledProcessError):
        pytest.skip("not a git checkout")
    return [ROOT / f for f in out.splitlines() if (ROOT / f).is_file()]


def test_detector_flags_real_looking_contacts():
    real_fr = "+33 7 " + "11 22 33 44"  # built at runtime so this file itself stays clean
    real_uk = "07" + "911 " + "123456"
    assert phone_problems(f"call {real_fr} or {real_uk}") == [real_fr, real_uk]
    assert email_problems("x " + "someone" + "@" + "gmail.com") == ["someone" + "@" + "gmail.com"]


def test_detector_accepts_fictional_ranges_and_dates():
    text = ("+44 7700 900123 · 07700 900123 · 020 7946 0123 · +44 20 7946 0123 · 0161 496 0123 · "
            "+44 161 496 0123 · +33 6 39 98 12 34 · 01 99 00 12 34 · jane@example.com\n"
            "2019 - 2021 2022 2023 · 2026-09-28 · 03.2019 - 04.2021 · 2019 2020 2021 2022")
    assert phone_problems(text) == [] and email_problems(text) == []


def file_text(path):
    """Text of a tracked file; PDFs and Word files are extracted (body, header/footer, text boxes)
    so their contact details are checked too. None for other binary files."""
    import cvlib
    if path.suffix.lower() == ".pdf":
        return "\n".join(cvlib.PDF_PARSERS["pymupdf"](str(path)).splitlines())
    if path.suffix.lower() == ".docx":
        return "\n".join([cvlib.docx_text(path), cvlib.docx_header_footer_text(path) or "",
                          cvlib.docx_textbox_text(path) or ""])
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return None


def test_binary_cvs_are_extracted_and_scanned():
    # The .pdf/.docx fixtures are generated (gitignored), but a binary CV committed later must be
    # scanned, not skipped as undecodable: check the extraction path on the generated ones.
    fixtures = [p for p in (ROOT / "tests" / "fixtures").iterdir() if p.suffix.lower() in (".pdf", ".docx")]
    if not fixtures:
        pytest.skip("binary fixtures not built")
    for path in fixtures:
        text = file_text(path)
        assert text and text.strip(), path
        assert phone_problems(text) == [] and email_problems(text) == [], path


def test_tracked_files_hold_only_fictional_contacts():
    found = []
    for path in tracked_files():
        text = file_text(path)
        if text is None:
            continue
        rel = path.relative_to(ROOT)
        found += [f"{rel}: phone {p!r}" for p in phone_problems(text)]
        found += [f"{rel}: email {e!r}" for e in email_problems(text)]
    assert found == []
