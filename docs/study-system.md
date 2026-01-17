# Study System Design

## Overview

A structured data collection system where:
- Administrators define **studies** with pre-selected image sets
- **Specialists** are assigned to studies
- Each specialist sees the **same images** in the same order
- Progress is tracked per user per study
- All data is stored in a SQLite database for integrity

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Administrator                            │
│  - Creates studies                                       │
│  - Defines image sets                                        │
│  - Assigns specialists to studies                        │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                     SQLite Database                          │
│  - studies, specialists, images, annotations             │
│  - Progress tracking                                         │
│  - Data integrity (transactions)                             │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                     Specialist Interface                     │
│  - Sees assigned study                                  │
│  - Images presented in order                                 │
│  - Cannot skip, must complete each                           │
│  - Progress saved automatically                              │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                     Export Pipeline                          │
│  - Export to JSONL for ML training                           │
│  - Export to HuggingFace format                              │
│  - Audio transcription integration                           │
└─────────────────────────────────────────────────────────────┘
```

---

## Database Schema

### Tables

#### 1. `specialists`
Stores specialist/user information.

| Column | Type | Description |
|--------|------|-------------|
| `id` | TEXT (UUID) | Primary key |
| `name` | TEXT | Display name |
| `email` | TEXT | Email (unique) |
| `expertise_level` | TEXT | novice, intermediate, experienced, expert, trainer |
| `years_experience` | INTEGER | Years of PAD analysis experience |
| `institution` | TEXT | Organization affiliation |
| `created_at` | TIMESTAMP | When account was created |
| `metadata` | JSON | Additional profile data |

#### 2. `studies`
Defines data collection studies/studies.

| Column | Type | Description |
|--------|------|-------------|
| `id` | TEXT (UUID) | Primary key |
| `name` | TEXT | Study name |
| `description` | TEXT | Purpose and instructions |
| `pad_configuration` | TEXT | PAD type (e.g., "FHI2020", "ChemoPAD") |
| `status` | TEXT | draft, active, completed, archived |
| `created_by` | TEXT | Admin who created it |
| `created_at` | TIMESTAMP | Creation date |
| `started_at` | TIMESTAMP | When study was activated |
| `completed_at` | TIMESTAMP | When study was finished |
| `config` | JSON | Additional settings |

#### 3. `study_images`
Images included in each study (ordered).

| Column | Type | Description |
|--------|------|-------------|
| `id` | TEXT (UUID) | Primary key |
| `study_id` | TEXT | FK to studies |
| `image_order` | INTEGER | Presentation order (1, 2, 3...) |
| `drug_name` | TEXT | Normalized drug name |
| `drug_name_display` | TEXT | Display name |
| `card_id` | INTEGER | PAD card ID from database |
| `image_filename` | TEXT | Local filename |
| `quantity` | INTEGER | Drug concentration % |
| `metadata` | JSON | Additional image data |

#### 4. `study_assignments`
Links specialists to studies.

| Column | Type | Description |
|--------|------|-------------|
| `id` | TEXT (UUID) | Primary key |
| `study_id` | TEXT | FK to studies |
| `specialist_id` | TEXT | FK to specialists |
| `assigned_at` | TIMESTAMP | When assigned |
| `started_at` | TIMESTAMP | When specialist started |
| `completed_at` | TIMESTAMP | When specialist finished all images |
| `current_image_order` | INTEGER | Last completed image order |

#### 5. `annotation_sessions`
One session per specialist per image.

| Column | Type | Description |
|--------|------|-------------|
| `id` | TEXT (UUID) | Primary key |
| `study_id` | TEXT | FK to studies |
| `specialist_id` | TEXT | FK to specialists |
| `image_id` | TEXT | FK to study_images |
| `started_at` | TIMESTAMP | When session began |
| `completed_at` | TIMESTAMP | When session was saved |
| `audio_filename` | TEXT | Audio file path |
| `audio_duration_ms` | INTEGER | Audio duration |
| `status` | TEXT | in_progress, completed, skipped |

#### 6. `annotations`
Individual region annotations within a session.

| Column | Type | Description |
|--------|------|-------------|
| `id` | TEXT (UUID) | Primary key |
| `session_id` | TEXT | FK to annotation_sessions |
| `sequence_order` | INTEGER | Order drawn (1st, 2nd, 3rd...) |
| `annotation_type` | TEXT | rectangle, polygon |
| `lanes` | JSON | Auto-detected lanes ["D", "E"] |
| `color` | TEXT | Annotation color |
| `timestamp_start_ms` | INTEGER | Audio timestamp start |
| `timestamp_end_ms` | INTEGER | Audio timestamp end |
| `bbox` | JSON | Bounding box {x, y, width, height} |
| `bbox_normalized` | JSON | Normalized coords {x1, y1, x2, y2} |
| `points` | JSON | Polygon points (if polygon) |
| `points_normalized` | JSON | Normalized polygon points |
| `transcription` | TEXT | Audio transcription (filled later) |
| `created_at` | TIMESTAMP | When annotation was created |

---

## Entity Relationships

```
specialists (1) ─────────────────────── (N) study_assignments
                                              │
studies (1) ─────────────────────── (N) ──┘
     │
     └── (1) ─────────────────────── (N) study_images
                                              │
annotation_sessions (N) ──────────────────────┘
     │
     └── (1) ─────────────────────── (N) annotations
