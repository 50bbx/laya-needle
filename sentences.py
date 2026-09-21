"""Split a passage into sentences, with offsets the browser can trust.

Offsets are UTF-16 code units, because that is what DOM ranges and JavaScript
string indices use. Python indexes by code point, so anything outside the BMP
(emoji, rare CJK) would shift the highlight without this conversion.
"""
import re

# A boundary is terminal punctuation, optional closing quotes/brackets, then space.
_BOUNDARY = re.compile(r'(?<=[.!?…])["\'”’)\]]*\s+')

# Splitting after these would cut mid-sentence.
_ABBREV = {
    "mr", "mrs", "ms", "dr", "prof", "sr", "jr", "st", "vs", "etc", "eg", "ie",
    "no", "fig", "al", "inc", "ltd", "co", "approx", "dept", "est", "min", "max",
}


def _u16(text: str) -> int:
    return len(text.encode("utf-16-le")) // 2


def _is_abbreviation(text: str, end: int) -> bool:
    word = re.search(r'([A-Za-z.]+)\.$', text[:end].rstrip())
    if not word:
        return False
    token = word.group(1).rstrip(".").lower()
    return token in _ABBREV or (len(token) == 1 and token.isalpha())


def sentence_spans(text: str):
    """Return [{start, end, text}] over `text`, with UTF-16 offsets."""
    cuts, position = [0], 0
    for match in _BOUNDARY.finditer(text):
        if not _is_abbreviation(text, match.start()):
            cuts.append(match.end())
    cuts.append(len(text))

    spans = []
    for start, end in zip(cuts, cuts[1:]):
        chunk = text[start:end]
        lead = len(chunk) - len(chunk.lstrip())
        trail = len(chunk) - len(chunk.rstrip())
        a, b = start + lead, end - trail
        if b > a:
            spans.append({"start": _u16(text[:a]), "end": _u16(text[:b]), "text": text[a:b]})
    return spans
