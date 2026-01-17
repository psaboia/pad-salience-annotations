# PAD Salience Annotations System - Requirements

## Project Overview

A system for capturing annotations from specialists over images of PAD (Paper Analytical Device) cards. The goal is to build a multimodal dataset that can be used for training AI systems and/or working with LLMs.

## Background: What is PAD?

**PAD (Paper Analytical Device)** is a paper-based test card developed by the Notre Dame PAD Project for screening pharmaceutical quality.

<p align="center">
  <img src="../sample_images/amoxicillin_15214_processed.png" alt="PAD Card Example - Amoxicillin" width="300">
  <br>
  <em>Example PAD card showing 12 lanes (A-L) with color reactions for Amoxicillin</em>
</p>

### Key characteristics:
- Small, inexpensive (~$2 USD) paper-based test cards
- Used to detect whether drug tablets contain correct active ingredients or adulterants
- Requires no electricity or complex equipment
- Can be used by non-specialists in field settings after minimal training
- Results available within ~5 minutes
- Particularly valuable for identifying counterfeit/low-quality medicines in low-resource settings

### PAD Structure:
- Contains **12 lanes (A-L)**, each with different chemical reagents
- Sample is swiped across all lanes, then water is added
- Water wicks up the card, carrying the sample through the reagent lanes
- Each lane produces a **color reaction** with the substance
- The combination of colors across lanes creates a **"barcode" or "fingerprint"** unique to each substance
- Typically **3-5 lanes are most relevant** for identifying a specific drug type

