"""Render the README banner (1280 x 640, also usable as the GitHub social preview).

Numbers come from evidence/final_three_model_summary_20260929.json. Needs Chrome or Edge
(set CAROUSEL_BROWSER to override) and network access for Google Fonts.

    python portfolio/build_readme_banner.py
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
W, H = 1280, 640
BROWSERS = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
]


def browser() -> str:
    if os.environ.get("CAROUSEL_BROWSER"):
        return os.environ["CAROUSEL_BROWSER"]
    for b in BROWSERS:
        if Path(b).exists():
            return b
    for name in ("google-chrome", "chromium", "msedge"):
        if shutil.which(name):
            return shutil.which(name)
    raise SystemExit("Chrome/Edge not found; set CAROUSEL_BROWSER")


def main() -> None:
    s = json.loads((ROOT / "evidence/final_three_model_summary_20260929.json").read_text(encoding="utf-8"))
    m = s["models"]
    wape = {k: m[k]["primary_median_series_wape"] for k in m}
    bias = m["ai_forecast_v2"]["paired_signed_bias"]
    wins = s["series_lowest_wape_counts"]["ai_forecast_v2"]
    cells = s["expected_series_origin_pairs"] * 3
    cards = [("ai_forecast v2", wape["ai_forecast_v2"], "#4C9BFF", True),
             ("Tuned Prophet", wape["prophet_tuned"], "#3DDC97", False),
             ("Weekly baseline", wape["snaive7"], "#FF7A59", False)]
    card_html = "".join(
        f'<div class="card{" win" if win else ""}"><div class="name">{name}</div>'
        f'<div class="v" style="color:{color}">{v:.1%}</div>'
        f'<div class="track"><div style="width:{v / 0.28 * 100:.0f}%;background:{color}"></div></div></div>'
        for name, v, color, win in cards)
    html = f"""<!doctype html><html><head><meta charset="utf-8">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800&display=block" rel="stylesheet">
<style>*{{margin:0;padding:0;box-sizing:border-box}}
html,body{{width:{W}px;height:{H}px;overflow:hidden;background:#0B1020;color:#E8ECF4;font-family:Inter,sans-serif}}
.page{{position:relative;width:{W}px;height:{H}px;padding:56px 64px}}
.glow{{position:absolute;width:760px;height:760px;right:-240px;top:-320px;background:radial-gradient(circle,#1D3C8A 0%,transparent 65%);opacity:.8}}
.kicker{{font-size:18px;letter-spacing:.14em;text-transform:uppercase;color:#7FA7FF;font-weight:700;position:relative}}
h1{{font-size:58px;line-height:1.04;font-weight:800;letter-spacing:-.03em;margin-top:22px;position:relative;max-width:1060px}}
em{{font-style:normal;color:#4C9BFF}}
.row{{display:grid;grid-template-columns:1fr 1fr 1fr;gap:18px;margin-top:34px}}
.card{{background:#121A2E;border:1px solid #243154;border-radius:20px;padding:20px 24px}}
.card.win{{border-color:#4C9BFF;background:#13244A}}
.name{{font-size:19px;font-weight:600;color:#C9D1E0}}
.v{{font-size:56px;font-weight:800;letter-spacing:-.03em;margin-top:6px}}
.track{{background:#1A2338;border-radius:6px;height:12px;margin-top:10px;overflow:hidden}}.track div{{height:12px;border-radius:6px}}
.bottom{{display:flex;justify-content:space-between;align-items:center;margin-top:26px;font-size:21px;color:#A9B3C7}}
.bottom b{{color:#E8ECF4}} .warn{{color:#FF9C85;font-weight:700}}
.chips{{margin-top:26px}}.chip{{display:inline-block;background:#121A2E;border:1px solid #243154;border-radius:999px;padding:9px 18px;font-size:19px;color:#C9D1E0;margin-right:10px}}.chip b{{color:#E8ECF4}}
</style></head><body><div class="page"><div class="glow"></div>
<div class="kicker">Databricks forecasting benchmark · NYC 311 · 2025</div>
<h1>One SQL function beat my <em>tuned</em> forecasting pipeline.</h1>
<div class="row">{card_html}</div>
<div class="bottom"><span>Median series error · lower is better · most accurate on <b>{wins} of 21</b> series</span>
<span class="warn">but it forecast {abs(bias):.0%} low</span></div>
<div class="chips"><span class="chip"><b>21</b> series</span><span class="chip"><b>12</b> monthly origins</span><span class="chip"><b>28</b>-day horizon</span><span class="chip"><b>{cells}/{cells}</b> forecasts</span><span class="chip">protocol frozen <b>before</b> 2025</span></div>
</div></body></html>"""
    out = ROOT / "portfolio/readme_banner.png"
    with tempfile.TemporaryDirectory() as tmp:
        src = Path(tmp) / "banner.html"
        src.write_text(html, encoding="utf-8")
        subprocess.run([browser(), "--headless=new", "--disable-gpu", "--hide-scrollbars", "--force-device-scale-factor=1",
                        f"--window-size={W},{H}", "--virtual-time-budget=8000", f"--screenshot={out}", src.as_uri()],
                       check=True, capture_output=True, timeout=120)
    print(out)


if __name__ == "__main__":
    main()
