(() => {
  const existing = document.getElementById("laya-needle-host");
  if (existing) {
    existing.dispatchEvent(new Event("laya-needle-close"));
    return;
  }
  const host = document.createElement("div");
  host.id = "laya-needle-host";
  host.style.cssText = "position:fixed;top:20px;right:20px;z-index:2147483647";
  const shadow = host.attachShadow({ mode: "open" });
  shadow.innerHTML = `<style>
 :host{all:initial}
 *{box-sizing:border-box}
 .dock{
   --bg:#fff; --fg:#111; --muted:#767676; --line:#e3e3e3; --hover:#0000000a;
   --invert-bg:#111; --invert-fg:#fff;
   width:min(460px,calc(100vw - 40px));
   background:var(--bg); color:var(--fg);
   border:1px solid var(--line); border-radius:12px;
   box-shadow:0 8px 30px #00000014;
   font:13px/1.5 system-ui,-apple-system,sans-serif; padding:14px;
 }
 @media (prefers-color-scheme:dark){
   .dock{
     --bg:#161616; --fg:#f2f2f2; --muted:#9a9a9a; --line:#2e2e2e; --hover:#ffffff12;
     --invert-bg:#f2f2f2; --invert-fg:#111;
     box-shadow:0 8px 30px #00000059;
   }
 }
 .top{display:flex;align-items:center;gap:8px}
 .brand{
   display:flex;align-items:center;gap:7px;margin-right:auto;
   font-size:13px;font-weight:600;letter-spacing:-.1px;color:var(--fg);
 }
 .brand svg{width:15px;height:15px;flex-shrink:0;display:block}
 button{
   font:inherit;cursor:pointer;border:0;border-radius:6px;
   background:transparent;color:var(--muted);padding:5px 7px;line-height:1;
 }
 button:hover{background:var(--hover);color:var(--fg)}
 .search{
   display:flex;align-items:center;gap:8px;
   border-bottom:1px solid var(--line);margin-top:10px;padding-bottom:10px;
 }
 input{
   width:100%;min-width:0;border:0;background:transparent;outline:none;
   color:var(--fg);font:16px/1.4 system-ui,-apple-system,sans-serif;padding:0;
 }
 input::placeholder{color:var(--muted)}
 .go{background:var(--invert-bg);color:var(--invert-fg);padding:5px 9px;font-size:13px}
 .go:hover{background:var(--invert-bg);color:var(--invert-fg);opacity:.85}
 .status{display:flex;align-items:center;gap:4px;margin-top:9px}
 .label{flex:1;color:var(--fg);font-size:12px}
 .detail{margin:6px 0 0;color:var(--muted);font-size:11px;line-height:1.45}
 .error{color:var(--fg);font-weight:600}
 button:focus-visible,input:focus-visible{outline:2px solid var(--fg);outline-offset:2px}
 </style><section class="dock" role="dialog" aria-label="Find with laya-needle"><div class="top"><span class="brand"><svg aria-hidden="true" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32" fill="none" stroke="currentColor" stroke-width="2.6" stroke-linecap="round"><path d="m7 27 13-19"/><path d="m18 10 4 2.7"/><circle cx="21.5" cy="6.5" r="2.6"/></svg><span>laya needle</span></span><button class="settings" aria-label="Open settings">⚙</button><button class="close" aria-label="Close">✕</button></div><form class="search"><input aria-label="Find what you mean" placeholder="Find what you mean…" maxlength="400"><button class="go" aria-label="Search">↗</button></form><div class="status"><span class="label" aria-live="polite">A thought, a question, a half-remembered idea.</span><button class="nav prev" aria-label="Previous match">↑</button><button class="nav next" aria-label="Next match">↓</button></div><p class="detail"></p></section>`;
  document.documentElement.append(host);
  const $ = (s) => shadow.querySelector(s),
    input = $("input"),
    label = $(".label"),
    detail = $(".detail");
  let active = 0, matches = [], generation = 0, timer, closed = false,
    blocks = [], highlightStyle = null;

  // A table cell on its own says nothing: "Saturn Awards" with no column and no
  // row is a fragment the model cannot score. The row is the smallest unit that
  // still means something, so rows are captured whole and their cells are not.
  function passageText(el) {
    if (el.tagName !== "TR") return el.textContent.trim();
    const cells = [...el.querySelectorAll("th,td")]
      .filter((c) => !c.querySelector("th,td"))
      // innerText, not textContent: an infobox header split across two block
      // elements concatenates to "Productioncompanies" under textContent, and
      // that junk token scored 0.44 against a search about asparagus.
      .map((c) => (c.innerText ?? c.textContent).trim().replace(/\s+/g, " "))
      .filter(Boolean);
    return cells.join(" · ");
  }

  function collect() {
    const candidates = [...document.querySelectorAll("p,li,pre,blockquote,h1,h2,h3,h4,tr,figcaption")];
    let size = 0, truncated = false;
    const selected = candidates.filter(
      (el) =>
        !el.closest('nav,header,footer,script,style,[contenteditable="true"]') &&
        el.getClientRects().length &&
        getComputedStyle(el).visibility !== "hidden",
    );
    const rows = new Set(selected.filter((el) => el.tagName === "TR"));
    blocks = [];
    for (const el of selected) {
      if (el.tagName === "TR") {
        // Nested tables: keep the innermost row.
        if (selected.some((other) => other !== el && other.tagName === "TR" && el.contains(other))) continue;
      } else {
        // A row owns everything inside it, so its cells' contents are not separate passages.
        if ([...rows].some((row) => row.contains(el))) continue;
        if (selected.some((other) => other !== el && el.contains(other))) continue;
      }
      const text = passageText(el);
      if (text.length < 12) continue;
      if (text.length > 2200) { truncated = true; continue; }
      if (blocks.length >= 160 || size + text.length > 60000) { truncated = true; break; }
      // `text` is what the server scores. For a row that is assembled from cells,
      // so it never equals the element's own text; keep that separately for the
      // did-this-page-change check below.
      blocks.push({ id: `b${blocks.length}`, text, raw: el.textContent.trim(), row: el.tagName === "TR", el });
      size += text.length;
    }
    detail.textContent = `${blocks.length} readable passages${truncated ? " · some content omitted" : ""} · scored locally by Laya.`;
  }

  function clearHighlights() {
    if (globalThis.CSS?.highlights) {
      CSS.highlights.delete("laya-needle-matches");
      CSS.highlights.delete("laya-needle-active");
      CSS.highlights.delete("laya-needle-sentences");
    }
    highlightStyle?.remove();
    highlightStyle = null;
  }

  function paint() {
    clearHighlights();
    if (!matches.length) return;
    const ranges = [], sentences = [];
    let selectedSentence = null;
    matches.forEach((match, i) => {
      const block = blocks.find((b) => b.id === match.id);
      if (!block?.el.isConnected || block.el.textContent.trim() !== block.raw) return;
      const context = new Range();
      context.selectNodeContents(block.el);
      ranges.push(context);
      // A row's text is joined from its cells, so no sentence of it exists as one
      // run in the DOM and no range can be mapped. The row is the unit: light it
      // all up rather than nothing.
      const sentence = block.row
        ? context.cloneRange()
        : globalThis.LayaNeedleTextRange(block.el, match.focus, block.text);
      if (sentence) {
        sentences.push(sentence);
        if (i === active) selectedSentence = sentence;
      }
    });
    if (globalThis.CSS?.highlights && globalThis.Highlight) {
      highlightStyle = document.createElement("style");
      // Both background and colour are set, so a highlight stays legible whatever
      // the host page uses. The active one is a straight inversion.
      highlightStyle.textContent =
        "::highlight(laya-needle-matches){background:#f0f0f0;color:#111}" +
        "::highlight(laya-needle-sentences){background:#dcdcdc;color:#111}" +
        "::highlight(laya-needle-active){background:#111;color:#fff}" +
        "@media (prefers-color-scheme:dark){" +
        "::highlight(laya-needle-matches){background:#2b2b2b;color:#f2f2f2}" +
        "::highlight(laya-needle-sentences){background:#444;color:#fff}" +
        "::highlight(laya-needle-active){background:#f2f2f2;color:#111}}";
      document.documentElement.append(highlightStyle);
      const context = new Highlight(...ranges),
        focus = new Highlight(...sentences),
        selected = new Highlight(...(selectedSentence ? [selectedSentence] : []));
      context.priority = 0;
      focus.priority = 1;
      selected.priority = 2;
      CSS.highlights.set("laya-needle-matches", context);
      CSS.highlights.set("laya-needle-sentences", focus);
      CSS.highlights.set("laya-needle-active", selected);
    }
    blocks.find((b) => b.id === matches[active].id)?.el.scrollIntoView({
      behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "instant" : "smooth",
      block: "center",
    });
  }

  function update() {
    label.textContent = matches.length
      ? `${active + 1} of ${matches.length} ${matches.length === 1 ? "connection" : "connections"}`
      : "No strong matches.";
    paint();
  }

  async function search() {
    clearTimeout(timer);
    const current = ++generation;
    collect();
    clearHighlights();
    matches = [];
    active = 0;
    label.classList.remove("error");
    const query = input.value.trim();
    if (query.length < 2) { label.textContent = "Describe what you're looking for."; return; }
    if (!blocks.length) { label.textContent = "No readable paragraphs on this page."; return; }

    // Laya scores one passage per forward pass, so say how long this will feel.
    label.textContent = `Reading ${blocks.length} passages locally…`;
    try {
      const result = await chrome.runtime.sendMessage({
        type: "LAYA_NEEDLE_SEARCH",
        payload: { query, blocks: blocks.map(({ id, text }) => ({ id, text })) },
      });
      if (closed || current !== generation) return;
      if (!result || result.error) throw new Error(result?.error || "Could not complete the search.");
      matches = result.matches.filter((m) => blocks.some((b) => b.id === m.id));
      update();
      detail.textContent += ` · ${result.elapsedMs} ms · the strongest sentence is inverted.`;
    } catch (error) {
      if (!closed && current === generation) {
        label.textContent = error.message;
        label.classList.add("error");
      }
    }
  }

  function move(delta) {
    if (matches.length) {
      active = (active + delta + matches.length) % matches.length;
      update();
    }
  }

  function close() {
    closed = true;
    generation++;
    clearTimeout(timer);
    clearHighlights();
    host.remove();
    document.removeEventListener("keydown", key, true);
  }

  function key(event) {
    if (event.key === "Escape") { close(); event.stopPropagation(); }
    if ((event.ctrlKey || event.metaKey) && event.key === "f") {
      event.preventDefault();
      event.stopPropagation();
      input.focus();
      input.select();
    }
  }

  host.addEventListener("laya-needle-close", close);
  document.addEventListener("keydown", key, true);
  $(".close").onclick = close;
  $(".settings").onclick = () => chrome.runtime.sendMessage({ type: "LAYA_NEEDLE_SETTINGS" });
  $(".prev").onclick = () => move(-1);
  $(".next").onclick = () => move(1);
  $(".search").onsubmit = (event) => { event.preventDefault(); search(); };
  input.oninput = () => {
    generation++;
    clearTimeout(timer);
    clearHighlights();
    matches = [];
    label.textContent = "…";
    // Local inference is not free, so wait longer than Needle before firing.
    timer = setTimeout(search, 900);
  };
  input.onkeydown = (event) => {
    if (event.key === "Enter" && matches.length) {
      event.preventDefault();
      move(event.shiftKey ? -1 : 1);
    }
  };
  collect();
  input.focus();
})();
