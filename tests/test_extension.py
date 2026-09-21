"""Static checks on the extension. These would have caught options.js never loading."""
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXT = os.path.join(ROOT, "extension")
sys.path.insert(0, os.path.join(ROOT, "scripts"))
from package_extension import FILES  # noqa: E402


def read(name):
    with open(os.path.join(EXT, name), encoding="utf-8") as f:
        return f.read()


# Every local asset an HTML page references must exist, and scripts must be wired up.
for page in ("options.html",):
    html = read(page)
    referenced = re.findall(r'(?:src|href)="(?!https?:|data:)([^"]+)"', html)
    for asset in referenced:
        assert os.path.isfile(os.path.join(EXT, asset)), f"{page} references missing {asset}"
    for script in [f for f in os.listdir(EXT) if f == page.replace(".html", ".js")]:
        assert script in referenced, f"{page} never loads {script}"

# Every #id the page script queries must exist in its HTML.
options_html, options_js = read("options.html"), read("options.js")
for ident in sorted(set(re.findall(r'querySelector\("#([\w-]+)"\)', options_js))):
    assert f'id="{ident}"' in options_html, f"options.js queries #{ident}, absent from options.html"

# Manifest files must all be present, and the packaged set must cover them.
manifest = json.loads(read("manifest.json"))
declared = [manifest["background"]["service_worker"], manifest["options_page"]]
declared += list(manifest["icons"].values())
declared += list(manifest["action"]["default_icon"].values())
for name in declared:
    assert os.path.isfile(os.path.join(EXT, name)), f"manifest declares missing {name}"
    assert name in FILES, f"manifest declares {name}, which packaging would leave out"

# Scripts the background injects must ship too.
for injected in re.findall(r'files:\s*\[([^\]]+)\]', read("background.js")):
    for name in re.findall(r'"([^"]+)"', injected):
        assert os.path.isfile(os.path.join(EXT, name)), f"background.js injects missing {name}"
        assert name in FILES, f"background.js injects {name}, which packaging would leave out"

# Requesting an origin that is only in host_permissions throws in Chrome.
assert "permissions.contains" in options_js, "check the permission before requesting it"
assert "optional_host_permissions" in manifest, "a non-default server URL could never be granted"

# A row's text is assembled from its cells, so it never equals the element's own
# text. Checking freshness against the assembled text silently dropped every
# table-row highlight in v1.2.0.
content = read("content.js")
assert "block.raw" in content and "!== block.text" not in content, \
    "check freshness against the element's own text, not the text sent to the server"
assert "raw: el.textContent.trim()" in content, "each block must keep the element's own text"
assert "block.row" in content, "a row highlights whole; no sentence of it exists as one DOM run"
assert "getManifest().version" in content, \
    "the panel shows its version, so a stale build is visible without opening chrome://extensions"

# The default server URL must agree across the extension and the server.
default = re.search(r'DEFAULT_SERVER = "([^"]+)"', options_js).group(1)
assert re.search(r'DEFAULT_SERVER = "([^"]+)"', read("background.js")).group(1) == default, \
    "options.js and background.js disagree on the default server"
with open(os.path.join(ROOT, "server.py"), encoding="utf-8") as f:
    port = re.search(r'PORT = int\(os\.environ\.get\("PORT", "(\d+)"\)\)', f.read()).group(1)
assert default == f"http://127.0.0.1:{port}", f"extension points at {default}, server listens on {port}"

print("extension: all passed")