### References:
- [Notre Dame PAD Project](https://padproject.nd.edu/)
- [idPAD: Paper Analytical Device for Presumptive Identification - PMC](https://pmc.ncbi.nlm.nih.gov/articles/PMC7332374/)
- [USP Technology Review: PAD](https://www.usp.org/sites/default/files/usp/document/our-work/global-public-health/usp-paper-analytical-device-pad.pdf)

---

## Core Functionality

The system must allow specialists to:

1. **View PAD card images** for annotation
2. **Highlight specific regions** within the image where they observe meaningful information
3. **Record audio explanations** while selecting areas, capturing their reasoning process
4. **Associate metadata** with each PAD image (drug type, distractor type, etc.)

---

## Data Architecture

The system uses a **two-layer architecture** to preserve raw captured data while enabling flexible export to various training formats.

```
┌─────────────────────────────────────────────────────┐
│                   RAW DATA LAYER                    │
│       (Preserve everything from interface)          │
├─────────────────────────────────────────────────────┤
│  - Original freeform region shapes (full polygons)  │
│  - Audio files with timestamps                      │
│  - Sequence/timing of annotations                   │
│  - Raw transcriptions                               │
│  - User interaction metadata                        │
│  - Multiple sessions/revisions per image            │
│  - Original pixel coordinates + image dimensions    │
└─────────────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────┐
│              EXPORT/CONVERSION LAYER                │
│         (Transform to specific formats)             │
├─────────────────────────────────────────────────────┤
│  → DeepSeek-OCR format (VLM fine-tuning)            │
│  → Embedding-friendly format (CLIP, retrieval)      │
│  → Prompt templates (inference with VLMs)           │
│  → ShareGPT conversations (conversational tuning)   │
│  → Future formats as needed                         │
└─────────────────────────────────────────────────────┘
```

### Why Two Layers?

1. **Preserve rich information** - Raw polygons, timing, audio are valuable and shouldn't be flattened prematurely
2. **Multiple downstream uses**:
   - Fine-tuning/distillation of multimodal LLMs
   - Prompt-based inference with existing VLMs (no training, just context)
   - Embedding space operations (similarity search, clustering, retrieval)
   - Future use cases not yet anticipated
3. **Reproducibility** - Can regenerate any export format from raw data
4. **Flexibility** - Format requirements may change as models evolve

---

## Raw Data Model

### Per PAD Image (Raw Storage):
| Field | Description |
|-------|-------------|
| `image_id` | Unique identifier |
| `image_file` | Path to PAD card image file |
| `image_dimensions` | Original width x height in pixels |
| `drug_distractor_type` | Classification label for the whole image |
| `pad_configuration` | Which PAD type/version (for extensibility) |
| `annotations` | Collection of region annotations |
| `metadata` | Additional metadata (capture date, source, etc.) |

### Per Annotation (Raw Storage):
| Field | Description |
|-------|-------------|
| `annotation_id` | Unique identifier |
| `region_polygon` | Full polygon coordinates as array of [x, y] points (original pixels) |
| `region_bbox` | Bounding box [x, y, width, height] (derived from polygon) |
| `lane_reference` | Which reagent lane(s) if applicable (e.g., "D", "F", "G-H") |
| `annotation_type` | Type: "observation", "artifact", "issue", etc. |
| `audio_file` | Path to audio recording file |
| `audio_duration_ms` | Duration of audio in milliseconds |
| `transcription_raw` | Raw text transcription of audio |
| `timestamp_created` | When annotation was created |
| `timestamp_audio_start` | When audio recording started (relative to session) |
| `sequence_order` | Order in which regions were annotated (1st, 2nd, etc.) |

### Per Annotation Session:
| Field | Description |
|-------|-------------|
| `session_id` | Unique identifier |
| `image_id` | Which image was annotated |
| `specialist_id` | Who performed the annotation |
| `session_start` | When session began |
| `session_end` | When session ended |
| `annotations` | List of annotations created in this session |
| `session_audio` | Optional: full session audio recording |

### Per Specialist (User Profile):
| Field | Description |
|-------|-------------|
| `specialist_id` | Unique identifier |
| `expertise_level` | Level of expertise (see below) |
| `years_experience` | Years of experience with PAD analysis (optional) |
| `training_date` | When the specialist completed PAD training |
| `certifications` | Any relevant certifications |
| `specializations` | Specific drug types or PAD configurations they specialize in |
| `institution` | Organization/institution affiliation (optional) |
| `annotations_count` | Running count of annotations made (computed) |
| `metadata` | Additional profile metadata |

#### Expertise Levels (example scale - to be refined):
| Level | Description |
|-------|-------------|
| `novice` | Recently trained, limited field experience |
| `intermediate` | Some field experience, still developing skills |
| `experienced` | Significant field experience, reliable analysis |
| `expert` | Long-term specialist, can train others |
| `trainer` | Certified to train new specialists |

> **Note:** The expertise level schema should be flexible to accommodate different classification needs. The actual levels and criteria will be defined based on project requirements.

---

## Key Requirements

### 1. Selective Lane Relevance
- Not all 12 lanes are relevant for every drug/distractor type
- The system must NOT force specialists to annotate all lanes
- Only lanes relevant to the specific substance being analyzed should be annotated

### 2. Freeform Region Selection
- Annotations must support flexible, freeform region highlighting
- Regions may not align perfectly to lane boundaries
- Specialists need to mark irregular areas based on what they observe

### 3. Real-World Imperfections
The system must accommodate annotations of imperfect/problematic PAD images. Specialists may need to annotate:

- **Reaction issues**: Uneven wicking, incomplete color development
- **Sample application problems**: Smudging, uneven distribution across lanes
- **Cross-lane contamination**: Color bleeding between adjacent lanes
- **Physical artifacts**: Damage, stains, improper handling
- **Process anomalies**: Any issue that affects interpretation of results

### 4. Audio Capture
- Record specialist explanations synchronized with region selection
- Audio captures expert reasoning about:
  - Why specific regions/lanes are significant
  - What color patterns indicate
  - What artifacts or issues are present
  - How to interpret imperfect samples

### 5. Generic Interface
- The interface should be flexible enough to handle different PAD configurations
- Initial implementation will target a specific configuration (TBD)
- System should be extensible to support antibiotics, TB drugs, illicit substances, etc.

---

## Dataset Purpose

The collected dataset will be used for:

1. **Training AI/Computer Vision models** to:
   - Automatically identify relevant regions on PAD cards
   - Classify drug/distractor types from visual patterns
   - Detect quality issues and artifacts

2. **Fine-tuning / Distillation of Multimodal LLMs**:
   - Fine-tune multimodal LLMs on expert annotations and explanations
   - Distill specialized PAD analysis knowledge into smaller, deployable models
   - Create domain-specific models that combine visual understanding with expert reasoning
   - Enable transfer of specialist knowledge to AI systems at scale

3. **Prompt-based Inference with Existing VLMs**:
   - Use raw annotations as context for multimodal LLMs (no training required)
   - Provide expert examples for few-shot learning
   - Build retrieval-augmented systems that fetch relevant annotations as context

4. **Embedding Space Operations**:
   - Generate embeddings for similarity search (find similar PAD patterns)
   - Cluster annotations by visual/semantic similarity
   - Build retrieval systems for expert knowledge lookup
   - Enable semantic search across annotation transcriptions

---

## Export Layer: Format & Schema Considerations

The export layer converts raw data to specific formats for integration with open-weight models available in the Hugging Face ecosystem and Ollama for local deployment.

### Design Principles:

1. **Hugging Face Datasets Compatibility**
   - Store data in formats easily loadable by `datasets` library (JSON, JSONL, Parquet)
   - Follow conventions used by popular multimodal datasets (LLaVA, ShareGPT-4V, etc.)
   - Support direct upload to Hugging Face Hub

2. **Inline Grounding Format (DeepSeek-OCR Style)**

   Based on how DeepSeek-OCR was fine-tuned, use an **interleaved text + coordinates format** with special tokens:

   - `<|ref|>description<|/ref|>` - References text explanation to a region
   - `<|det|>[x1, y1, x2, y2]<|/det|>` - Bounding box coordinates (normalized 0-999)
   - `<|grounding|>` - Enables spatial awareness mode

   **Example for PAD annotation:**
   ```
   <image>
   <|grounding|>Analyze this PAD card for Amoxicillin.

   <|ref|>Lane D shows strong purple coloration indicating presence of active ingredient<|/ref|><|det|>[120, 200, 180, 400]<|/det|>

   <|ref|>Lane F has faint reaction suggesting low concentration<|/ref|><|det|>[220, 200, 280, 400]<|/det|>

   <|ref|>Bleeding artifact between lanes G and H - ignore this region<|/ref|><|det|>[300, 250, 380, 350]<|/det|>
   ```

   **Why this format:**
   - Text-native - works directly with LLM fine-tuning
   - Explanations and coordinates are naturally paired
   - Same format for training and inference
   - Compatible with grounding-enabled models (DeepSeek, Qwen-VL, LLaVA, etc.)

3. **Coordinate Normalization**
   - Normalize all coordinates to **0-999 range** (1000 bins), resolution-independent
   - Format: `[x1, y1, x2, y2]` where (x1,y1) is top-left, (x2,y2) is bottom-right
   - Allows same coordinates to work across different image sizes

4. **Audio Processing**
   - Store original audio files (WAV/MP3) for future use
   - Include text transcriptions for immediate LLM training
   - Transcriptions become the `<|ref|>...<|/ref|>` content linked to regions

5. **Multimodal Training Ready**
   - Structure data for vision-language models (LLaVA, Qwen-VL, DeepSeek-VL, etc.)
   - Support image + grounded explanation format
   - Enable both full fine-tuning and LoRA/QLoRA approaches

### Suggested Export Formats:

| Use Case | Format | Notes |
|----------|--------|-------|
| Hugging Face upload | Parquet + images folder | Native `datasets` support |
| VLM fine-tuning | JSONL with inline grounding tokens | DeepSeek-OCR style, direct training |
| Ollama/local LLMs | JSONL conversations | For text-based fine-tuning with transcriptions |
| Conversational | ShareGPT format with grounding | Multi-turn conversations about PAD analysis |
| Embeddings/Retrieval | JSONL with text + region pairs | For CLIP-like models, semantic search |
| Prompt templates | Markdown/JSON templates | Few-shot examples for inference |

### Export Pipeline Must Support:
- Batch export in multiple formats from raw data
- Conversion scripts for common frameworks (transformers, axolotl, llama-factory, unsloth)
- Metadata preservation across format conversions
- Coordinate normalization (raw pixels → 0-999 normalized)
- Polygon → bounding box conversion where needed
- Audio transcription integration
- Selective export (filter by drug type, annotation type, etc.)

### References:
- [DeepSeek-OCR GitHub](https://github.com/deepseek-ai/DeepSeek-OCR)
- [DeepSeek-OCR Hugging Face](https://huggingface.co/deepseek-ai/DeepSeek-OCR)
- [Unsloth Fine-tuning Guide](https://docs.unsloth.ai/models/deepseek-ocr-how-to-run-and-fine-tune)

---

## Study System

The data collection uses a structured study system where:
- Administrators define studies with pre-selected image sets
- Specialists are assigned to studies
- Each specialist sees the same images in the same order
- Progress is tracked per user per study
- Data stored in SQLite database for integrity

See [study-system.md](./study-system.md) for full design details including:
- Database schema (specialists, studies, images, annotations)
- API endpoints
- Workflow for admins and specialists
- Progress tracking
- Export formats

---

## Future Considerations

- **Internet connectivity requirements** - To be addressed later
- **Specific PAD configuration** - To be provided
- **Expertise level classification criteria** - Define what qualifies as novice vs expert, etc.
- **Expertise progression tracking** - Allow expertise level to change over time as specialists gain experience

---

## Open Questions

### Resolved
- [x] Technical platform - Web app (HTML/JS + Python FastAPI backend)
- [x] Annotation tool type - Both rectangle and polygon (freehand closed)
- [x] Audio/annotation synchronization - Timestamps (start_ms, end_ms) per annotation
- [x] Raw data storage format - SQLite database (designed, pending implementation)
- [x] Audio transcription method - OpenAI API (gpt-4o-transcribe) - to be integrated

### Pending
- [ ] Specific PAD configuration to start with
- [ ] Review/validation workflow for annotations
- [ ] Expected volume of images/annotations per study
- [ ] Specialist authentication method (simple name selection vs login system)
- [ ] Admin interface for study management
- [ ] Backup and data recovery procedures
