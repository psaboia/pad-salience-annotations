# PAD Salience Annotation Prototype - Specifications

## Overview

A web-based annotation tool for specialists to mark salient regions on PAD (Paper Analytical Device) card images while recording audio explanations.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Browser (Frontend)                       │
│  ┌─────────────────────────────────────────────────────────┐│
│  │  prototype/index.html                                   ││
│  │  - Canvas-based annotation                              ││
│  │  - Audio recording (MediaRecorder API)                  ││
│  │  - Auto lane detection                                  ││
│  └─────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼ POST /api/save-annotation
┌─────────────────────────────────────────────────────────────┐
│                     Server (Backend)                         │
│  ┌─────────────────────────────────────────────────────────┐│
│  │  server.py (FastAPI)                                    ││
│  │  - Serves static files                                  ││
│  │  - Saves annotations to JSONL                           ││
│  │  - Saves audio files separately                         ││
│  └─────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                     Data Storage                             │
│  data/                                                       │
│  ├── annotations.jsonl    (all annotation sessions)          │
│  └── audio/               (audio files by session_id)        │
│      ├── session_xxx.webm                                    │
│      └── ...                                                 │
└─────────────────────────────────────────────────────────────┘
```

---

## Annotation Tools

### 1. Rectangle Tool
- Draw bounding boxes by click-drag
- Best for: Quickly selecting lane regions

### 2. Polygon Tool
- Freehand drawing that auto-closes to form a polygon
- Best for: Irregular shapes, artifacts, bleeding areas

### Decision Rationale
Both tools provided because:
- Rectangles are faster for standard lane annotations
- Polygons needed for real-world imperfections (smudges, bleeding, artifacts)
- Specialist can choose based on the specific annotation

---

## Lane Detection

### Automatic Detection
Lanes are detected automatically based on the X-coordinate of the annotation.

### Configuration (for 730px wide processed images)
```javascript
const LANE_CONFIG = {
    startPercent: 0.082,  // ~60px - where lanes start
    endPercent: 0.986,    // ~720px - where lanes end
    lanes: ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J', 'K', 'L']
};
```

### Lane Boundaries (calculated)
| Lane | X Start | X End |
|------|---------|-------|
| A    | 60px    | 115px |
| B    | 115px   | 170px |
| C    | 170px   | 225px |
| D    | 225px   | 280px |
| E    | 280px   | 335px |
| F    | 335px   | 390px |
| G    | 390px   | 445px |
| H    | 445px   | 500px |
| I    | 500px   | 555px |
| J    | 555px   | 610px |
| K    | 610px   | 665px |
| L    | 665px   | 720px |

### Visual Feedback
- **Cursor tooltip**: Shows current lane (e.g., "Lane F") following the cursor
- Appears directly above cursor position for immediate feedback
- Shows "Outside" when cursor is outside lane boundaries

### Decision Rationale
- Manual lane selection was removed - too much cognitive load
- Auto-detection based on position is intuitive and faster
- Tooltip provides immediate feedback without looking away from annotation area

---

## Audio Recording

### Approach: Continuous Recording
- Audio records continuously during the annotation session
- Each annotation captures start/end timestamps relative to recording start

### Timestamps per Annotation
```json
{
    "timestamp_start_ms": 12500,  // When drawing started
    "timestamp_end_ms": 15800     // When drawing completed
}
```

### Decision Rationale
- Continuous recording captures natural explanation flow
- Start/end timestamps allow extraction of specific audio segments
- Better than per-region recording: less interruption, captures transitions
- Post-processing can align transcriptions to specific annotations

### Audio Storage
- Format: WebM (browser native)
- Saved separately: `data/audio/session_xxx.webm`
- Reference stored in JSONL (not base64 embedded)

---

## Data Format

### Storage: JSONL
One JSON object per line in `data/annotations.jsonl`.

### Session Schema
```json
{
  "session_id": "session_1768229766121",
  "timestamp": "2026-01-12T14:56:06.121Z",
  "sample": {
    "drug_name": "Amoxicillin",
    "card_id": 15214,
    "filename": "amoxicillin_15214_processed.png",
    "path": "sample_images/amoxicillin_15214_processed.png",
    "image_type": "processed"
  },
  "image_dimensions": {
    "width": 730,
    "height": 1220
  },
  "annotations": [...],
  "audio": {
    "format": "webm",
    "filename": "session_1768229766121.webm",
    "duration_ms": 45000
  },
  "specialist_id": null,
  "specialist_expertise": null
}
```

### Annotation Schema
```json
{
  "id": 1768229699409,
  "type": "rectangle",
  "color": "#00d4ff",
  "lanes": ["F"],
  "timestamp_start_ms": 12500,
  "timestamp_end_ms": 15800,
  "bbox": {
    "x": 343.88,
    "y": 363.99,
    "width": 40.99,
    "height": 138
  },
  "bbox_normalized": {
    "x1": 471,
    "y1": 298,
    "x2": 527,
    "y2": 411
  }
}
```

### Coordinate Normalization
- **Raw coordinates**: Pixel values for the specific image
- **Normalized coordinates**: 0-999 range (resolution independent)
- Format matches DeepSeek-OCR style: `[x1, y1, x2, y2]`

### Decision Rationale
- JSONL format: Easy to append, load with pandas/HuggingFace datasets
- Normalized coordinates: Compatible with VLM fine-tuning (DeepSeek-OCR style)
- Audio stored separately: Keeps JSONL manageable, allows flexible audio processing

---

## Sample Images

### Source
- Project: FHI2020 from Notre Dame PAD Project
- Accessed via: `pad-analytics` Python package

### Image Type
- **Processed images** (not raw)
- Cropped and rotated to show lanes A-L vertically
- Standard dimensions: ~730 x 1220 pixels

### Included Drugs (26 samples)
Albendazole, Amoxicillin, Ampicillin, Ascorbic Acid, Azithromycin,
Benzyl Penicillin, Calcium Carbonate, Ceftriaxone, Chloroquine,
Ciprofloxacin, Doxorubicin, Doxycycline, Epinephrine, Ethambutol,
Ferrous Sulfate, Hydroxychloroquine, Isoniazid, Lactose,
Promethazine Hydrochloride, Pyrazinamide, Rifampicin, RIPE,
Starch (Maize), Sulfamethoxazole, Tetracycline, Unknown

---

## UI/UX Decisions

### Color Options
5 annotation colors available:
- `#00d4ff` (cyan) - default
- `#ff4757` (red)
- `#2ed573` (green)
- `#ffa502` (orange)
- `#a55eea` (purple)

### Workflow
1. Select drug sample from left panel
2. Click "Start Recording" to begin audio capture
3. Draw annotations on the PAD card image
4. Lanes detected automatically, shown in tooltip
5. Click "Export" to save (auto-stops recording)
6. Use "Start New Session" to clear and start over

### Feedback
- Annotations persist after export (can continue annotating)
- Confirmation shows annotation count and audio status
- Fallback to local file download if server unavailable

---

## Running the Prototype

### Start Server
```bash
./run_prototype.sh
```

### Access
Open http://localhost:8765 in browser

### Data Location
- Annotations: `data/annotations.jsonl`
- Audio files: `data/audio/`

---

## Future Enhancements (Not in Prototype)

- [ ] Specialist identification and expertise level
- [ ] Audio transcription integration (OpenAI API)
- [ ] Export pipeline to DeepSeek-OCR format
- [ ] Review/validation workflow
- [ ] Internet connectivity handling
- [ ] Different PAD configurations support
