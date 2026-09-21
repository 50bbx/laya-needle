import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from search import ABOUT, ALWAYS, FLOOR, FOCUS, MAX_MATCHES, RATIO, search, take, validate, SearchError

DOC = [
    {"id": "b0", "text": "Our plan costs $29 per month. Annual billing saves 20%."},
    {"id": "b1", "text": "You may cancel any time. We do not refund unused time."},
    {"id": "b2", "text": "Our offices are in Berlin and Lisbon."},
]


def model(passages, sentences=None):
    """Stands in for Laya. Keys are the first six characters of the scored text."""
    calls = []

    def score(states, instructions):
        calls.append((instructions, len(states)))
        table = passages if instructions == ABOUT else (sentences or {})
        key = "passage" if instructions == ABOUT else "sentence"
        return [table.get(s[key][:6], 0.0) for s in states]

    score.calls = calls
    return score


def fails(body, fragment, score=None):
    try:
        search(body, score or model({}))
    except SearchError as e:
        assert fragment in e.message, f"expected {fragment!r} in {e.message!r}"
        return
    raise AssertionError(f"expected SearchError containing {fragment!r}")


score = model({"Our pl": 0.04, "You ma": 0.93, "Our of": 0.02},
              {"You ma": 0.2, "We do ": 0.9})
result = search({"query": "cancelling", "blocks": DOC}, score)

assert [s["id"] for s in result["scores"]] == ["b1", "b0", "b2"], "ranked by probability"
assert [m["id"] for m in result["matches"]] == ["b1"], "only above the cutoff"
assert result["matches"][0]["focus"]["text"] == "We do not refund unused time.", "highest sentence wins"
assert "text" not in result["scores"][0], "passage text is not echoed back"

focus = result["matches"][0]["focus"]
assert DOC[1]["text"][focus["start"]:focus["end"]] == focus["text"], "offsets index the passage"

# Every passage is scored in ONE call, and sentences only for the match.
assert score.calls == [(ABOUT, 3), (FOCUS, 2)], f"expected two batched calls, got {score.calls}"

# A single-sentence match needs no sentence pass at all.
single = model({"Just o": 0.9})
out = search({"query": "q", "blocks": [{"id": "b0", "text": "Just one sentence here"}]}, single)
assert single.calls == [(ABOUT, 1)], f"no focus call expected, got {single.calls}"
assert out["matches"][0]["focus"]["text"] == "Just one sentence here"

# Several matches keep their own sentences apart.
many = model({"Alpha ": 0.9, "Bravo ": 0.8},
             {"Alpha ": 0.1, "First ": 0.9, "Bravo ": 0.2, "Second": 0.95})
out = search({"query": "q", "blocks": [
    {"id": "b0", "text": "Alpha one. First pick here."},
    {"id": "b1", "text": "Bravo two. Second pick here."}]}, many)
assert [m["focus"]["text"] for m in out["matches"]] == ["First pick here.", "Second pick here."], \
    "each match picks from its own sentences"

# A short or malformed score list is an error, not a silent zero.
fails({"query": "q", "blocks": DOC}, "incomplete", lambda states, ins: [0.9])
fails({"query": "q", "blocks": DOC}, "incomplete", lambda states, ins: [1.4] * 3)

fails({"query": "  ", "blocks": DOC}, "Enter something")
fails({"query": "x" * 401, "blocks": DOC}, "under 400")
fails({"query": "q", "blocks": []}, "between 1 and 160")
fails({"query": "q", "blocks": [{"id": "b0", "text": "a"}, {"id": "b0", "text": "b"}]}, "invalid passage")
fails({"query": "q", "blocks": [{"id": "b0", "text": "x" * 2201}]}, "invalid passage")
fails({"query": "q", "blocks": [{"id": f"b{i}", "text": "x" * 1000} for i in range(61)]}, "too long")

assert validate({"query": " spaced ", "blocks": DOC})["query"] == "spaced", "query is trimmed"

# A search shows a ranked list. The top few are always shown, because a passage
# ranked 3rd of 120 is an answer even when its score is low.
def ranked(*probabilities):
    return [{"id": f"b{i}", "probability": p} for i, p in enumerate(probabilities)]

assert [s["id"] for s in take(ranked(0.9, 0.8, 0.7, 0.6))] == ["b0", "b1", "b2", "b3"], "close contenders kept"
assert [s["id"] for s in take(ranked(0.9, 0.2, 0.15, 0.1))] == ["b0", "b1", "b2"], \
    "the top few survive a steep drop-off"
assert [s["id"] for s in take(ranked(0.9, 0.5, 0.44, 0.1))] == ["b0", "b1", "b2"], \
    "past the first few, only what is close to the best"
assert [s["id"] for s in take(ranked(0.1, 0.9, 0.5))] == ["b1", "b2", "b0"], \
    "take orders by score, whatever order it is given"
assert take(ranked(0.04, 0.01)) == [], "a page scoring near zero shows nothing"
assert len(take(ranked(*([0.9] * 20)))) == MAX_MATCHES, f"capped at {MAX_MATCHES}"
assert len(take(ranked(0.9, 0.06))) == 2, "the floor, not ALWAYS, decides when there are too few"

# The regression this rule exists for: "Budget · $175 million" ranks 3rd of 120
# for the search "cost" at 0.277, and used to be dropped by a fixed cutoff.
page = ranked(0.75, 0.67, 0.277, 0.2, 0.15)
assert "b2" in [s["id"] for s in take(page)], "a good rank with a low score is still shown"

low = model({"Aaaaaa": 0.40, "Bbbbbb": 0.36, "Cccccc": 0.01})
out = search({"query": "q", "blocks": [
    {"id": "b0", "text": "Aaaaaa is one thing"},
    {"id": "b1", "text": "Bbbbbb is another"},
    {"id": "b2", "text": "Cccccc is unrelated"}]}, low)
assert [m["id"] for m in out["matches"]] == ["b0", "b1"], \
    f"a low-scoring page still returns its best, and drops what is under the floor, " \
    f"got {[m['id'] for m in out['matches']]}"

nothing = model({"Aaaaaa": 0.02, "Bbbbbb": 0.01})
out = search({"query": "q", "blocks": [
    {"id": "b0", "text": "Aaaaaa is one thing"},
    {"id": "b1", "text": "Bbbbbb is another"}]}, nothing)
assert out["matches"] == [], "nothing above the floor means no matches"

flat = model({f"Blk{i:03}": 0.9 for i in range(40)})
out = search({"query": "q", "blocks": [
    {"id": f"b{i}", "text": f"Blk{i:03} first sentence. Second sentence here."} for i in range(40)]}, flat)
assert len(out["matches"]) == MAX_MATCHES, f"capped at {MAX_MATCHES}, got {len(out['matches'])}"
assert len(out["scores"]) == 40, "every passage is still ranked"

# This is a search, not question answering. Guard the wording that regressed.
assert "about" in ABOUT.lower() and "answer" not in ABOUT.lower(), \
    "the passage question must ask what the passage is about, not what it answers"

print("search: all passed")
