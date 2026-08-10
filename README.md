# AI Stock Metadata Agent

**Desktop application for automatically generating and embedding stock photography metadata using local AI models.**

Process hundreds of images and videos in batch — generating titles, descriptions, and keywords that conform to a universal metadata spec compatible with Shutterstock, Adobe Stock, Getty/iStock, Alamy, and other agencies.

---

## Table of Contents

- [Features](#features)
- [Quick Start](#quick-start)
- [Supported Formats](#supported-formats)
- [Installation](#installation)
  - [From Release (Recommended)](#from-release-recommended)
  - [From Source](#from-source)
- [Configuration](#configuration)
  - [Settings Dialog](#settings-dialog)
  - [Settings File](#settings-file)
- [Usage](#usage)
  - [Batch Processing](#batch-processing)
  - [Batch Options Card](#batch-options-card)
  - [Results & Detail Panel](#results--detail-panel)
- [Metadata Specification](#metadata-specification)
  - [Title & Description](#title--description)
  - [Keywords](#keywords)
  - [Content Type Detection](#content-type-detection)
- [AI Pipeline](#ai-pipeline)
  - [Vision Analysis](#vision-analysis)
  - [Text Generation](#text-generation)
  - [Cloud Fallback](#cloud-fallback)
- [Architecture](#architecture)
  - [Project Structure](#project-structure)
  - [Core Modules](#core-modules)
  - [Processing Pipeline](#processing-pipeline)
- [Building from Source](#building-from-source)
  - [macOS](#macos)
  - [Windows](#windows)
  - [Linux](#linux)
- [Location Memory](#location-memory)
- [Duplicate Detection](#duplicate-detection)
- [Quality Validation](#quality-validation)
- [CSV Export](#csv-export)
- [Troubleshooting](#troubleshooting)
- [Changelog](#changelog)
- [License](#license)

---

## Features

- **Batch Processing** — Process entire folders of images and videos with configurable parallel workers (1-16)
- **Local AI Models** — Runs entirely offline using local OLLAMA/OMLX instances; no cloud dependency required
- **Vision Analysis** — Analyzes images and video frames for subject, location, objects, people, logos, and commercial safety
- **Smart Metadata** — Generates titles, descriptions, and keywords following a universal spec compatible with all major stock agencies
- **GPS & Location Parsing** — Reads EXIF GPS data, reverse geocodes via local model, stores in a persistent SQLite memory database
- **Duplicate Detection** — Identifies duplicate and near-duplicate images using perceptual hashing (imagehash)
- **Quality Scoring** — Validates metadata quality and flags issues (length, missing fields, banned words, duplicates)
- **Editorial Detection** — Detects logos, identifiable people, and property that require editorial licensing
- **Content Type Override** — Force all files in a batch to Editorial or Commercial from the Batch Options card
- **Cloud Fallback** — Optional OpenAI/GPT-4o-mini fallback if the local text model fails
- **Multiple Output Formats** — Embedded metadata (EXIF/XMP), sidecar `.xmp` files, or both
- **CSV Export** — Optional CSV export of all generated metadata for review or bulk import
- **Desktop UI** — PySide6 application with dark/light theme support, thumbnail previews, and keyword copy buttons
- **Cross-Platform** — Runs on macOS (Apple Silicon), Windows (x64), and Linux

---

## Quick Start

1. **Download** the latest release for your platform from [Releases](https://github.com/cipgysmo/stock-metadata-agent-py/releases)
2. **Start a local OLLAMA/OMLX server** with a vision model (e.g., `Qwen2.5-VL-3B-Instruct-8bit`)
3. **Open the app**, go to Settings (gear icon), and enter your local model endpoint
4. **Select a folder** with your photos/videos
5. **Click Process** — the app will generate and embed metadata into all files

---

## Supported Formats

| Type | Formats |
|------|---------|
| **Images** | `.jpg`, `.jpeg`, `.png`, `.tiff`, `.tif` |
| **Videos** | `.mp4`, `.mov`, `.m4v`, `.avi`, `.mxf`, `.prores`, `.hevc` |

**Metadata embedding:**
- Images: EXIF/XMP embedded directly via exiftool
- Videos (.mov, .mp4, .m4v, .mxf): Direct embedding via exiftool
- Videos (.avi, .prores, .hevc): Sidecar `.xmp` file (format doesn't support direct embedding)

---

## Installation

### From Release (Recommended)

Download from [Releases](https://github.com/cipgysmo/stock-metadata-agent-py/releases):

| Platform | File | Size |
|----------|------|------|
| macOS (Apple Silicon) | `*.tar.gz` | ~10 MB |
| Windows (x64) | `*.zip` | ~154 MB |

**macOS:** Extract the `.tar.gz`, then drag `AI Stock Metadata Agent.app` to Applications.

**Windows:** Extract the `.zip`, run `AI Stock Metadata Agent.exe`.

> **First launch on macOS:** You may need to right-click → Open, then confirm the security dialog to allow the unsigned app to run.

### From Source

```bash
# Clone the repository
git clone https://github.com/cipgysmo/stock-metadata-agent-py.git
cd stock-metadata-agent-py

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run directly
python main.py
```

---

## Configuration

### Settings Dialog

Click the **gear icon** in the top-right of the left panel to open Settings.

| Section | Setting | Description |
|---------|---------|-------------|
| **Vision Model** | Endpoint | URL of your local OLLAMA/OMLX server (default: `http://127.0.0.1:8000`) |
| | API Key | API key if required (leave empty for local) |
| | Model Name | Vision model ID (e.g., `Qwen2.5-VL-3B-Instruct-8bit`) |
| **Text Model** | Reuse Vision | Checkbox to use the same endpoint/model for text generation |
| | Endpoint | Separate text model endpoint |
| | API Key | Text model API key |
| | Model Name | Text model ID (e.g., `Qwen2.5-VL-7B-Instruct-4bit`) |
| **Options** | Auto-Learn Location | Store GPS→location mappings in SQLite database for future reuse |
| | Workers | Parallel worker count (1-16) |
| | Output Format | `Embedded` (direct), `Sidecar` (.xmp), or `Both` |
| | Duplicate Threshold | Perceptual hash distance for duplicate detection (1-50, default: 10) |
| **Cloud Text Fallback** | Enabled | Enable GPT-4o-mini fallback when local text model fails |
| | Endpoint | OpenAI API endpoint (default: `https://api.openai.com`) |
| | API Key | OpenAI API key |
| | Model | Cloud model name (default: `gpt-4o-mini`) |

### Settings File

Settings are stored at `~/.stock-metadata-agent/settings.json`:

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

1. **Select Folder** — Click "Browse" or paste a path into the folder input field
2. **Review File Count** — The app counts supported files (images + videos) in the selected folder
3. **Click Process** — Batch processing begins with parallel workers
4. **Monitor Progress** — The bottom progress bar shows `current/total` and current file name
5. **Cancel** — Click Cancel at any time to stop processing (uses a 50ms polling loop for snappy cancellation)

### Batch Options Card

The expandable **Batch Options** card in the left panel provides batch-level settings:

| Option | Values | Description |
|--------|--------|-------------|
| **Content Type** | Auto (Detect), Force Editorial, Force Commercial | Override the AI-detected content type for the entire batch |
| **Export CSV after batch** | Checked/Unchecked | Toggle CSV export on/off (stored in settings) |

### Results & Detail Panel

After processing, the right panel shows:

- **Results Table** — Two columns (File, Title). Double-click a file to open it in the default application.
- **Detail Panel** — Click any row to see:
  - Thumbnail preview (images and video frames)
  - Filename, Content Type (Commercial/Editorial), Category
  - Full title with copy button
  - All keywords (comma-separated) with copy button
- **Stats Row** — Processed count, total time, and per-file average time

---

## Metadata Specification

The app generates metadata following a universal spec that works across all major stock agencies.

### Title & Description

- **Identical text** for title and description (required by some agencies)
- **180-200 characters** (target range, enforced by post-processing)
- **Flowing sentence** format, one or two complete sentences ending with a period
- **Lead with** primary subject → action → setting → secondary detail
- **Commercial titles** use only periods (`.`) and commas (`,`) — no dashes, colons, or special characters
- **Editorial titles** use dateline format: `"City, Country - Month DD, YYYY: [factual sentence]."`
- **Banned words**: stunning, amazing, beautiful, breathtaking, incredible, magnificent, spectacular, wonderful, perfect, superb, excellent, outstanding
- **Location** included only when identifiable geographic features are present

**Example (194 chars):**
> Young woman works on a laptop at a wooden desk in a bright modern home office, surrounded by houseplants and natural light streaming through a large window.

### Keywords

- **10-40 keywords**, ordered by priority
- **Tier 1 (first 15-20)**: Literal subject terms — what is physically in the frame
- **Tier 2 (next 10-15)**: Context terms — location type, time of day, composition, demographics
- **Tier 3 (last 5-10)**: Conceptual/emotional terms — what the image represents
- **Max 3 keywords** sharing the same root word
- **No duplicates**, no filler
- **Priority ordering**: Landmark, city, country, and main subject keywords are pinned to the front
- **Banned keywords**: stock photography, stock photo, professional photography, high quality, royalty free, and other zero-value terms
- **Pipe characters** (`|`) in LLM output are split into separate keywords

### Content Type Detection

The app determines Commercial vs Editorial through a two-stage process:

1. **Vision model** analyzes the image for:
   - `has_logos` — visible brand logos, trademarks, or company names
   - `needs_model_release` — clearly identifiable people (faces)
   - `needs_property_release` — unique private buildings or interiors
   - `editorial_only` — combined editorial content flag

2. **Text model** receives vision flags and sets `content_type`:
   - If logos or editorial content detected → `"Editorial"`
   - Otherwise → `"Commercial"`

**Override:** Use the Batch Options card to force Editorial or Commercial for the entire batch.

---

## AI Pipeline

### Vision Analysis

The vision model (e.g., `Qwen2.5-VL-3B-Instruct-8bit`) analyzes each image or video frame and returns structured JSON:

```json
{
  "country": "France",
  "city": "Saint-Michel-en-Greffeuille",
  "landmark": "Mont Saint-Michel",
  "main_subject": "medieval abbey on tidal island",
  "photo_category": "Architecture",
  "visible_objects": ["abbey", "tower", "bridge", "tide", "sky", "clouds"],
  "has_logos": false,
  "has_people": false,
  "needs_model_release": false,
  "editorial_only": false,
  "time_of_day": "midday",
  "weather": "sunny",
  "season": "summer"
}
```

**For videos:** The app extracts key frames (3-7 frames), analyzes the best frame, and detects camera movement.

### Text Generation

The text model receives vision analysis results, GPS data, and location context, then generates:

```json
{
  "content_type": "Commercial",
  "title": "[180-200 char flowing sentence]",
  "description": "[same as title]",
  "keywords": ["keyword1", "keyword2", "..."],
  "top_keywords": ["top1", "top2", "...", "top10"],
  "category": "Architecture"
}
```

**Post-processing:**
- Title length enforced: truncated at 200 chars if over, expanded with factual clauses if under 180
- Commercial titles: dashes/hyphens replaced with commas
- Keywords: banned terms filtered, priority terms pinned to front, duplicates removed, pipes split

### Cloud Fallback

When the local text model fails (after 3 retries with exponential backoff), the app optionally falls back to OpenAI's GPT-4o-mini:

1. Local model attempt 1 (immediate)
2. Local model attempt 2 (after 2s delay)
3. Local model attempt 3 (after 4s delay)
4. Cloud fallback (if enabled in Settings)

The fallback uses the same prompt and post-processing pipeline as the local model.

---

## Architecture

### Project Structure

```
stock-metadata-agent-py/
├── main.py                      # Application entry point, UI theming
├── config/
│   ├── constants.py             # Limits, banned words, supported formats
│   └── settings.py              # Settings file I/O, validation
├── ui/
│   ├── window.py                # Main window, batch options, results table, detail panel
│   └── panels/
│       └── settings.py          # Settings dialog with model endpoints, workers, cloud fallback
├── core/
│   ├── orchestrator.py          # Batch processing orchestrator, parallel workers, abort handling
│   ├── scanner.py               # File discovery, format validation
│   ├── duplicate.py             # Perceptual hash duplicate detection (imagehash)
│   ├── quality/
│   │   └── scorer.py            # Metadata quality scoring and validation
│   ├── location/
│   │   ├── parser.py            # Location string parsing and normalization
│   │   └── gps.py               # EXIF GPS reading, reverse geocoding
│   ├── metadata/
│   │   ├── writer.py            # EXIF/XMP embedding via bundled exiftool
│   │   └── sidecar.py           # Sidecar .xmp file writing
│   └── video/
│       ├── extractor.py         # Key frame extraction (ffmpeg + opencv)
│       └── movement.py          # Camera movement detection from frames
├── ai/
│   ├── client.py                # HTTP client for OLLAMA/OMLX and OpenAI APIs
│   ├── vision.py                # Vision model prompt, analysis parsing
│   └── generator.py             # Text model prompt, metadata generation, post-processing
├── export/
│   └── csv.py                   # CSV export of batch metadata
├── db/
│   └── memory.py                # SQLite location memory database
├── resources/
│   ├── exiftool-mac/            # Bundled exiftool binary (macOS)
│   ├── exiftool-win/            # Bundled exiftool binary (Windows)
│   └── icon.png                 # Application icon
├── tests/
│   └── test_all.py              # Unit tests
├── requirements.txt             # Python dependencies
├── pyproject.toml               # Project metadata
├── stock-metadata-agent.spec    # PyInstaller build configuration
├── build.sh                     # macOS build script
└── build.bat                    # Windows build script
```

### Core Modules

| Module | Responsibility |
|--------|---------------|
| `BatchOrchestrator` | Orchestrates the full pipeline: scan → GPS → vision → text → write. Manages parallel workers, abort signals, and progress callbacks. |
| `Scanner` | Walks the input directory, filters by supported extensions, returns `MediaFile` list. |
| `GPSValidator` | Reads EXIF GPS coordinates via exiftool, reverse geocodes to city/country/region. |
| `VisionAnalyzer` | Sends image/frame to vision model, parses structured JSON response. |
| `MetadataGenerator` | Sends vision + location context to text model, parses response, applies post-processing. |
| `MetadataWriter` | Embeds title, description, keywords, content type into files via exiftool. |
| `XmpSidecarWriter` | Generates `.xmp` sidecar files for formats that don't support direct embedding. |
| `DuplicateDetector` | Computes perceptual hashes (imagehash) to find duplicate/near-duplicate images. |
| `QualityValidator` | Scores metadata quality: title length, keyword count, banned words, duplicates. |
| `LocationMemory` | SQLite database that stores GPS→location mappings for reuse across batches. |

### Processing Pipeline

For each file in a batch:

```
1. SCAN         → Discover file, determine type (image/video)
2. GPS          → Read EXIF GPS, reverse geocode to location
3. VISION       → Analyze image/frame with vision model
   ├─ Image:  send full image
   └─ Video:  extract key frames → analyze best frame → detect movement
4. DUPLICATE    → Perceptual hash check against already-processed files
5. TEXT         → Generate title, description, keywords with text model
   ├─ Post-process title (length enforcement, dash cleanup)
   ├─ Reorder keywords (pin landmark/city/country/subject to front)
   ├─ Filter banned keywords
   └─ Apply content type override if set
6. QUALITY      → Validate metadata quality, flag issues
7. WRITE        → Embed metadata (EXIF/XMP) and/or write sidecar
```

**Parallelism:**
- GPS + Vision run concurrently (both are I/O bound)
- Text generation is sequential but rate-limited by semaphore (3 concurrent max)
- Multiple files processed in parallel via `ThreadPoolExecutor` (configurable 1-16 workers)

---

## Building from Source

### macOS

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt pyinstaller
pyinstaller --clean stock-metadata-agent.spec
# Result: dist/AI Stock Metadata Agent.app
```

### Windows

```batch
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt pyinstaller
pyinstaller --clean stock-metadata-agent.spec
REM Result: dist\AI Stock Metadata Agent.exe
```

Or use the included `build.bat` script.

### Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt pyinstaller
pyinstaller --clean stock-metadata-agent.spec
# Result: dist/AI Stock Metadata Agent
```

---

## Location Memory

When **Auto-Learn Location** is enabled, the app stores GPS→location mappings in a SQLite database at `~/.stock-metadata-agent/location_memory.db`.

On subsequent runs, files with matching GPS coordinates are looked up first before calling the vision model, providing:
- **Consistency** — Same coordinates always map to the same location
- **Speed** — Skips vision model call for known locations
- **Fallback** — Vision model still called for new coordinates, results stored

---

## Duplicate Detection

Uses perceptual hashing (via the `imagehash` library) to detect duplicate and near-duplicate images:

- **Duplicate** — Perceptual hash distance ≤ `duplicate_threshold` (default: 10)
- **Near-duplicate** — Hash distance between threshold and `similar_threshold` (default: 30)

Duplicate files are still processed (metadata is generated), but flagged in the quality report for review.

---

## Quality Validation

The `QualityValidator` scores each file's metadata and reports issues:

| Check | Description |
|-------|-------------|
| Title length | Must be 180-200 characters |
| Keyword count | Must be 10-40 keywords |
| Keyword duplicates | No duplicate keywords |
| Banned words | Titles must not contain banned adjectives |
| Empty fields | Title, description, and keywords must not be empty |

Files with quality issues are still processed and embedded, but flagged for review.

---

## CSV Export

When **Export CSV after batch** is enabled, the app generates a CSV file (`metadata_export.csv`) in the source folder after batch completion:

| Column | Content |
|--------|---------|
| `filename` | Original filename |
| `title` | Generated title/description |
| `keywords` | Comma-separated keywords |
| `content_type` | Commercial or Editorial |
| `category` | Photo category |
| `quality_score` | Quality validation score |
| `issues` | Comma-separated quality issues (if any) |

---

## Troubleshooting

### "Missing required settings" error

The vision and text model endpoints must be configured in Settings before processing. Ensure:
- `Vision Endpoint` is set (e.g., `http://127.0.0.1:8000`)
- `Vision Model` is set (e.g., `Qwen2.5-VL-3B-Instruct-8bit`)
- Either `Reuse Vision Model for Text` is checked, or text model is configured separately

### Vision model returns empty response

- Check that your OLLAMA/OMLX server is running and accessible
- Verify the model is loaded and accepting requests
- Test with `curl http://127.0.0.1:8000/v1/models` to confirm the API is responsive
- Increase `image_resize_max` in settings if the model struggles with image resolution

### Text generation fails / falls back to cloud

- The local text model may be too small for the task; try a larger model (7B+)
- Check server logs for context overflow or timeout errors
- Ensure `max_tokens` in the request is sufficient (default: 1500)

### exiftool errors on macOS

- The bundled exiftool should work out of the box
- If permission errors occur, try right-clicking the app → Open on first launch
- You can also install exiftool system-wide: `brew install exiftool`

### Video frame extraction fails

- Requires `ffmpeg` to be installed: `brew install ffmpeg` (macOS) or `choco install ffmpeg` (Windows)
- Check that the video file is not corrupted and can be played normally

### "File not found" when double-clicking results

This is expected if the source files were moved or renamed after processing. The results table references original file paths.

---

## Changelog

### v0.1.8 (2026-08-10)
- **Model readiness fix**: Only polls local endpoints (localhost, LAN), skips cloud endpoints
- **Shorter poll timeout**: 10s per poll instead of 120s, preventing hangs while model loads
- **Progress feedback**: Shows elapsed seconds during model loading

### v0.1.7 (2026-08-10)
- **Metadata fix**: Correct XMP embedding — uses composite tags that work on all JPEGs
- **Metadata fix**: Keywords now properly replace existing keywords (no accumulation)
- **Metadata verification**: Post-write read-back validates all 4 fields
- **Sidecar fix**: Proper XMP `<rdf:Bag>` with `<rdf:li>` elements
- **Combo arrows fixed**: Native OS arrows on all platforms (was broken on macOS/Windows)
- **Cleaner logs**: exiftool path logged once instead of per-file
- **Code cleanup**: Removed unused imports across 15 files, dropped tenacity dependency

### v0.1.6 (2026-08-10)
- **Instant file list**: Files appear immediately in results table before processing starts
- **Live spinners**: Animated blue spinner per row shows which files are currently processing
- **Cancel on Windows**: Fixed button state and semaphore timeouts for instant cancel response
- **Detail panel refresh**: Auto-refreshes title, keywords, and thumbnail when selected file finishes
- **Unprocessed file selection**: Shows 'Queued' status instead of crashing
- **Rerun button**: Only visible after file has been processed
- **Consistent spacing**: All gaps between panes and sections are now uniform
- **Vertically centered stats**: Final summary text is properly centered

### v0.1.5 (2026-08-10)
- **Model readiness check**: Waits for AI model to load before processing (120s timeout)
- **Regenerate per file**: Rerun button per row to regenerate vision + text for a single file
- **Spinning indicator**: Animated spinner during regeneration
- **Detail panel refresh**: Title, keywords, and metadata update after regeneration
- **CSV auto-refresh**: CSV export updates after each regeneration
- **Underscore keyword fix**: Sanitizes underscored keywords (e.g., `wind_farm` → `wind farm`)
- **Solar panel bias fix**: Removes contradictory tech keywords for wind farm images
- **Font warning fix**: Removed `sans-serif` fallback from stylesheet

### v0.1.1 (2026-08-09)
- **Batch Options card**: Expandable panel with batch-level settings
- **Content Type override**: Force Editorial or Commercial for entire batch
- **Export CSV toggle**: Moved from Settings to Batch Options card
- **Keyword reordering**: Landmark, city, country, subject keywords pinned to front
- **Commercial title cleanup**: Dashes and hyphens replaced with commas
- **Banned keyword filter**: Removed zero-value keywords from output
- **Keyword count relaxed**: 10-40 range (was 30-35) to reduce LLM spam padding
- **Windows double-click fix**: Use `os.startfile()` on Windows
- **UI cleanup**: Removed status column from table, consolidated stats into single row

### v0.1.0 (2026-08-09)
- Initial release
- Batch processing with parallel workers (1-16)
- Vision analysis with local OLLAMA models
- Text metadata generation with local + cloud fallback
- Universal metadata spec: 180-200 char titles, 10-40 keywords
- GPS/location parsing with SQLite memory database
- Duplicate detection with perceptual hashing
- Quality scoring and validation
- Embedded metadata via exiftool, sidecar support, CSV export
- PySide6 desktop UI with dark/light theme
- macOS (Apple Silicon) and Windows (x64) builds

---

## License

MIT
