import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from sentences import sentence_spans


def check(text, expected_texts):
    spans = sentence_spans(text)
    got = [s["text"] for s in spans]
    assert got == expected_texts, f"{text!r}\n  got      {got}\n  expected {expected_texts}"
    for s in spans:
        # Offsets must slice the original the way JavaScript would.
        js = text.encode("utf-16-le")
        sliced = js[s["start"] * 2:s["end"] * 2].decode("utf-16-le")
        assert sliced == s["text"], f"offset mismatch: {sliced!r} != {s['text']!r}"


check("One thing. Two things.", ["One thing.", "Two things."])
check("Only one sentence here", ["Only one sentence here"])
check("Ask Dr. Smith about it. Then leave.", ["Ask Dr. Smith about it.", "Then leave."])
check("Costs approx. 4 euro. Fine.", ["Costs approx. 4 euro.", "Fine."])
check("Really? Yes! Sure.", ["Really?", "Yes!", "Sure."])
check("Emoji 🎉 first. Second one.", ["Emoji 🎉 first.", "Second one."])
check('He said "go now." She left.', ['He said "go now."', "She left."])
check("  padded.  ", ["padded."])
assert sentence_spans("") == []
assert sentence_spans("   ") == []

print("sentences: all passed")
