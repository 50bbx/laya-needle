const DEFAULT_SERVER = "http://127.0.0.1:8787";

chrome.runtime.onInstalled.addListener(({ reason }) => {
  if (reason === "install") chrome.runtime.openOptionsPage();
});

chrome.action.onClicked.addListener(async (tab) => {
  try {
    await chrome.scripting.executeScript({
      target: { tabId: tab.id },
      files: ["text-range.js", "content.js"],
    });
  } catch {
    await chrome.runtime.openOptionsPage();
  }
});

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.type === "LAYA_NEEDLE_SETTINGS") {
    chrome.runtime.openOptionsPage();
    return;
  }
  if (message.type !== "LAYA_NEEDLE_SEARCH" || !sender.tab) return;
  (async () => {
    const { server = DEFAULT_SERVER } = await chrome.storage.local.get(["server"]);
    try {
      const response = await fetch(`${server}/api/search`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(message.payload),
        // Laya scores passages one at a time, so a long page takes a few seconds.
        signal: AbortSignal.timeout(120000),
      });
      const data = await response.json();
      sendResponse(response.ok ? data : { error: data.error || "Search failed." });
    } catch (error) {
      sendResponse({
        error:
          error.name === "TimeoutError"
            ? "Laya took too long. Try a shorter page."
            : `Cannot reach the Laya server at ${server}. Start it with: python server.py`,
      });
    }
  })();
  return true;
});
