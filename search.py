"""Rank a page's passages against a search, then pick the sentence to highlight.

This is a search, so the question asked of each passage is whether it is *about*
the search, not whether it answers it. An earlier version asked the
question-answering version and explicitly discounted topic matches, which buried
exactly the passages a search is for: a table cell reading "Saturn Awards"
scored 0.43 for the search "awards". Asking the topical question scores it 0.87.

Short instructions also beat long ones, both in speed and in separation, so both
questions here are one line.

Scoring is batched. See scorer.py for why that is not just a loop.
"""
from sentences import sentence_spans

MAX_QUERY = 400
MAX_BLOCKS = 160
MAX_BLOCK_CHARS = 2200
MAX_TOTAL_CHARS = 60000

# A fixed cutoff cannot work here, because the score scale moves with what a
# passage is made of. The bare cell "Teen Choice Awards" scores 0.874 for the
# search "awards"; the whole row, which also carries a year, a nominee and a
# result, scores 0.531 for the same search while being the better passage to
# show. A fixed 0.58 returned the fragment and nothing at all for the row. The
# cutoff is therefore relative to the best passage on the page, with a floor so
# that a page about nothing relevant still returns nothing.
FLOOR = 0.25
RATIO = 0.45
MAX_MATCHES = 25  # each match costs a sentence pass

ABOUT = "Is this passage about the search topic?"
FOCUS = "Is this sentence the part that is about the search topic?"


class SearchError(Exception):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.message, self.status = message, status


def validate(body):
    query = body.get("query") if isinstance(body, dict) else None
    if not isinstance(query, str) or not query.strip():
        raise SearchError("Enter something you want to find.")
    if len(query) > MAX_QUERY:
        raise SearchError(f"Keep your search under {MAX_QUERY} characters.")

    blocks = body.get("blocks")
    if not isinstance(blocks, list) or not blocks or len(blocks) > MAX_BLOCKS:
        raise SearchError(f"Search between 1 and {MAX_BLOCKS} passages at a time.")

    seen, total, clean = set(), 0, []
    for b in blocks:
        bid = b.get("id") if isinstance(b, dict) else None
        text = b.get("text") if isinstance(b, dict) else None
        if (not isinstance(bid, str) or bid in seen
                or not isinstance(text, str) or not text.strip()
                or len(text) > MAX_BLOCK_CHARS):
            raise SearchError("The document contains an invalid passage.")
        seen.add(bid)
        total += len(text)
        clean.append({"id": bid, "text": text})
    if total > MAX_TOTAL_CHARS:
        raise SearchError(f"This document is too long. Try a section under {MAX_TOTAL_CHARS:,} characters.")
    return {"query": query.strip(), "blocks": clean}


def checked(values, expected):
    if len(values) != expected or any(
            not isinstance(v, (int, float)) or not 0 <= v <= 1 for v in values):
        raise SearchError("Laya returned an incomplete evaluation. Please try again.", 502)
    return values


def cutoff_for(top, floor=FLOOR, ratio=RATIO):
    return max(floor, top * ratio)


def search(body, score, floor=FLOOR):
    """`score(states, instructions) -> [probability]`, batched. Injected for tests."""
    request = validate(body)
    query = request["query"]

    blocks = [b for b in request["blocks"] if sentence_spans(b["text"])]
    if not blocks:
        return {"scores": [], "matches": [], "cutoff": floor}

    # One pass over every passage on the page.
    probabilities = checked(
        score([{"search": query, "passage": b["text"]} for b in blocks], ABOUT), len(blocks))
    scores = [{"id": b["id"], "text": b["text"], "probability": round(p, 4)}
              for b, p in zip(blocks, probabilities)]
    scores.sort(key=lambda s: -s["probability"])

    # A second pass, over the sentences of the matches only.
    cutoff = cutoff_for(scores[0]["probability"], floor)
    hits = [s for s in scores if s["probability"] >= cutoff][:MAX_MATCHES]
    sentences = [sentence_spans(h["text"]) for h in hits]
    states, spans = [], []
    for hit, group in zip(hits, sentences):
        if len(group) > 1:
            for sentence in group:
                states.append({"search": query, "sentence": sentence["text"]})
                spans.append(sentence)

    picked = checked(score(states, FOCUS), len(states)) if states else []
    matches, at = [], 0
    for hit, group in zip(hits, sentences):
        if len(group) > 1:
            best = max(range(len(group)), key=lambda i: picked[at + i])
            focus = spans[at + best]
            at += len(group)
        else:
            focus = group[0]
        matches.append({"id": hit["id"], "probability": hit["probability"], "focus": focus})

    return {
        "scores": [{"id": s["id"], "probability": s["probability"]} for s in scores],
        "matches": matches,
        "cutoff": round(cutoff, 4),
    }
