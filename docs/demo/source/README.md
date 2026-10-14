# Video and audit report sources

Everything needed to rebuild the silent walkthrough (`docs/demo/demo.mp4`) and the audit report
(`docs/demo/AUDIT_REPORT.*`) from this repository alone. Paths below are relative to the repo root.

## What is here

| Path | What it is |
|---|---|
| `index.html` | Root of the video: theme (colours, type), and the timing of every slide |
| `compositions/bg.html`, `compositions/chrome.html` | Background grid, and the persistent project label, slide counter and progress bar |
| `compositions/s01-context.html` | Slide 01, the industry and four everyday problems |
| `compositions/s02-hook.html` | Slide 02, the project in one sentence over the 26 real hub positions |
| `compositions/explainer.html` | Slides 03-04, the white "how it works" chapter (edit its `CONFIG` block) |
| `compositions/s03-architecture.html` | Slide 05, the architecture diagram (nodes, cylinders and the `W` wires object) |
| `compositions/s04-routes.html` | Slide 06, daily cancellations for four weeks and the cost split by day type |
| `compositions/value.html` | Slide 07, the rider board and hub-lead scene (data injected by `tools/inject_sheet.py`) |
| `compositions/s05-results.html`, `s06-twist.html`, `s07-end.html` | Slides 08-10, A/B results, what didn't win, end card |
| `assets/run_series.json` | Daily cancellation rates, the stress split, run totals and hub positions, exported by `tools/export_series.py` |
| `assets/rider_board.json` | Hub 18, 2026-02-14, 21:46 dispatch wave, exported by `tools/export_rider_board.py` |
| `audit/facts.yaml` | Every figure (F-xx), assumption (A-xx), slide text and check expression used by the report |
| `tools/build_audit_report.py` | Builds the slide stills, re-checks every figure against the repo outputs, writes MD, DOCX and PDF |
| `tools/export_series.py` | Reads `outputs/` and `data/` and writes `assets/run_series.json` |
| `tools/export_rider_board.py` | Re-runs the repo's own simulator for one hub-day and exports one wave's rider board as JSON |
| `tools/inject_sheet.py` | Inlines a JSON file into a composition's `SHEET` or `SERIES` block (renders cannot fetch files) |
| `package.json`, `hyperframes.json`, `meta.json` | HyperFrames project files (CLI pinned to 0.8.156) |

No matplotlib plot is used, so there is no image-conversion step: the charts on slide 06 are drawn
from the injected numbers. Fonts (Inter, JetBrains Mono, Montserrat) are referenced by name and
embedded by the HyperFrames renderer; all three are SIL Open Font License.

## Requirements

- Node 22 and `npx` (HyperFrames 0.8.156 is fetched by `npx`), plus Chrome/Chromium for rendering.
- `ffmpeg` for compressing the video and extracting slide stills.
- LibreOffice (`soffice`) to convert the report to PDF.
- The repo's own environment (`uv sync`) for `make run` and `export_rider_board.py`.
- For `build_audit_report.py`, `export_series.py` and `inject_sheet.py` (any Python 3.11+, not added
  to the repo's `pyproject.toml`): `pip install pyyaml pandas python-docx pillow numpy matplotlib`.

## Rebuild the numbers, the video and the report

```bash
# 1. data and repo outputs (about 3 minutes)
make run

# 2. inputs for the video
python3 docs/demo/source/tools/export_series.py docs/demo/source/assets/run_series.json
PYTHONPATH=src .venv/bin/python docs/demo/source/tools/export_rider_board.py docs/demo/source/assets/rider_board.json
python3 docs/demo/source/tools/inject_sheet.py docs/demo/source/assets/rider_board.json \
  docs/demo/source/compositions/value.html --name SHEET
for f in s02-hook s04-routes s07-end; do
  python3 docs/demo/source/tools/inject_sheet.py docs/demo/source/assets/run_series.json \
    docs/demo/source/compositions/$f.html --name SERIES
done

# 3. render (84.6 s, 1920x1080, 30 fps, silent) and compress
cd docs/demo/source
npx --yes hyperframes@0.8.156 check
npx --yes hyperframes@0.8.156 render -f 30 -q looks -o renders/last-mile-dispatch-master.mp4
cd -
ffmpeg -y -i docs/demo/source/renders/last-mile-dispatch-master.mp4 -c:v libx264 -preset slow -crf 25 \
  -pix_fmt yuv420p -movflags +faststart -an docs/demo/demo.mp4

# 4. GIFs (README preview of slide 07, and the architecture loop)
VF="fps=12,scale=800:-1:flags=lanczos,split[a][b];[a]palettegen=max_colors=128:stats_mode=diff[p];[b][p]paletteuse=dither=bayer:bayer_scale=5:diff_mode=rectangle"
ffmpeg -y -ss 53.6 -t 12 -i docs/demo/source/renders/last-mile-dispatch-master.mp4 -vf "$VF" -loop 0 docs/demo/demo.gif
ffmpeg -y -ss 32.8 -t 7.7 -i docs/demo/source/renders/last-mile-dispatch-master.mp4 -vf "$VF" -loop 0 docs/demo/architecture.gif

# 5. audit report: slide stills, automated checks, AUDIT_REPORT.md/.docx/.pdf
python3 docs/demo/source/tools/build_audit_report.py docs/demo/source/audit/facts.yaml
```

`build_audit_report.py` exits with code 1 if any figure on screen no longer matches the repo outputs.
The run is fully seeded (data seed 7, hub assignment seed 2026, simulator seed per hub-day), so a fresh
`make run` reproduces every number; `export_rider_board.py` asserts that its re-run matches
`outputs/hub_day_metrics.csv` before it writes anything.

The `renders/` folder (about 14 MB) is not committed; step 3 recreates it.
