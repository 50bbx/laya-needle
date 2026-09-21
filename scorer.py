"""Score many passages in one forward pass.

`Agent.predict` encodes one state per call, so a 138-passage page meant 138
calls. Laya's own collate takes a list of items that each carry their own
sequence, so the states can share a pass. Two things then dominate:

  Padding. Every item in a batch is padded to the longest one, so a 2,200-char
  paragraph next to a three-word table cell wastes most of the batch. Sorting by
  encoded length before batching took padding waste from 61% to 11%.

  Length. A search asks what a passage is about, and the opening says that. Only
  the first CLIP characters are encoded.

This reaches into laya.common, which is not a public API, so `available` reports
whether the import worked and the server falls back to one call per passage.
"""
import numpy as np
import torch

CLIP = 400      # characters of a passage encoded for scoring
BATCH = 32

try:
    from laya.common import QTYPES, build_sequence, collate_items, temp_bucket
    available = True
except ImportError:  # a laya release moved them; the caller falls back
    available = False


class Scorer:
    def __init__(self, agent, clip=CLIP, batch=BATCH):
        self.agent, self.clip, self.batch = agent, clip, batch
        self.noul = QTYPES["noul"]
        self.temperature = agent.temperature_by_options.get(
            temp_bucket(self.noul, 2), agent.temperature[self.noul])

    def _encode(self, state, instructions):
        text = state.get("passage") or state.get("sentence") or ""
        field = "passage" if "passage" in state else "sentence"
        ids, markers = build_sequence(
            self.agent.tok, {**state, field: text[: self.clip]},
            {"t": "noul", "ins": instructions, "crit": None},
            self.agent.cfg.get("max_len", 512), self.agent.cfg.get("head_max_len", 192))
        return {"ids": ids, "markers": markers, "qtype": self.noul}

    def score(self, states, instructions):
        """Probability, per state, that the answer to `instructions` is yes."""
        if not states:
            return []
        items = [(i, self._encode(s, instructions)) for i, s in enumerate(states)]
        items.sort(key=lambda pair: len(pair[1]["ids"]))

        out = [0.0] * len(states)
        for start in range(0, len(items), self.batch):
            chunk = items[start: start + self.batch]
            b = collate_items([[item for _, item in chunk]], self.agent.tok.pad_token_id)
            with torch.no_grad():
                logits, _ = self.agent.model(
                    b["input_ids"].to(self.agent.device),
                    b["attention_mask"].to(self.agent.device),
                    b["marker_pos"].to(self.agent.device),
                    b["marker_mask"].to(self.agent.device),
                    b["qtype"].to(self.agent.device))
            logits = logits.float().cpu().numpy()
            for row, (index, _) in enumerate(chunk):
                z = logits[row, :2] / max(1e-3, float(self.temperature))
                p = np.exp(z - z.max())
                out[index] = float(p[1] / p.sum())
        return out


def fallback(agent):
    """One call per state, for when laya.common has moved."""
    def score(states, instructions):
        return [float(agent.predict(s, {"q": {"type": "noul", "instructions": instructions}})
                      ["answers"]["q"]["noul"]) for s in states]
    return score
