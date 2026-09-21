"""Zip the extension for the GitHub release. python scripts/package_extension.py"""
import os
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SOURCE = os.path.join(ROOT, "extension")
# An allowlist, so nothing stray in extension/ ever ships.
FILES = ["manifest.json", "background.js", "content.js", "text-range.js",
         "options.html", "options.css", "options.js",
         "icons/needle-16.png", "icons/needle-32.png",
         "icons/needle-48.png", "icons/needle-128.png"]


def build(out="laya-needle-extension.zip"):
    missing = [f for f in FILES if not os.path.isfile(os.path.join(SOURCE, f))]
    if missing:
        raise SystemExit("missing from extension/: " + ", ".join(missing))
    target = os.path.join(ROOT, out)
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as zf:
        for name in FILES:
            zf.write(os.path.join(SOURCE, name), name)
    return target, os.path.getsize(target)


if __name__ == "__main__":
    path, size = build()
    print(f"{os.path.relpath(path, ROOT)}  {size / 1024:.0f} KB  ({len(FILES)} files)")
