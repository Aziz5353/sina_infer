import re

# Order matters: labelled DOBs and full dates go before the bare-number patterns
# so a date like 1980-03-12 is not half-matched as a phone number.
_PHI_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("email", re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")),
    (
        "dob",
        re.compile(
            r"\b(?:DOB|D\.O\.B\.?|date\s+of\s+birth|born(?:\s+on)?)\s*[:\-]?\s*"
            r"[\w./\-, ]{0,20}?\d{4}\b",
            re.IGNORECASE,
        ),
    ),
    (
        "date",
        re.compile(
            r"\b(?:\d{1,2}[/.\-]\d{1,2}[/.\-]\d{4}|\d{4}[/.\-]\d{1,2}[/.\-]\d{1,2})\b"
        ),
    ),
    (
        "date",
        re.compile(
            r"\b\d{1,2}\s+(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?,?\s+\d{4}\b"
            r"|\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s+\d{1,2},?\s+\d{4}\b",
            re.IGNORECASE,
        ),
    ),
    # Saudi national ID (starts with 1) and Iqama (starts with 2): 10 digits.
    ("national_id", re.compile(r"(?<!\d)[12]\d{9}(?!\d)")),
    # International numbers: +966 5x xxx xxxx, 00966..., +1 (555) 123-4567.
    ("phone", re.compile(r"(?:\+|\b00)\d[\d\s\-()]{6,}\d")),
    # Local Saudi numbers: 05xxxxxxxx / 01x xxx xxxx, with optional separators.
    ("phone", re.compile(r"(?<!\d)0\d{2}[\s\-]?\d{3}[\s\-]?\d{4}(?!\d)")),
    # NANP-style 555-123-4567.
    ("phone", re.compile(r"(?<!\d)\d{3}[\s\-.]\d{3}[\s\-.]\d{4}(?!\d)")),
)

_WHITESPACE_RE = re.compile(r"\s{2,}")


def scrub_phi(text: str) -> tuple[str, list[str]]:
    """Strip emails, phone numbers, Saudi national/Iqama IDs and dates of birth.

    Returns the scrubbed text and the kinds of identifiers that were removed
    (one entry per match), so callers can log counts without logging the values.
    """
    removed: list[str] = []
    for kind, pattern in _PHI_PATTERNS:
        text, n = pattern.subn(" ", text)
        removed.extend([kind] * n)
    return _WHITESPACE_RE.sub(" ", text).strip(), removed
