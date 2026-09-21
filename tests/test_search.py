import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from search import search, validate, focus_sentence, SearchError

DOC = [
    {"id": "b0", "text": "Our plan costs $29 per month. Annual billing saves 20%."},
    {"id": "b1", "text": "You may cancel any time. We do not refund unused time."},
    {"id": "b2", "text": "Our offices are in Berlin and Lisbon."},
]


def model(passage_scores, sentence_scores=None):
    """Stands in for Laya. Keys are the first six characters of the scored text."""
    calls = []

    def predict(state, questions):
        if "passage" in state:
            calls.append(("passage", state["passage"][:6]))
            return {"relevant": {"noul": passage_scores[state["passage"][:6]]}}
        calls.append(("sentence", state["sentence"][:6]))
        return {"specific": {"noul": (sentence_scores or {}).get(state["sentence"][:6], 0.5)}}

    predict.calls = calls
    return predict


def fails(body, fragment, predict=None):
    try:
        search(body, predict or model({}))
    except SearchError as e:
        assert fragment in e.message, f"expected {fragment!r} in {e.message!r}"
        return
    raise AssertionError(f"expected SearchError containing {fragment!r}")


predict = model({"Our pl": 0.04, "You ma": 0.93, "Our of": 0.02},
                {"You ma": 0.2, "We do ": 0.9})
result = search({"query": "what if I cancel?", "blocks": DOC}, predict)

assert [s["id"] for s in result["scores"]] == ["b1", "b0", "b2"], "ranked by probability"
assert [m["id"] for m in result["matches"]] == ["b1"], "only above threshold"
assert result["matches"][0]["focus"]["text"] == "We do not refund unused time.", "highest sentence wins"
assert "text" not in result["scores"][0], "passage text is not echoed back"

focus = result["matches"][0]["focus"]
assert DOC[1]["text"][focus["start"]:focus["end"]] == focus["text"], "offsets index the passage"

# Focus must cost nothing on passages that did not match.
scored = [c for c in predict.calls if c[0] == "sentence"]
assert len(scored) == 2, f"only the matching passage's sentences are scored, got {scored}"

# A single-sentence passage needs no sentence scoring at all.
single = model({"Just o": 0.9})
search({"query": "q", "blocks": [{"id": "b0", "text": "Just one sentence here"}]}, single)
assert not [c for c in single.calls if c[0] == "sentence"], "no sentence calls for one sentence"

# A missing or out-of-range probability is an error, not a silent zero.
fails({"query": "q", "blocks": [DOC[0]]}, "incomplete", lambda s, q: {"relevant": {}})
fails({"query": "q", "blocks": [DOC[0]]}, "incomplete", lambda s, q: {"relevant": {"noul": 1.4}})

fails({"query": "  ", "blocks": DOC}, "Enter something")
fails({"query": "x" * 401, "blocks": DOC}, "under 400")
fails({"query": "q", "blocks": []}, "between 1 and 160")
fails({"query": "q", "blocks": [{"id": "b0", "text": "a"}, {"id": "b0", "text": "b"}]}, "invalid passage")
fails({"query": "q", "blocks": [{"id": "b0", "text": "x" * 2201}]}, "invalid passage")
fails({"query": "q", "blocks": [{"id": f"b{i}", "text": "x" * 1000} for i in range(61)]}, "too long")

assert validate({"query": " spaced ", "blocks": DOC})["query"] == "spaced", "query is trimmed"
assert focus_sentence("q", "", model({})) is None, "empty passage has no focus"

print("search: all passed")
