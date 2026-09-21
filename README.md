# laya-needle

Find what you mean on a webpage, not what you typed. Ask in your own words, and
the matching passages light up in the page with the key sentence picked out.

Everything runs on your machine. [Laya](https://github.com/NandhaKishorM/laya)
is a 322M-parameter decision model that scores each passage in a single forward
pass. No API key, no account, no cloud, no per-search cost. After the first run
it works offline.

This is a port of [Needle](https://github.com/Shubhamsaboo/awesome-llm-apps/tree/main/advanced_llm_apps/needle),
which does the same thing with TypeSafe's hosted Jev model through Vercel AI
Gateway. See [Differences from Needle](#differences-from-needle).

---

## Install

Needs Python 3.10+, about 700 MB of disk for the weights, and Chrome. A GPU is
optional. Apple silicon, NVIDIA and plain CPU all work.

```bash
git clone https://github.com/50bbx/laya-needle
cd laya-needle
uv venv --python 3.12 && uv pip install -e .
```

No `uv`? Use `python3 -m venv .venv && .venv/bin/pip install -e .` instead.

## Run the server

```bash
.venv/bin/python server.py
```

It serves **`http://127.0.0.1:8787`**, the default the extension expects. The
first run downloads the weights and takes a few minutes. After that it is ready
in about 20 seconds. Leave it running while you use the extension.

```
laya-needle listening on http://127.0.0.1:8787 (threshold 0.58)
loading laya (multilingual); the first run downloads weights and takes a few minutes
ready on mps in 21.8s
```

## Install the extension

Download **`laya-needle-extension.zip`** from
[Releases](https://github.com/50bbx/laya-needle/releases), or build it yourself
with `python scripts/package_extension.py`. You can also skip the zip and point
Chrome straight at the `extension/` folder in this repo.

1. Unzip it into a folder you will keep. Chrome reads that folder every time it
   starts, so do not delete it.
2. Open `chrome://extensions` and turn on **Developer mode**.
3. Click **Load unpacked** and select the folder containing `manifest.json`.
4. Pin laya-needle from the puzzle-piece menu.

The settings page opens on install. The server URL is already
`http://127.0.0.1:8787`. Click **Test connection** to confirm, then **Save
connection** and allow the permission prompt.

## Use it

Open any normal webpage and press **Cmd+Shift+F** (**Ctrl+Shift+F** on Windows
and Linux), or click the pinned icon. Type what you mean, such as "what happens
if I cancel?" or "costs beyond the advertised price".

Matching passages get a pale highlight, the sentence that actually answers gets
a bright one, and **↑ / ↓** jump between matches. **Esc** closes it.

---

## Defaults

| | |
|---|---|
| Endpoint | `http://127.0.0.1:8787/api/search` |
| Health check | `http://127.0.0.1:8787/api/health` |
| Port | `8787`, override with `PORT=8788 python server.py` |
| Checkpoint | `multilingual`, override with `LAYA_NEEDLE_MODEL=english` |
| Match threshold | `0.58`, override with `LAYA_NEEDLE_THRESHOLD=0.75` |

The server binds to loopback only, so nothing on your network can reach it.

## Call it without the extension

```bash
curl -s -X POST localhost:8787/api/search -H 'content-type: application/json' -d '{
  "query": "what happens if I cancel?",
  "blocks": [
    {"id": "b0", "text": "Our standard plan costs $29 per month, billed monthly."},
    {"id": "b1", "text": "You may cancel at any time from the billing page. Cancellation takes effect at the end of the current billing period, and we do not issue partial refunds for unused time."}
  ]
}'
```

`matches` holds the passages at or above the threshold, sorted best first, each
with the `focus` sentence and its offsets into the original passage text.

```json
{
  "matches": [{
    "id": "b1",
    "probability": 0.9846,
    "focus": {
      "start": 50, "end": 170,
      "text": "Cancellation takes effect at the end of the current billing period, and we do not issue partial refunds for unused time."
    }
  }],
  "scores": [{"id": "b1", "probability": 0.9846}, {"id": "b0", "probability": 0.0127}],
  "threshold": 0.58, "elapsedMs": 138, "model": "multilingual"
}
```

## How good is it, honestly

Laya scores passages well and picks sentences less well.

**Passage relevance is strong.** On a support-document test the matching passage
scored 0.985 while every unrelated passage sat under 0.12. That is a wide, safe
margin.

**Short passages with word overlap are the weak spot.** Searching a Wikipedia
article for "why does the crema form?" ranks "Espresso con panna: espresso with
cream" above the sentence that explains crema. Navigation fragments and list
items are the usual offenders. If you get noise, raise
`LAYA_NEEDLE_THRESHOLD` toward `0.8`.

**Sentence selection had to be rebuilt.** Needle asks Jev to pick the key
sentence with one `choice` question. Laya's choice head is close to useless at
this: on a hand-labelled set of 8 passages it picked the right sentence **0
times**, almost always the first. Scoring each sentence with its own boolean
gets **7 of 8**. That is what this port does.

This is a 322M model on your laptop, not a frontier model in a datacentre. It is
free, private and fast. It is not as accurate as Jev.

## Speed

Measured on an M-series Mac, `multilingual` on MPS.

| page size | time |
|---|---|
| 10 passages | ~0.45 s |
| 160 passages (the cap) | ~4.5 s |

That is about 28 to 35 ms per passage. Laya reads at most 512 to 1024 tokens, so
passages are scored one at a time rather than in one batch. The key-sentence pass
only runs on passages that already matched, which is usually a handful.

### Why `multilingual`

All three Laya checkpoints were measured on the same passage-ranking task. The
smallest is both the fastest and the most accurate here, so it is the default.

| checkpoint | per passage | gap between top hit and next |
|---|---|---|
| **multilingual** (322M) | **35 ms** | **0.951** |
| english (421M) | 74 ms | 0.684 |
| typed-decisions (421M) | 69 ms | 0.438 |

## Differences from Needle

Needle calls hosted Jev through Vercel AI Gateway from a Node backend. This port
runs the model locally, which changed four things.

The backend is Python and calls Laya in-process. Node, React, Vite and the Vercel
functions are gone, along with the API key, the access token and the hosted
deployment. One process, one port.

Each passage is scored in its own forward pass. Needle puts the whole page in one
request; Laya's context is 512 to 1024 tokens, so that would truncate silently.

The key sentence is chosen by scoring each sentence, not by one `choice`
question, for the accuracy reason above.

`text-range.js` now finds the sentence by its text when the server offset does
not line up with the live page, instead of dropping the highlight.

## Development

```bash
python3 tests/test_sentences.py
python3 tests/test_search.py
python3 tests/test_extension.py
python3 scripts/package_extension.py
```

The tests inject a fake model, so they need no weights and run in milliseconds.
`test_extension.py` is a static check on the extension: that every asset a page
references exists, that each page loads its script, that every `#id` the script
queries is in the HTML, and that the extension's default URL matches the port
the server listens on.

After changing anything in `extension/`, click **Reload** on the laya-needle card
in `chrome://extensions`, then refresh the page before reopening it.

## Troubleshooting

| What you see | What to do |
|---|---|
| "Cannot reach the Laya server" | Start `.venv/bin/python server.py` and leave it running. |
| "Laya is still loading" | First run downloads weights. Watch the terminal. |
| "Port 8787 is already in use" | Another copy is running, or use `PORT=8788 python server.py` and update the extension setting. |
| Too many weak matches | Raise `LAYA_NEEDLE_THRESHOLD` toward `0.8`. |
| No highlights, but matches found | The page changed after capture. Search again. |
| Nothing happens on a page | Chrome blocks its own pages, the Web Store and the built-in PDF viewer. |

## What gets sent where

Page text goes from the extension to `127.0.0.1` and no further. The server does
not log page text and makes no outbound requests once the weights are cached.
Weights are downloaded once from Hugging Face into `~/.cache/huggingface`.

## Credits and licence

Apache-2.0. See [`LICENSE`](LICENSE) and [`NOTICE`](NOTICE).

[Needle](https://github.com/Shubhamsaboo/awesome-llm-apps/tree/main/advanced_llm_apps/needle)
by Shubham Saboo and contributors, in awesome-llm-apps, Apache-2.0. The
extension, its interaction design and its icons come from there.

[Laya](https://github.com/NandhaKishorM/laya) by Nandakishor M of Convai
Innovations, Apache-2.0. This repository does not contain the model. It installs
the `laya` package and downloads the open weights.