```

---

## Workflow

### Admin Workflow

1. **Create Study**
   ```
   POST /api/studies
   {
     "name": "TB Drugs Study Q1 2026",
     "description": "Annotate TB drug samples for training",
     "pad_configuration": "FHI2020"
   }
   ```

2. **Add Images to Study**
   ```
   POST /api/studies/{id}/images
   {
     "images": [
       {"drug_name": "isoniazid", "card_id": 17776},
       {"drug_name": "rifampicin", "card_id": 23550},
       {"drug_name": "ethambutol", "card_id": 22639}
     ]
   }
   ```

3. **Assign Specialists**
   ```
   POST /api/studies/{id}/assignments
   {
     "specialist_ids": ["uuid-1", "uuid-2", "uuid-3"]
   }
   ```

4. **Activate Study**
   ```
   POST /api/studies/{id}/activate
   ```

### Specialist Workflow

1. **Login / Identify**
   - Select name from list or enter credentials
   - System loads their assigned study(s)

2. **Start Session**
   - System presents first uncompleted image
   - Cannot choose which image (sequential order)

3. **Annotate**
   - Draw regions, record audio
   - Progress auto-saved

4. **Complete Image**
   - Click "Save & Next"
   - Moves to next image in sequence
   - Cannot go back (prevents bias)

5. **Complete Study**
   - When all images done, show completion message
   - Can view summary of their annotations

---

## API Endpoints

### Studys
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/studies` | List all studies |
| POST | `/api/studies` | Create new study |
| GET | `/api/studies/{id}` | Get study details |
| PUT | `/api/studies/{id}` | Update study |
| POST | `/api/studies/{id}/activate` | Activate study |
| POST | `/api/studies/{id}/complete` | Mark as completed |

### Images
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/studies/{id}/images` | List images in study |
| POST | `/api/studies/{id}/images` | Add images to study |
| DELETE | `/api/studies/{id}/images/{img_id}` | Remove image |

### Assignments
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/studies/{id}/assignments` | List assigned specialists |
| POST | `/api/studies/{id}/assignments` | Assign specialists |
| DELETE | `/api/studies/{id}/assignments/{specialist_id}` | Remove assignment |

### Specialists
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/specialists` | List all specialists |
| POST | `/api/specialists` | Create specialist |
| GET | `/api/specialists/{id}` | Get specialist details |
| GET | `/api/specialists/{id}/progress` | Get annotation progress |

### Annotation Sessions
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/sessions/current` | Get current session for logged-in user |
| POST | `/api/sessions` | Start new session |
| PUT | `/api/sessions/{id}` | Update session (save annotations) |
| POST | `/api/sessions/{id}/complete` | Mark session complete, move to next |

### Export
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/export/jsonl` | Export all data as JSONL |
| GET | `/api/export/study/{id}` | Export specific study |
| GET | `/api/export/huggingface/{id}` | Export in HuggingFace format |

---

## Progress Tracking

### Per Specialist
```json
{
  "specialist_id": "uuid-123",
  "study_id": "uuid-456",
  "total_images": 26,
  "completed_images": 12,
  "current_image_order": 13,
  "percent_complete": 46.2,
  "estimated_remaining": "14 images"
}
```

### Per Study (Admin View)
```json
{
  "study_id": "uuid-456",
  "total_images": 26,
  "total_specialists": 5,
  "progress": [
    {"specialist": "Dr. Smith", "completed": 26, "percent": 100},
    {"specialist": "Dr. Jones", "completed": 18, "percent": 69.2},
    {"specialist": "Dr. Lee", "completed": 12, "percent": 46.2}
  ],
  "images_with_multiple_annotations": 12,
  "total_annotations": 342
}
```

---

## Data Export

### JSONL Format (for ML training)
Each line is one annotation session:
```json
{
  "session_id": "uuid",
  "study": {"id": "uuid", "name": "TB Drugs Study"},
  "specialist": {"id": "uuid", "expertise_level": "expert"},
  "image": {
    "drug_name": "isoniazid",
    "card_id": 17776,
    "filename": "isoniazid_17776_processed.png"
  },
  "annotations": [...],
  "audio": {"filename": "session_uuid.webm", "duration_ms": 45000}
}
```

### HuggingFace Dataset Format
```
dataset/
├── data/
│   ├── train.jsonl
│   ├── validation.jsonl
│   └── test.jsonl
├── images/
│   └── *.png
├── audio/
│   └── *.webm
└── dataset_info.json
```

---

## File Storage

```
data/
├── pad_annotations.db      # SQLite database
├── audio/                   # Audio recordings
│   └── {session_id}.webm
├── exports/                 # Generated exports
│   └── {study_id}/
│       ├── annotations.jsonl
│       └── metadata.json
└── backups/                 # Database backups
    └── pad_annotations_{date}.db
```

---

## Security Considerations

1. **Specialist Authentication**
   - For prototype: simple name selection
   - For production: proper login system

2. **Data Backup**
   - Automatic daily backups of SQLite file
   - Export to JSONL as additional backup

3. **Audit Trail**
   - All changes timestamped
   - Session history preserved

---

## Implementation Phases

### Phase 1: Prototype (Current)
- [x] Basic annotation interface
- [x] JSONL storage
- [ ] SQLite database

### Phase 2: Study System
- [ ] Database schema implementation
- [ ] Study CRUD API
- [ ] Specialist management
- [ ] Progress tracking

### Phase 3: Production
- [ ] User authentication
- [ ] Admin dashboard
- [ ] Export pipeline
- [ ] Audio transcription integration

---

## Database Choice Rationale

**Why SQLite over PostgreSQL:**
- No server setup required
- Single file - easy to backup and transfer
- Works offline
- Sufficient for expected scale (hundreds of studies, thousands of annotations)
- Can migrate to PostgreSQL later if needed

**Why database over JSONL files:**
- ACID transactions - no data loss on crash
- Relationships between entities
- Easy progress queries
- Concurrent access support
- Data integrity constraints
