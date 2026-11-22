import os, sys, urllib.request, json, subprocess
from pathlib import Path

wheel_dir = Path("scratch/wheels")
wheel_dir.mkdir(parents=True, exist_ok=True)

packages = ["faster-whisper", "ctranslate2", "av"]
urls = []

print("=== Fetching wheel URLs from PyPI ===")
for pkg in packages:
    req = urllib.request.Request(f"https://pypi.org/pypi/{pkg}/json", headers={"User-Agent": "Mozilla/5.0"})
    data = json.loads(urllib.request.urlopen(req, timeout=15).read().decode("utf-8"))
    cand = []
    for u in data["urls"]:
        fn = u["filename"]
        if fn.endswith("-py3-none-any.whl"):
            cand.append(u)
        elif "cp313" in fn and "win_amd64" in fn:
            cand.append(u)
        elif "abi3" in fn and "win_amd64" in fn:
            cand.append(u)
    if cand:
        # Sort by filename to get latest
        chosen = sorted(cand, key=lambda x: x["filename"])[-1]
        urls.append((chosen["filename"], chosen["url"], chosen["size"]))
        print(f"Found {pkg}: {chosen['filename']} ({round(chosen['size']/1024/1024, 2)} MB)")
    else:
        print(f"No suitable wheel for {pkg}")

print("\n=== Downloading wheels ===")
downloaded = []
for fn, url, size in urls:
    target = wheel_dir / fn
    if target.exists() and target.stat().st_size == size:
        print(f"Already downloaded: {fn}")
        downloaded.append(target)
        continue
    print(f"Downloading {fn}...")
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=60) as resp, open(target, "wb") as f:
        f.write(resp.read())
    print(f"Downloaded {fn} ({target.stat().st_size} bytes)")
    downloaded.append(target)

print("\n=== Installing via pip ===")
cmd = [str(Path(".venv/Scripts/pip.exe")), "install"] + [str(p) for p in downloaded]
res = subprocess.run(cmd, capture_output=True, text=True)
print("Pip returncode:", res.returncode)
print("Pip stdout:\n", res.stdout)
if res.stderr:
    print("Pip stderr:\n", res.stderr)

