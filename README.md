# PAD Salience Annotations

A system for capturing expert annotations on PAD (Paper Analytical Device) card images to build training datasets for AI models.

## What is PAD?

**PAD (Paper Analytical Device)** is a paper-based test card developed by the [Notre Dame PAD Project](https://padproject.nd.edu/) for screening pharmaceutical quality. Each card has 12 lanes (A-L) with different chemical reagents that produce color reactions to identify drugs and detect counterfeits.

<p align="center">
  <img src="sample_images/amoxicillin_15214_processed.png" alt="PAD Card Example - Amoxicillin" width="300">
  <br>
  <em>Example PAD card showing 12 lanes (A-L) with color reactions for Amoxicillin</em>
</p>

## Purpose

This project builds a structured annotation system where:
- **Specialists** mark salient regions on PAD card images
- **Audio explanations** capture expert reasoning
- **Data** is formatted for training multimodal AI models (fine-tuning, distillation, embeddings)

## Features

### Prototype (Current)
- Web-based annotation interface
- Rectangle and polygon drawing tools
- Automatic lane detection (A-L)
- Continuous audio recording with timestamps
- Export to JSONL format
- 26 drug samples from FHI2020 project

### Eye-Tracking (feature/eye-tracking branch)
- AprilTag markers for Pupil Labs surface tracking
- 4 tags (tag36h11 family) displayed around PAD image
- Enables gaze data to be mapped to image coordinates

### Planned
- SQLite database for data integrity
- Experiment management system
- Specialist progress tracking
- Audio transcription integration (OpenAI API)
- Export pipeline for HuggingFace/Ollama
- Live gaze overlay from eye-tracker

## Quick Start

```bash
# Clone the repository
git clone https://github.com/psaboia/pad-salience-annotations.git
cd pad-salience-annotations

# Install dependencies (requires uv)
uv sync

# Run the server
./run_prototype.sh

# Open in browser
# http://localhost:8765
```

## Documentation

| Document | Description |
|----------|-------------|
| [Requirements](docs/requirements.md) | Full system requirements and data architecture |
| [Experiment System](docs/experiment-system.md) | Database schema and experiment workflow design |
| [Prototype Specs](docs/prototype-specifications.md) | Current prototype implementation details |
| [Eye-Tracking Integration](docs/eye-tracking-integration.md) | Pupil Labs setup and AprilTag configuration |
| [Feedback Questionnaire](docs/feedback-questionnaire.md) | Questions for users and specialists |

## Project Structure

```
pad-salience-annotations/
├── prototype/
│   └── index.html          # Annotation interface
├── sample_images/
│   ├── manifest.json       # Image metadata
│   └── *.png               # PAD card images
├── assets/
│   └── apriltags/          # AprilTag markers for eye-tracking
├── data/
│   ├── annotations.jsonl   # Saved annotations
│   └── audio/              # Audio recordings
├── docs/
│   ├── requirements.md
│   ├── experiment-system.md
│   ├── prototype-specifications.md
│   ├── eye-tracking-integration.md
│   └── feedback-questionnaire.md
├── server.py               # FastAPI backend
├── run_prototype.sh        # Server launcher
└── pyproject.toml          # Python dependencies
```

## Data Format

Annotations are saved in JSONL format with normalized coordinates (0-999) compatible with DeepSeek-OCR style grounding:

```json
{
  "session_id": "session_123",
  "sample": {"drug_name": "amoxicillin", "card_id": 15214},
  "annotations": [
    {
      "type": "rectangle",
      "lanes": ["D", "E"],
      "timestamp_start_ms": 12500,
      "timestamp_end_ms": 15800,
      "bbox_normalized": {"x1": 225, "y1": 298, "x2": 335, "y2": 411}
    }
  ],
  "audio": {"filename": "session_123.webm", "duration_ms": 45000}
}
```

## Dependencies

- Python 3.12+
- [uv](https://github.com/astral-sh/uv) - Package manager
- [pad-analytics](https://github.com/PaperAnalyticalDeviceND/pad-analytics) - PAD database API

## Contributing

We welcome feedback! Please:
- Open an [issue](https://github.com/psaboia/pad-salience-annotations/issues) for bugs or suggestions
- Review the [feedback questionnaire](docs/feedback-questionnaire.md) and share your thoughts

## License

TBD

## Acknowledgments

- [Notre Dame PAD Project](https://padproject.nd.edu/) for PAD technology and data
- [pad-analytics](https://github.com/PaperAnalyticalDeviceND/pad-analytics) package for API access
