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
ready in 21.1s, running on your Mac's GPU (mps)
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
| Score floor | `0.05`, override with `LAYA_NEEDLE_FLOOR=0.2` |

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

`matches` holds the best few passages, sorted best first, each with the `focus`
sentence and its offsets into the original passage text. That is always the top 3
above the floor, plus any others scoring within 45% of the best, capped at 8.
`scores` ranks every passage on the page.

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
  "floor": 0.05, "elapsedMs": 138, "model": "multilingual"
}
```

## How good is it, honestly

Laya scores passages well and picks sentences less well.

**Passage relevance is strong.** On a support-document test the matching passage
scored 0.985 while every unrelated passage sat under 0.12. That is a wide, safe
margin.

**It matches words more than meaning.** This is the sharpest limit. On that
Wikipedia article the row `Budget · $175 million` scores **0.820** for the search
"budget" and **0.277** for "cost". Same row, same meaning, different word. It
still ranks 3rd of 120 so you will find it, but the premise of finding what you
mean rather than what you typed only half holds.

Coaching the instruction does not help. An instruction spelling out *"a budget is
a cost, a release date is when it came out"* was measured against four others on
eight queries and came **last**, 1 correct out of 8 against 5 for the one-line
version now in use. Every attempt to explain synonyms made it worse.

**A search that matches nothing still returns something.** Searching that article
for "quantum chromodynamics" returns a box-office sentence at 0.609, while the
genuine top hit for "awards" is 0.671. Scores are not comparable between one
search and another, so no cutoff keeps the real matches and rejects the nonsense
ones. Read the results as "the closest passages on this page", not "the relevant
ones".

**Phrase a search as a topic, not a question.** "awards" works. "what awards did
the film win?" returns nothing. This is a find-in-page, not a chatbot.

If you get noise, raise `LAYA_NEEDLE_FLOOR` toward `0.5`. If relevant things are
missing, lower it toward `0.15`.

**Sentence selection had to be rebuilt.** Needle asks Jev to pick the key
sentence with one `choice` question. Laya's choice head is close to useless at
this: on a hand-labelled set of 8 passages it picked the right sentence **0
times**, almost always the first. Scoring each sentence with its own boolean
gets **7 of 8**. That is what this port does.

**Tables are captured one row at a time.** Needle captures each `td` as its own
passage. A cell reading "Saturn Awards", with no column heading and no row around
it, is a fragment the model cannot place: it scored **0.064** for the search
"awards", while the cell "Teen Choice Awards" scored 0.874 on the same page. The
row is the smallest unit that still means something, so rows are joined into one
passage and their cells are not captured separately. That row now scores
**0.671**, and the award rows take five of the top six results. Cells use rendered
text rather than `textContent`, because an infobox heading split across two block
elements concatenates into junk like "Productioncompanies".

**It shows a ranked list, it does not filter.** Every cutoff tried was wrong in
one direction or the other. The row `Budget · $175 million` ranks **3rd of 120**
passages for the search "cost", which is a useful answer, but it scores 0.277 and
any threshold that admitted it also admitted junk. So the best few are always
shown in order, and the floor only drops passages that scored near zero. Press
the down arrow; the answer is usually one or two below the top.

**Ask what a passage is about, not what it answers.** An early version asked
whether each passage *answered* the search, and explicitly discounted topic
matches. That is question answering, not search, and it buried the passages a
search exists to find: on the Wikipedia article above, the cell "Teen Choice
Awards" scored **0.65** for the search "awards". The topical question scores it
**0.87** and puts the award rows in the top four. Short instructions also beat
long ones on both speed and separation, so both questions are now one line.

This is a 322M model on your laptop, not a frontier model in a datacentre. It is
free, private and fast. It is not as accurate as Jev.

## Speed

Measured on an M-series Mac, `multilingual` on MPS, against the full
Spider-Man: Homecoming Wikipedia article.

| page size | time |
|---|---|
| a typical article section | under 0.5 s |
| 138 passages, 60,000 characters (the cap) | **1.9 s** |

Three things get it there. Every passage on the page is scored in **one batched
forward pass** rather than one call each. Items are **sorted by encoded length**
before batching, because a batch pads to its longest member, and a 2,200-char
paragraph next to a three-word table cell otherwise wastes most of it; that took
padding waste from 61% to 11%. And only the **first 400 characters** of a passage
are encoded, since a search asks what a passage is about and the opening says so.

Together those took the worst case from 5.6 s to 1.9 s. The sentence pass runs
only on passages that already matched, which is usually a handful.

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

Passages are scored in batches built directly on Laya's collate, sorted by
length, with each passage clipped to 400 characters. Needle puts the whole page
in one request; Laya's context is 512 to 1024 tokens, so that would truncate
silently. `scorer.py` explains the coupling, and falls back to one call per
passage if a Laya release moves those internals.

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
