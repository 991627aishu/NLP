import os, sys, subprocess
from pathlib import Path

chrome_path = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
os.environ["CHROME_PATH"] = chrome_path

out_dir = Path("docs/lighthouse")
out_dir.mkdir(parents=True, exist_ok=True)

# 1. Desktop Audit
print("=== Running Lighthouse Desktop Audit ===")
desktop_out = out_dir / "desktop-report"
cmd_desktop = [
    r"F:\npx.CMD", "lighthouse", "http://127.0.0.1:8000/",
    "--chrome-flags=--headless=new --no-sandbox",
    "--output=html", "--output=json",
    f"--output-path={desktop_out}",
    "--preset=desktop",
    "--quiet"
]
p_desk = subprocess.run(cmd_desktop, capture_output=True, text=True)
print("Desktop return code:", p_desk.returncode)
if p_desk.stderr:
    print("Desktop stderr:", p_desk.stderr[:500])

# 2. Mobile Audit
print("\n=== Running Lighthouse Mobile Audit ===")
mobile_out = out_dir / "mobile-report"
cmd_mobile = [
    r"F:\npx.CMD", "lighthouse", "http://127.0.0.1:8000/",
    "--chrome-flags=--headless=new --no-sandbox",
    "--output=html", "--output=json",
    f"--output-path={mobile_out}",
    "--form-factor=mobile",
    "--quiet"
]
p_mob = subprocess.run(cmd_mobile, capture_output=True, text=True)
print("Mobile return code:", p_mob.returncode)
if p_mob.stderr:
    print("Mobile stderr:", p_mob.stderr[:500])

print("\n=== Audit Completed ===")

