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
- **Eye-tracking** captures gaze patterns during annotation
- **Data** is formatted for training multimodal AI models (fine-tuning, distillation, embeddings)

## Features

### Current
- **Study Management System** with SQLite database
  - Admin interface for creating and managing studies
  - Specialist dashboard with assignment tracking
  - Randomized sample order per specialist
  - Progress tracking and statistics
- **Authentication System** with JWT tokens and bcrypt password hashing
- Web-based annotation interface with two layout options
- Rectangle and polygon drawing tools
- Automatic lane detection (A-L)
- Continuous audio recording with timestamps
- **Eye-tracking support** with AprilTag markers for Pupil Labs surface tracking
- **Unique AprilTag identification** per sample for automatic image correlation with gaze data
- YAML configuration file for easy customization
- Export to JSONL format
- 26 drug samples from FHI2020 project

### Planned
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

# Create admin user
uv run python scripts/create_admin.py --email admin@example.com --password yourpassword

# Run the server
uv run uvicorn app.main:app --reload --port 8765

# Open in browser
# http://localhost:8765
```

## System Architecture

### Admin Workflow
1. Admin logs in at `/login`
2. Creates study from `/admin/studies`
3. Selects samples and assigns specialists
4. Monitors progress from dashboard

### Specialist Workflow
1. Specialist logs in at `/login`
2. Views assigned studies at `/specialist`
3. Starts study (samples randomized)
4. Annotates each sample sequentially (no skipping/going back)
5. Progress automatically tracked

## Configuration

Settings are stored in `config.yaml`:

```yaml
# AprilTag settings
apriltags:
  size_px: 60          # Tag size in pixels (recommended: 60-80)
  margin_px: 10        # Margin between tags and PAD image
  family: "tag36h11"
  ids: [0, 3, 7, 4]    # Default tags (overridden per sample)

# Layout settings
layout:
  sidebar_width_px: 240
  background_color: "#1a1a2e"
  sidebar_color: "#16213e"

# PAD image settings
pad_image:
  max_height_vh: 85    # Max height as % of viewport
  border_px: 3
  border_color: "#333333"

# Lane detection
lanes:
  start_percent: 0.082
  end_percent: 0.986
  labels: ["A", "B", "C", "D", "E", "F", "G", "H", "I", "J", "K", "L"]
```

## Eye-Tracking Setup

For Pupil Labs integration, see [Eye-Tracking Integration](docs/eye-tracking-integration.md).

**AprilTag Identification System:**
- Each sample has 4 unique AprilTags (tag36h11 family, 587 tags available)
- Minimum distance of 2 between any pair of samples
- Enables automatic correlation of gaze data with the correct image
- Supports 1000+ unique samples
- See [AprilTag Identification System](docs/apriltag-identification-system.md) for details

**AprilTag size recommendations:**
- Minimum detectable: ~32 pixels (white border to white border)
- Recommended: 60-80 pixels for reliable detection at 50-70cm distance
- Tags at corners should be larger if detection issues occur at angles

## Documentation

| Document | Description |
|----------|-------------|
| [Requirements](docs/requirements.md) | Full system requirements and data architecture |
| [Study System](docs/study-system.md) | Database schema and study workflow design |
| [Prototype Specs](docs/prototype-specifications.md) | Current prototype implementation details |
| [Eye-Tracking Integration](docs/eye-tracking-integration.md) | Pupil Labs setup and AprilTag configuration |
| [AprilTag Identification](docs/apriltag-identification-system.md) | Unique tag allocation for automatic sample identification |
| [Feedback Questionnaire](docs/feedback-questionnaire.md) | Questions for users and specialists |

## Project Structure

```
pad-salience-annotations/
├── app/                           # FastAPI backend
│   ├── main.py                    # Application entry point
│   ├── database.py                # SQLite helpers
│   ├── models/                    # Pydantic models
│   ├── routers/                   # API endpoints
│   │   ├── auth.py               # Authentication
│   │   ├── admin.py              # Admin endpoints
│   │   └── specialist.py         # Specialist endpoints
│   └── services/                  # Business logic
├── frontend/                      # HTML templates
│   ├── static/                    # CSS and JS
│   └── templates/                 # Jinja2 templates
│       ├── login.html
│       ├── admin/                 # Admin pages
│       └── specialist/            # Specialist pages
├── migrations/                    # SQL migrations
├── scripts/                       # Utility scripts
│   ├── create_admin.py           # Create users
│   ├── allocate_tags.py          # Allocate unique AprilTags
│   └── generate_apriltags.py     # Generate tag images
├── sample_images/
│   ├── manifest.json             # Image metadata
│   └── *.png                     # PAD card images
├── assets/
│   └── apriltags/                # AprilTag markers (587 tags)
├── data/
│   ├── pad_annotations.db        # SQLite database
│   └── audio/                    # Audio recordings
├── docs/                         # Documentation
├── config.yaml                   # Configuration file
└── pyproject.toml                # Python dependencies
```

## API Endpoints

### Authentication
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/auth/login` | POST | Login with email/password |
| `/api/auth/logout` | POST | Logout |
| `/api/auth/me` | GET | Get current user |

### Admin
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/admin/studies` | GET/POST | List/Create studies |
| `/api/admin/studies/{id}` | GET/PUT/DELETE | CRUD operations |
| `/api/admin/studies/{id}/samples` | GET/POST | Manage samples |
| `/api/admin/studies/{id}/assignments` | GET/POST/DELETE | Manage assignments |
| `/api/admin/users` | GET/POST | Manage users |

### Specialist
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/specialist/studies` | GET | List assigned studies |
| `/api/specialist/studies/{id}/start` | POST | Start study |
| `/api/specialist/studies/{id}/current` | GET | Get current sample |
| `/api/specialist/sessions/{uuid}/complete` | POST | Complete annotation |

## Data Format

Annotations are saved in SQLite database with normalized coordinates (0-999) compatible with DeepSeek-OCR style grounding:

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
- [FastAPI](https://fastapi.tiangolo.com/) - Web framework
- [aiosqlite](https://aiosqlite.omnilib.dev/) - Async SQLite
- [python-jose](https://python-jose.readthedocs.io/) - JWT tokens
- [passlib](https://passlib.readthedocs.io/) - Password hashing
- [pad-analytics](https://github.com/PaperAnalyticalDeviceND/pad-analytics) - PAD database API
- [Pillow](https://pillow.readthedocs.io/) - Image processing
- [PyYAML](https://pyyaml.org/) - Configuration file parsing

## Contributing

We welcome feedback! Please:
- Open an [issue](https://github.com/psaboia/pad-salience-annotations/issues) for bugs or suggestions
- Review the [feedback questionnaire](docs/feedback-questionnaire.md) and share your thoughts

## License

TBD

## Acknowledgments

- [Notre Dame PAD Project](https://padproject.nd.edu/) for PAD technology and data
- [pad-analytics](https://github.com/PaperAnalyticalDeviceND/pad-analytics) package for API access
- [Pupil Labs](https://pupil-labs.com/) for eye-tracking technology
