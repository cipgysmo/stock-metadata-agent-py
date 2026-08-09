# AI Stock Metadata Agent

Batch-generate and embed professional stock photography metadata using local AI models. Compatible with Shutterstock, Adobe Stock, Getty/iStock, Alamy, and other agencies.

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/)
[![PySide6](https://img.shields.io/badge/UI-PySide6-41cd52.svg)](https://www.qt.io/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

---

## Features

- **Batch processing** with parallel workers (1\u201316)
- **Local AI** \u2013 runs entirely offline via Ollama/OMLX; no cloud API required
- **Vision analysis** \u2013 subject, location, objects, people, logos, commercial safety
- **Universal metadata spec** \u2013 titles, descriptions, and keywords tuned for all major agencies
- **GPS + location memory** \u2013 reads EXIF GPS, reverse-geocodes, stores mappings in SQLite
- **Duplicate detection** \u2013 perceptual hashing catches identical / near-duplicate images
- **Quality validation** \u2013 flags title length, keyword count, banned words, duplicates
- **Content-type override** \u2013 force Editorial or Commercial per batch
- **Cloud fallback** \u2013 optional GPT-4o-mini when the local text model fails
- **Multiple output formats** \u2013 embedded EXIF/XMP, sidecar `.xmp`, or both
- **CSV export** \u2013 optional metadata spreadsheet for review
- **Desktop UI** \u2013 PySide6 with dark/light theme, thumbnail previews, keyword copy
- **Cross-platform** \u2013 macOS (Apple Silicon), Windows (x64), Linux

---

## Quick Start

1. **Download** the latest release for your platform from [Releases](https://github.com/cipgysmo/stock-metadata-agent-py/releases)
2. **Start** a local Ollama/OMLX server with a vision model loaded (e.g. `Qwen2.5-VL-3B-Instruct-8bit`)
3. **Open** the app \u2192 click the gear icon \u2192 enter your local endpoint
4. **Select** a folder with photos/videos
5. **Click Process** \u2014 metadata is generated and embedded

---

## Supported Formats

| Type | Extensions |
|------|------------|
| **Images** | `.jpg`, `.jpeg`, `.png`, `.tiff`, `.tif` |
| **Videos** | `.mp4`, `.mov`, `.m4v`, `.avi`, `.mxf`, `.prores`, `.hevc` |

**Metadata embedding:**
- Images \u2192 EXIF/XMP embedded via bundled exiftool
- `.mov`, `.mp4`, `.m4v`, `.mxf` \u2192 direct embedding
- `.avi`, `.prores`, `.hevc` \u2192 sidecar `.xmp` (format doesn\u2019t support direct embedding)

---

## Installation

### From Release

| Platform | Download | Size |
|----------|----------|------|
| macOS (Apple Silicon) | `*.tar.gz` | ~10 MB |
| Windows (x64) | `*.zip` | ~154 MB |

**macOS:** Extract \u2192 drag `AI Stock Metadata Agent.app` to Applications.

**Windows:** Extract \u2192 run `AI Stock Metadata Agent.exe`.

> **macOS first launch:** Right-click \u2192 Open to bypass Gatekeeper, then confirm the dialog.

### From Source

```bash
git clone https://github.com/cipgysmo/stock-metadata-agent-py.git
cd stock-metadata-agent-py
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python3 main.py
```

---

## Configuration

### Settings Dialog

Open via the **gear icon** (top-right of left panel).

| Section | Setting | Default | Description |
|---------|---------|---------|-------------|
| **Vision** | Endpoint | `http://127.0.0.1:8000` | Ollama/OMLX server URL |
| | API Key | *(empty)* | Key if your server requires one |
| | Model | `Qwen2.5-VL-3B-Instruct-8bit` | Vision model ID |
| **Text** | Reuse Vision Model | \u2612 | Use same endpoint/model for text |
| | Endpoint | *(same as vision)* | Separate text endpoint |
| | API Key | *(empty)* | Text model API key |
| | Model | `Qwen2.5-VL-7B-Instruct-4bit` | Text model ID |
| **Options** | Auto-Learn Location | \u2612 | Store GPS \u2192 location in SQLite |
| | Workers | `2` | Parallel worker count (1\u201316) |
| | Output Format | `Embedded` | Embedded / Sidecar / Both |
| | Duplicate Threshold | `10` | Hash distance for duplicates (1\u201350) |
| **Cloud Fallback** | Enabled | \u2610 | GPT-4o-mini fallback on local failure |
| | Endpoint | `https://api.openai.com` | OpenAI-compatible endpoint |
| | API Key | *(empty)* | OpenAI API key |
| | Model | `gpt-4o-mini` | Cloud model name |

### Settings File

Persisted to `~/.stock-metadata-agent/settings.json`:

```json
{
  "vision_endpoint": "http://127.0.0.1:8000",
  "vision_api_key": "",
  "vision_model": "Qwen2.5-VL-3B-Instruct-8bit",
  "text_endpoint": "http://127.0.0.1:8000",
  "text_api_key": "",
  "text_model": "Qwen2.5-VL-7B-Instruct-4bit",
  "cloud_text_enabled": false,
  "cloud_text_endpoint": "https://api.openai.com",
  "cloud_text_api_key": "",
  "cloud_text_model": "gpt-4o-mini",
  "max_workers": 2,
  "output_format": "embedded",
  "export_csv": true,
  "export_sidecar": false,
  "auto_learn_location": true,
  "image_resize_max": 1280,
  "duplicate_threshold": 10
}
```

---

## Usage

### Batch Processing

1. **Browse** \u2192 select a folder, or paste a path
2. **Review** \u2192 file count appears below the input
3. **Process** \u2192 workers process files in parallel
4. **Progress bar** \u2192 `current/total \u2014 filename`
5. **Cancel** \u2192 50 ms polling loop for snappy cancellation

### Batch Options Card

Expandable card in the left panel:

| Option | Values | Effect |
|--------|--------|--------|
| **Content Type** | Auto (Detect) / Force Editorial / Force Commercial | Override AI-detected type for the whole batch |
| **Export CSV after batch** | \u2612 / \u2610 | Toggle CSV export (persists to settings) |

### Results & Detail Panel

- **Table** \u2013 File + Title columns. Double-click a row to open the file.
- **Detail** \u2013 Click a row: thumbnail, filename, content type, category, full title, keywords. Copy buttons for title and keywords.
- **Stats** \u2013 Processed count, total time, per-file average.

---

## Metadata Specification

### Title & Description

- **Identical** text for both fields
- **180\u2013200 characters** (post-processing enforces)
- **Flowing sentence**(s) ending with a period
- **Structure:** primary subject \u2192 action \u2192 setting \u2192 secondary detail
- **Commercial:** only `.` and `,` \u2014 no dashes, colons, or special characters
- **Editorial:** dateline format \u2014 `"City, Country \u2013 Month DD, YYYY: [sentence]."`
- **Banned words:** stunning, amazing, beautiful, breathtaking, incredible, magnificent, spectacular, wonderful, perfect, superb, excellent, outstanding
- **Location** included only when identifiable features are present

### Keywords

- **10\u201340 keywords**, ordered by relevance
- **Priority pinning:** landmark, city, country, main subject \u2192 first
- **Tier 1:** literal subject terms (what\u2019s in the frame)
- **Tier 2:** context (location type, time of day, demographics)
- **Tier 3:** conceptual / emotional
- **Max 3** per root word, no duplicates, no filler
- **Banned:** stock photography, stock photo, professional photography, high quality, royalty free, etc.

### Content-Type Detection

1. **Vision model** flags: `has_logos`, `needs_model_release`, `needs_property_release`, `editorial_only`
2. **Text model** sets `content_type` based on flags
3. **Override** available via Batch Options card

---

## AI Pipeline

```
┌─────────────┐     ┌──────────────┐     ┌───────────────┐
│   Image /   │\u2192    │  Vision Model  │\u2192    │  Text Model   │
│   Video     │     │  (OMLX local) │     │  (OMLX local) │
└─────────────┘     └──────────────┘     └───────┬───────┘
                                                  │
                                           ┌──────▼───────┐
                                           │ Post-process  │
                                           ├───────────────┤
                                           │ \u2022 Title 180\u2013200  │
                                           │ \u2022 Dash cleanup  │
                                           │ \u2022 Keyword order │
                                           │ \u2022 Banned filter  │
                                           └───────┬───────┘
                                                   │
                                            ┌──────▼───────┐
                                            │   exiftool    │
                                            │  (embed XMP)  │
                                            └──────────────┘
```

### Vision Analysis

Returns structured JSON:

```json
{
  "country": "France",
  "city": "Cancale",
  "landmark": "Mont Saint-Michel",
  "main_subject": "medieval abbey on tidal island",
  "photo_category": "Architecture",
  "visible_objects": ["abbey", "tower", "bridge", "tide"],
  "has_logos": false,
  "has_people": false,
  "needs_model_release": false,
  "editorial_only": false,
  "time_of_day": "midday",
  "weather": "sunny",
  "season": "summer"
}
```

**Videos:** 3\u20137 key frames extracted via ffmpeg \u2192 best frame analyzed \u2192 camera movement detected.

### Text Generation

Receives vision + location context, outputs:

```json
{
  "content_type": "Commercial",
  "title": "[180-200 char sentence]",
  "description": "[same as title]",
  "keywords": ["kw1", "kw2", "..."],
  "top_keywords": ["top1", "...", "top10"],
  "category": "Architecture"
}
```

### Cloud Fallback

If the local text model fails (3 retries, exponential backoff 2s/4s):

1. Local attempt 1 (immediate)
2. Local attempt 2 (after 2 s)
3. Local attempt 3 (after 4 s)
4. **Cloud fallback** (GPT-4o-mini, if enabled)

Same prompt and post-processing pipeline for both paths.

---

## Architecture

### Project Structure

```
stock-metadata-agent-py/
\u251c\u2500\u2500 main.py                      # Entry point, stylesheet theming
\u251c\u2500\u2500 config/
\u2502   \u251c\u2500\u2500 constants.py             # Limits, banned words, formats
\u2502   \u2514\u2500\u2500 settings.py              # JSON settings I/O
\u251c\u2500\u2500 ui/
\u2502   \u251c\u2500\u2500 window.py                # MainWindow, ProcessPage, ResultsView,
\u2502   \u2502                             # ExpandableHeader, BatchOptionsCard
\u2502   \u2514\u2500\u2500 panels/
\u2502       \u2514\u2500\u2500 settings.py          # Settings dialog
\u251c\u2500\u2500 core/
\u2502   \u251c\u2500\u2500 orchestrator.py          # Batch orchestrator, parallel workers
\u2502   \u251c\u2500\u2500 scanner.py               # File discovery
\u2502   \u251c\u2500\u2500 duplicate.py             # Perceptual hash detection
\u2502   \u251c\u2500\u2500 location/
\u2502   \u2502   \u251c\u2500\u2500 parser.py            # Location string normalization
\u2502   \u2502   \u2514\u2500\u2500 gps.py               # EXIF GPS reader, reverse geocode
\u2502   \u251c\u2500\u2500 metadata/
\u2502   \u2502   \u251c\u2500\u2500 writer.py            # EXIF/XMP embedding (exiftool)
\u2502   \u2502   \u2514\u2500\u2500 sidecar.py           # .xmp sidecar writing
\u2502   \u251c\u2500\u2500 quality/
\u2502   \u2502   \u2514\u2500\u2500 scorer.py            # Quality scoring
\u2502   \u2514\u2500\u2500 video/
\u2502       \u251c\u2500\u2500 extractor.py         # Key-frame extraction (ffmpeg)
\u2502       \u2514\u2500\u2500 movement.py          # Camera movement detection
\u251c\u2500\u2500 ai/
\u2502   \u251c\u2500\u2500 client.py                # HTTP client (OMLX + OpenAI)
\u2502   \u251c\u2500\u2500 vision.py                # Vision prompt, parsing
\u2502   \u2514\u2500\u2500 generator.py             # Text prompt, generation, post-process
\u251c\u2500\u2500 export/
\u2502   \u2514\u2500\u2500 csv.py                   # CSV batch export
\u251c\u2500\u2500 db/
\u2502   \u2514\u2500\u2500 memory.py                # SQLite location memory
\u251c\u2500\u2500 resources/
\u2502   \u251c\u2500\u2500 exiftool-mac/            # Bundled exiftool (macOS)
\u2502   \u251c\u2500\u2500 exiftool-win/            # Bundled exiftool (Windows)
\u2502   \u2514\u2500\u2500 icon.png                 # App icon
\u251c\u2500\u2500 tests/
\u2502   \u2514\u2500\u2500 test_all.py              # Unit tests
\u251c\u2500\u2500 requirements.txt
\u251c\u2500\u2500 pyproject.toml
\u251c\u2500\u2500 stock-metadata-agent.spec      # PyInstaller spec
\u251c\u2500\u2500 build.sh                       # macOS build script
\u2514\u2500\u2500 build.bat                      # Windows build script
```

### Processing Pipeline (per file)

```
 1. SCAN       \u2192 discover file, type (image/video)
 2. GPS        \u2192 read EXIF GPS, reverse geocode
 3. VISION     \u2192 analyze with vision model
 4. DUPLICATE  \u2192 perceptual hash check
 5. TEXT       \u2192 generate title, description, keywords
 6. POST-PROC  \u2192 enforce title length, reorder keywords, filter banned
 7. QUALITY    \u2192 score and flag issues
 8. WRITE      \u2192 embed EXIF/XMP or write sidecar
```

**Parallelism:**
- GPS + Vision run concurrently
- Text generation rate-limited (3 concurrent via semaphore)
- Files processed in parallel via `ThreadPoolExecutor` (1\u201316 workers)

---

## Building from Source

### macOS

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt pyinstaller
pyinstaller --clean stock-metadata-agent.spec
# \u2192 dist/AI Stock Metadata Agent.app
```

### Windows

```batch
python -m venv .venv && .venv\Scripts\activate
pip install -r requirements.txt pyinstaller
pyinstaller --clean stock-metadata-agent.spec
REM \u2192 dist\AI Stock Metadata Agent.exe
```

### GitHub Actions (Windows)

The included `.github/workflows/build-windows.yml` builds on Ubuntu + Wine for cross-compilation. Trigger via Actions \u2192 **Run workflow**.

---

## Location Memory

When **Auto-Learn Location** is enabled, GPS \u2192 city/country/region mappings are stored in `~/.stock-metadata-agent/location_memory.db` (SQLite). Subsequent batches look up coordinates before calling the vision model, ensuring consistency and speed.

---

## Duplicate Detection

Uses perceptual hashing ([imagehash](https://github.com/JohannesBuchner/imagehash)):
- **Duplicate:** hash distance \u2264 threshold (default 10)
- **Near-duplicate:** hash distance \u2265 threshold and \u2264 30

Duplicates are still processed but flagged in the quality report.

---

## Quality Validation

| Check | Rule |
|-------|------|
| Title length | 180\u2013200 characters |
| Keyword count | 10\u201340 |
| Keyword duplicates | none |
| Banned words | not present in title |
| Empty fields | title, description, keywords required |

---

## CSV Export

When enabled, produces `metadata_export.csv` in the source folder:

| Column | Content |
|--------|---------|
| `filename` | Original filename |
| `title` | Generated title |
| `keywords` | Comma-separated |
| `content_type` | Commercial / Editorial |
| `category` | Category label |
| `quality_score` | Score (0\u2013100) |
| `issues` | Flagged issues (if any) |

---

## Troubleshooting

### \u201cMissing required settings\u201d

Configure vision endpoint + model in Settings before processing.

### Vision model returns empty

- Verify server: `curl http://127.0.0.1:8000/v1/models`
- Ensure the model is loaded and accepting requests
- Check `image_resize_max` (default 1280)

### Text generation falls back to cloud

- The local model may be too small; try 7B+
- Check server logs for context overflow
- Ensure `max_tokens` \u2265 1500

### exiftool errors on macOS

- First launch: right-click app \u2192 Open to bypass Gatekeeper
- Or install system-wide: `brew install exiftool`

### Video frame extraction fails

- Install ffmpeg: `brew install ffmpeg` (macOS) or `choco install ffmpeg` (Windows)

---

## Changelog

### v0.1.1 (2026-08-09)
- Batch Options card with Content Type override and CSV toggle
- Keyword reordering (landmark/city/country/subject pinned front)
- Commercial title dash cleanup
- Banned keyword filter expanded
- Keyword count relaxed to 10\u201340
- Windows double-click file open fix
- UI: removed status column, consolidated stats row

### v0.1.0 (2026-08-09)
- Initial release

---

## License

MIT
