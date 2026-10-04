import re
import unicodedata

_ARABIC_DIACRITICS_RE = re.compile(r"[ً-ْٰ]")


def normalize_arabic(text: str) -> str:
    """Must mirror the normalization used at index time in the ingestion pipeline."""
    if not text:
        return text
    text = unicodedata.normalize("NFKC", text)
    text = text.replace("ـ", "")
    text = _ARABIC_DIACRITICS_RE.sub("", text)
    text = text.replace("أ", "ا").replace("إ", "ا").replace("آ", "ا")
    text = text.replace("ى", "ي")
    return text.strip()
