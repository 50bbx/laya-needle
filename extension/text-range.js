// Turn a server sentence span into a DOM range, across inline tags.
// The server sends UTF-16 offsets, but a page can differ from what was captured,
// so the sentence text is the authority and the offset is only a starting hint.
globalThis.LayaNeedleTextRange = (element, focus, expectedText) => {
  const raw = element.textContent;
  if (raw.trim() !== expectedText || !focus?.text) return null;

  let at = expectedText.slice(focus.start, focus.end) === focus.text
    ? focus.start
    : expectedText.indexOf(focus.text);
  if (at < 0) return null;

  const padding = raw.length - raw.trimStart().length;
  const start = padding + at,
    end = start + focus.text.length;
  if (end > raw.length) return null;

  const walker = document.createTreeWalker(element, NodeFilter.SHOW_TEXT);
  let offset = 0, startNode = null, endNode = null, startOffset = 0, endOffset = 0, node;
  while ((node = walker.nextNode())) {
    const next = offset + node.textContent.length;
    if (!startNode && start < next) {
      startNode = node;
      startOffset = start - offset;
    }
    if (startNode && end <= next) {
      endNode = node;
      endOffset = end - offset;
      break;
    }
    offset = next;
  }
  if (!startNode || !endNode) return null;
  const range = new Range();
  range.setStart(startNode, startOffset);
  range.setEnd(endNode, endOffset);
  return range;
};
