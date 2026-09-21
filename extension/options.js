const DEFAULT_SERVER = "http://127.0.0.1:8787";
const form = document.querySelector("#settings"),
  server = document.querySelector("#server"),
  status = document.querySelector("#status");

chrome.storage.local.get(["server"]).then((data) => {
  server.value = data.server || DEFAULT_SERVER;
});

document.querySelector("#reset").addEventListener("click", () => {
  server.value = DEFAULT_SERVER;
});

document.querySelector("#test").addEventListener("click", async () => {
  status.textContent = "Checking…";
  try {
    const response = await fetch(`${new URL(server.value).origin}/api/health`);
    const data = await response.json();
    status.textContent = data.ok
      ? `Connected. Laya "${data.model}" on ${data.device}.`
      : "Server is up but Laya is still loading. Wait a moment.";
  } catch {
    status.textContent = "No answer. Is `python server.py` running?";
  }
});

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  try {
    const url = new URL(server.value);
    if (!["http:", "https:"].includes(url.protocol) || url.username || url.password)
      throw new Error("Enter an http or https server URL.");
    if (url.protocol !== "https:" && !["localhost", "127.0.0.1"].includes(url.hostname))
      throw new Error("Use HTTPS for anything that is not localhost.");
    const granted = await chrome.permissions.request({
      origins: [`${url.protocol}//${url.hostname}/*`],
    });
    if (!granted) throw new Error("Permission is needed to reach this server.");
    await chrome.storage.local.set({ server: url.origin });
    status.textContent = "Saved. Open a webpage and press Cmd+Shift+F.";
  } catch (error) {
    status.textContent = error.message;
  }
});
