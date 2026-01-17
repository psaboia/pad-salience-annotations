"""
Database module for PAD Salience Annotation System.
Uses SQLite with aiosqlite for async operations.
"""

import json
import aiosqlite
from pathlib import Path
from typing import Optional, Any
from contextlib import asynccontextmanager

# Database path
BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "pad_annotations.db"
MIGRATIONS_DIR = BASE_DIR / "migrations"


async def get_db() -> aiosqlite.Connection:
    """Get a database connection."""
    db = await aiosqlite.connect(DB_PATH)
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA foreign_keys = ON")
    return db


@asynccontextmanager
async def get_db_context():
    """Context manager for database connections."""
    db = await get_db()
    try:
        yield db
    finally:
        await db.close()


async def init_db():
    """Initialize database with migrations."""
    DATA_DIR.mkdir(exist_ok=True)

    async with get_db_context() as db:
        # Check which migrations have been applied
        try:
            cursor = await db.execute(
                "SELECT version FROM migrations ORDER BY version"
            )
            applied = {row[0] async for row in cursor}
        except aiosqlite.OperationalError:
            # migrations table doesn't exist yet
            applied = set()

        # Get all migration files
        migration_files = sorted(MIGRATIONS_DIR.glob("*.sql"))

        for migration_file in migration_files:
            version = migration_file.stem
            if version not in applied:
                print(f"Applying migration: {version}")
                sql = migration_file.read_text()
                await db.executescript(sql)
                await db.commit()
                print(f"Migration {version} applied successfully")


async def row_to_dict(row: aiosqlite.Row) -> dict:
    """Convert a Row to a dictionary."""
    if row is None:
        return None
    return dict(row)


async def rows_to_dicts(rows: list[aiosqlite.Row]) -> list[dict]:
    """Convert multiple Rows to dictionaries."""
    return [dict(row) for row in rows]


# Helper functions for JSON fields
def json_dumps(data: Any) -> str:
    """Serialize data to JSON string."""
    return json.dumps(data) if data is not None else None


def json_loads(data: str) -> Any:
    """Deserialize JSON string to data."""
    return json.loads(data) if data else None


# User operations
async def create_user(
    db: aiosqlite.Connection,
    email: str,
    name: str,
    password_hash: str,
    role: str,
    expertise_level: Optional[str] = None,
    years_experience: Optional[int] = None,
    training_date: Optional[str] = None,
    institution: Optional[str] = None,
    specializations: Optional[list] = None
) -> int:
    """Create a new user and return their ID."""
    cursor = await db.execute(
        """
        INSERT INTO users (email, name, password_hash, role, expertise_level,
                          years_experience, training_date, institution, specializations)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (email, name, password_hash, role, expertise_level,
         years_experience, training_date, institution, json_dumps(specializations))
    )
    await db.commit()
    return cursor.lastrowid


async def get_user_by_email(db: aiosqlite.Connection, email: str) -> Optional[dict]:
    """Get a user by email."""
    cursor = await db.execute(
        "SELECT * FROM users WHERE email = ? AND is_active = 1",
        (email,)
    )
    row = await cursor.fetchone()
    return await row_to_dict(row) if row else None


async def get_user_by_id(db: aiosqlite.Connection, user_id: int) -> Optional[dict]:
    """Get a user by ID."""
    cursor = await db.execute(
        "SELECT * FROM users WHERE id = ? AND is_active = 1",
        (user_id,)
    )
    row = await cursor.fetchone()
    return await row_to_dict(row) if row else None


async def get_specialists(db: aiosqlite.Connection) -> list[dict]:
    """Get all active specialists."""
    cursor = await db.execute(
        "SELECT * FROM users WHERE role = 'specialist' AND is_active = 1 ORDER BY name"
    )
    rows = await cursor.fetchall()
    users = await rows_to_dicts(rows)
    # Parse specializations JSON for each user
    for user in users:
        if user.get('specializations'):
            user['specializations'] = json_loads(user['specializations'])
    return users


async def get_all_users(db: aiosqlite.Connection, include_inactive: bool = False) -> list[dict]:
    """Get all users, optionally including inactive ones."""
    if include_inactive:
        cursor = await db.execute("SELECT * FROM users ORDER BY name")
    else:
        cursor = await db.execute("SELECT * FROM users WHERE is_active = 1 ORDER BY name")
    rows = await cursor.fetchall()
    users = await rows_to_dicts(rows)
    # Parse specializations JSON for each user
    for user in users:
        if user.get('specializations'):
            user['specializations'] = json_loads(user['specializations'])
    return users


async def update_user(
    db: aiosqlite.Connection,
    user_id: int,
    email: Optional[str] = None,
    name: Optional[str] = None,
    password_hash: Optional[str] = None,
    role: Optional[str] = None,
    expertise_level: Optional[str] = None,
    years_experience: Optional[int] = None,
    training_date: Optional[str] = None,
    institution: Optional[str] = None,
    specializations: Optional[list] = None,
    is_active: Optional[bool] = None
) -> bool:
    """Update a user. Returns True if user was found and updated."""
    updates = []
    params = []

    if email is not None:
        updates.append("email = ?")
        params.append(email)
    if name is not None:
        updates.append("name = ?")
        params.append(name)
    if password_hash is not None:
        updates.append("password_hash = ?")
        params.append(password_hash)
    if role is not None:
        updates.append("role = ?")
        params.append(role)
    if expertise_level is not None:
        updates.append("expertise_level = ?")
        params.append(expertise_level)
    if years_experience is not None:
        updates.append("years_experience = ?")
        params.append(years_experience)
    if training_date is not None:
        updates.append("training_date = ?")
        params.append(training_date)
    if institution is not None:
        updates.append("institution = ?")
        params.append(institution)
    if specializations is not None:
        updates.append("specializations = ?")
        params.append(json_dumps(specializations))
    if is_active is not None:
        updates.append("is_active = ?")
        params.append(1 if is_active else 0)

    if not updates:
        return False

    updates.append("updated_at = datetime('now')")
    params.append(user_id)

    query = f"UPDATE users SET {', '.join(updates)} WHERE id = ?"
    cursor = await db.execute(query, params)
    await db.commit()
    return cursor.rowcount > 0


async def deactivate_user(db: aiosqlite.Connection, user_id: int) -> bool:
    """Soft delete a user by setting is_active to 0."""
    cursor = await db.execute(
        "UPDATE users SET is_active = 0, updated_at = datetime('now') WHERE id = ?",
        (user_id,)
    )
    await db.commit()
    return cursor.rowcount > 0


async def get_user_by_id_include_inactive(db: aiosqlite.Connection, user_id: int) -> Optional[dict]:
    """Get a user by ID, including inactive users."""
    cursor = await db.execute(
        "SELECT * FROM users WHERE id = ?",
        (user_id,)
    )
    row = await cursor.fetchone()
    if row:
        user = await row_to_dict(row)
        if user.get('specializations'):
            user['specializations'] = json_loads(user['specializations'])
        return user
    return None


# Sample operations
async def import_samples_from_manifest(db: aiosqlite.Connection, manifest_path: Path):
    """Import samples from manifest.json file."""
    import json

    with open(manifest_path) as f:
        samples = json.load(f)

    for sample in samples:
        await db.execute(
            """
            INSERT OR IGNORE INTO samples
            (drug_name, drug_name_display, card_id, filename, image_path, quantity, image_type)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                sample["drug_name"],
                sample["drug_name_display"],
                sample["card_id"],
                sample["filename"],
                sample["path"],
                sample.get("quantity"),
                sample.get("image_type", "processed")
            )
        )
    await db.commit()


async def get_all_samples(db: aiosqlite.Connection) -> list[dict]:
    """Get all samples."""
    cursor = await db.execute("SELECT * FROM samples ORDER BY drug_name_display")
    rows = await cursor.fetchall()
    return await rows_to_dicts(rows)


async def get_sample_by_id(db: aiosqlite.Connection, sample_id: int) -> Optional[dict]:
    """Get a sample by ID."""
    cursor = await db.execute("SELECT * FROM samples WHERE id = ?", (sample_id,))
    row = await cursor.fetchone()
    return await row_to_dict(row) if row else None


# Experiment operations
async def create_experiment(
    db: aiosqlite.Connection,
    name: str,
    created_by: int,
    description: Optional[str] = None,
    instructions: Optional[str] = None
) -> int:
    """Create a new experiment."""
    cursor = await db.execute(
        """
        INSERT INTO experiments (name, description, instructions, created_by)
        VALUES (?, ?, ?, ?)
        """,
        (name, description, instructions, created_by)
    )
    await db.commit()
    return cursor.lastrowid


async def get_experiment_by_id(db: aiosqlite.Connection, experiment_id: int) -> Optional[dict]:
    """Get an experiment by ID."""
    cursor = await db.execute(
        "SELECT * FROM experiments WHERE id = ?",
        (experiment_id,)
    )
    row = await cursor.fetchone()
    return await row_to_dict(row) if row else None


async def get_all_experiments(db: aiosqlite.Connection) -> list[dict]:
    """Get all experiments."""
    cursor = await db.execute(
        "SELECT * FROM experiments ORDER BY created_at DESC"
    )
    rows = await cursor.fetchall()
    return await rows_to_dicts(rows)


async def update_experiment_status(
    db: aiosqlite.Connection,
    experiment_id: int,
    status: str
):
    """Update experiment status."""
    await db.execute(
        "UPDATE experiments SET status = ?, updated_at = datetime('now') WHERE id = ?",
        (status, experiment_id)
    )
    await db.commit()


async def add_samples_to_experiment(
    db: aiosqlite.Connection,
    experiment_id: int,
    sample_ids: list[int]
):
    """Add samples to an experiment with display order."""
    for order, sample_id in enumerate(sample_ids, 1):
        await db.execute(
            """
            INSERT OR REPLACE INTO experiment_samples (experiment_id, sample_id, display_order)
            VALUES (?, ?, ?)
            """,
            (experiment_id, sample_id, order)
        )
    await db.commit()


async def get_experiment_samples(db: aiosqlite.Connection, experiment_id: int) -> list[dict]:
    """Get samples for an experiment with their order."""
    cursor = await db.execute(
        """
        SELECT es.id as experiment_sample_id, es.display_order, s.*
        FROM experiment_samples es
        JOIN samples s ON es.sample_id = s.id
        WHERE es.experiment_id = ?
        ORDER BY es.display_order
        """,
        (experiment_id,)
    )
    rows = await cursor.fetchall()
    return await rows_to_dicts(rows)


# Assignment operations
async def create_assignment(
    db: aiosqlite.Connection,
    experiment_id: int,
    specialist_id: int,
    expertise_level_snapshot: Optional[str] = None,
    years_experience_snapshot: Optional[int] = None,
    training_date_snapshot: Optional[str] = None
) -> int:
    """Create an assignment for a specialist to an experiment with profile snapshot."""
    cursor = await db.execute(
        """
        INSERT INTO assignments (experiment_id, specialist_id,
                                expertise_level_snapshot, years_experience_snapshot, training_date_snapshot)
        VALUES (?, ?, ?, ?, ?)
        """,
        (experiment_id, specialist_id,
         expertise_level_snapshot, years_experience_snapshot, training_date_snapshot)
    )
    await db.commit()
    return cursor.lastrowid


async def get_assignment(
    db: aiosqlite.Connection,
    experiment_id: int,
    specialist_id: int
) -> Optional[dict]:
    """Get assignment for a specialist in an experiment."""
    cursor = await db.execute(
        """
        SELECT * FROM assignments
        WHERE experiment_id = ? AND specialist_id = ?
        """,
        (experiment_id, specialist_id)
    )
    row = await cursor.fetchone()
    return await row_to_dict(row) if row else None


async def get_specialist_assignments(
    db: aiosqlite.Connection,
    specialist_id: int
) -> list[dict]:
    """Get all assignments for a specialist with experiment details."""
    cursor = await db.execute(
        """
        SELECT a.*, e.name as experiment_name, e.description, e.instructions, e.status as experiment_status
        FROM assignments a
        JOIN experiments e ON a.experiment_id = e.id
        WHERE a.specialist_id = ? AND e.status IN ('active', 'paused')
        ORDER BY a.created_at DESC
        """,
        (specialist_id,)
    )
    rows = await cursor.fetchall()
    return await rows_to_dicts(rows)


async def get_experiment_assignments(
    db: aiosqlite.Connection,
    experiment_id: int
) -> list[dict]:
    """Get all assignments for an experiment with specialist details."""
    cursor = await db.execute(
        """
        SELECT a.*, u.name as specialist_name, u.email as specialist_email
        FROM assignments a
        JOIN users u ON a.specialist_id = u.id
        WHERE a.experiment_id = ?
        ORDER BY u.name
        """,
        (experiment_id,)
    )
    rows = await cursor.fetchall()
    return await rows_to_dicts(rows)


async def start_assignment(
    db: aiosqlite.Connection,
    assignment_id: int,
    randomization_seed: int
):
    """Start an assignment and set randomization seed."""
    await db.execute(
        """
        UPDATE assignments
        SET status = 'in_progress', randomization_seed = ?, started_at = datetime('now')
        WHERE id = ?
        """,
        (randomization_seed, assignment_id)
    )
    await db.commit()


async def generate_specialist_order(
    db: aiosqlite.Connection,
    assignment_id: int,
    randomization_seed: int
):
    """Generate randomized sample order for a specialist assignment."""
    import random

    # Get assignment details
    cursor = await db.execute(
        "SELECT experiment_id FROM assignments WHERE id = ?",
        (assignment_id,)
    )
    row = await cursor.fetchone()
    if not row:
        return

    experiment_id = row["experiment_id"]

    # Get experiment samples
    cursor = await db.execute(
        "SELECT id FROM experiment_samples WHERE experiment_id = ? ORDER BY display_order",
        (experiment_id,)
    )
    sample_rows = await cursor.fetchall()
    sample_ids = [row["id"] for row in sample_rows]

    # Randomize order using seed
    random.seed(randomization_seed)
    random.shuffle(sample_ids)

    # Insert randomized order
    for order, exp_sample_id in enumerate(sample_ids, 1):
        await db.execute(
            """
            INSERT INTO specialist_sample_order (assignment_id, experiment_sample_id, specialist_order)
            VALUES (?, ?, ?)
            """,
            (assignment_id, exp_sample_id, order)
        )
    await db.commit()


async def get_specialist_sample_order(
    db: aiosqlite.Connection,
    assignment_id: int
) -> list[dict]:
    """Get the randomized sample order for a specialist."""
    cursor = await db.execute(
        """
        SELECT sso.specialist_order, sso.experiment_sample_id, es.sample_id, s.*
        FROM specialist_sample_order sso
        JOIN experiment_samples es ON sso.experiment_sample_id = es.id
        JOIN samples s ON es.sample_id = s.id
        WHERE sso.assignment_id = ?
        ORDER BY sso.specialist_order
        """,
        (assignment_id,)
    )
    rows = await cursor.fetchall()
    return await rows_to_dicts(rows)


# Annotation session operations
async def create_annotation_session(
    db: aiosqlite.Connection,
    assignment_id: int,
    experiment_sample_id: int,
    session_uuid: str
) -> int:
    """Create a new annotation session."""
    cursor = await db.execute(
        """
        INSERT INTO annotation_sessions (assignment_id, experiment_sample_id, session_uuid)
        VALUES (?, ?, ?)
        """,
        (assignment_id, experiment_sample_id, session_uuid)
    )
    await db.commit()
    return cursor.lastrowid


async def get_session_by_uuid(db: aiosqlite.Connection, session_uuid: str) -> Optional[dict]:
    """Get an annotation session by UUID."""
    cursor = await db.execute(
        "SELECT * FROM annotation_sessions WHERE session_uuid = ?",
        (session_uuid,)
    )
    row = await cursor.fetchone()
    return await row_to_dict(row) if row else None


async def get_current_session_for_assignment(
    db: aiosqlite.Connection,
    assignment_id: int
) -> Optional[dict]:
    """Get the current (next incomplete) session for an assignment."""
    cursor = await db.execute(
        """
        SELECT
            ans.id as session_id,
            ans.session_uuid,
            ans.status as session_status,
            sso.specialist_order,
            sso.experiment_sample_id,
            s.id as sample_id,
            s.drug_name,
            s.drug_name_display,
            s.card_id,
            s.filename,
            s.image_path
        FROM specialist_sample_order sso
        JOIN experiment_samples es ON sso.experiment_sample_id = es.id
        JOIN samples s ON es.sample_id = s.id
        LEFT JOIN annotation_sessions ans ON ans.assignment_id = sso.assignment_id
            AND ans.experiment_sample_id = sso.experiment_sample_id
        WHERE sso.assignment_id = ?
            AND (ans.status IS NULL OR ans.status != 'completed')
        ORDER BY sso.specialist_order
        LIMIT 1
        """,
        (assignment_id,)
    )
    row = await cursor.fetchone()
    return await row_to_dict(row) if row else None


async def complete_session(
    db: aiosqlite.Connection,
    session_id: int,
    audio_filename: Optional[str],
    audio_duration_ms: Optional[int],
    image_dimensions: dict,
    layout_settings: dict
):
    """Mark a session as completed."""
    await db.execute(
        """
        UPDATE annotation_sessions
        SET status = 'completed',
            audio_filename = ?,
            audio_duration_ms = ?,
            image_dimensions_json = ?,
            layout_settings_json = ?,
            completed_at = datetime('now')
        WHERE id = ?
        """,
        (
            audio_filename,
            audio_duration_ms,
            json_dumps(image_dimensions),
            json_dumps(layout_settings),
            session_id
        )
    )
    await db.commit()


async def save_annotations(
    db: aiosqlite.Connection,
    session_id: int,
    annotations: list[dict]
):
    """Save annotations for a session."""
    for ann in annotations:
        await db.execute(
            """
            INSERT INTO annotations (
                session_id, annotation_type, color, lanes_json,
                bbox_normalized_json, points_normalized_json,
                timestamp_start_ms, timestamp_end_ms
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                session_id,
                ann["type"],
                ann.get("color"),
                json_dumps(ann.get("lanes", [])),
                json_dumps(ann.get("bbox_normalized")),
                json_dumps(ann.get("points_normalized")),
                ann.get("timestamp_start_ms"),
                ann.get("timestamp_end_ms")
            )
        )
    await db.commit()


async def get_assignment_progress(
    db: aiosqlite.Connection,
    assignment_id: int
) -> dict:
    """Get progress for an assignment."""
    # Total samples
    cursor = await db.execute(
        "SELECT COUNT(*) as total FROM specialist_sample_order WHERE assignment_id = ?",
        (assignment_id,)
    )
    row = await cursor.fetchone()
    total = row["total"]

    # Completed sessions
    cursor = await db.execute(
        """
        SELECT COUNT(*) as completed
        FROM annotation_sessions
        WHERE assignment_id = ? AND status = 'completed'
        """,
        (assignment_id,)
    )
    row = await cursor.fetchone()
    completed = row["completed"]

    return {
        "total": total,
        "completed": completed,
        "remaining": total - completed,
        "percentage": round((completed / total) * 100, 1) if total > 0 else 0
    }


async def get_experiment_progress(
    db: aiosqlite.Connection,
    experiment_id: int
) -> dict:
    """Get overall progress for an experiment."""
    # First get the total samples in the experiment (for specialists who haven't started)
    cursor = await db.execute(
        "SELECT COUNT(*) as count FROM experiment_samples WHERE experiment_id = ?",
        (experiment_id,)
    )
    row = await cursor.fetchone()
    experiment_sample_count = row["count"]

    cursor = await db.execute(
        """
        SELECT
            a.id as assignment_id,
            u.name as specialist_name,
            a.status,
            a.started_at,
            (SELECT COUNT(*) FROM specialist_sample_order WHERE assignment_id = a.id) as started_samples,
            (SELECT COUNT(*) FROM annotation_sessions WHERE assignment_id = a.id AND status = 'completed') as completed_samples
        FROM assignments a
        JOIN users u ON a.specialist_id = u.id
        WHERE a.experiment_id = ?
        ORDER BY u.name
        """,
        (experiment_id,)
    )
    rows = await cursor.fetchall()
    specialists = await rows_to_dicts(rows)

    # Add percentage to each - use experiment_sample_count for specialists who haven't started
    for spec in specialists:
        # If specialist hasn't started, use experiment's sample count as total
        started = spec["started_samples"]
        spec["total_samples"] = started if started > 0 else experiment_sample_count
        total = spec["total_samples"]
        completed = spec["completed_samples"]
        spec["percentage"] = round((completed / total) * 100, 1) if total > 0 else 0
        # Remove the intermediate field
        del spec["started_samples"]

    # Overall stats
    total_annotations = sum(s["total_samples"] for s in specialists)
    completed_annotations = sum(s["completed_samples"] for s in specialists)

    return {
        "specialists": specialists,
        "total_annotations": total_annotations,
        "completed_annotations": completed_annotations,
        "overall_percentage": round((completed_annotations / total_annotations) * 100, 1) if total_annotations > 0 else 0
    }


# Migration helper
async def migrate_legacy_annotations(db: aiosqlite.Connection, jsonl_path: Path):
    """Migrate existing annotations from JSONL file to database."""
    if not jsonl_path.exists():
        return 0

    count = 0
    with open(jsonl_path) as f:
        for line in f:
            if not line.strip():
                continue

            data = json.loads(line)
            audio = data.get("audio") or {}
            await db.execute(
                """
                INSERT INTO legacy_annotations (
                    original_session_id, original_timestamp, sample_json,
                    image_dimensions_json, annotations_json, audio_filename,
                    audio_duration_ms, specialist_id, specialist_expertise,
                    layout_settings_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    data.get("session_id"),
                    data.get("timestamp"),
                    json_dumps(data.get("sample")),
                    json_dumps(data.get("image_dimensions")),
                    json_dumps(data.get("annotations", [])),
                    audio.get("filename"),
                    audio.get("duration_ms"),
                    data.get("specialist_id"),
                    data.get("specialist_expertise"),
                    json_dumps(data.get("layout_settings"))
                )
            )
            count += 1

    await db.commit()
    return count


# Sample tag operations (for AprilTag identification)
async def get_sample_tags(db: aiosqlite.Connection, sample_id: int) -> list[dict]:
    """Get all tags for a sample."""
    cursor = await db.execute(
        """
        SELECT tag_id, position
        FROM sample_tags
        WHERE sample_id = ?
        ORDER BY position
        """,
        (sample_id,)
    )
    rows = await cursor.fetchall()
    return await rows_to_dicts(rows)


async def get_sample_tags_by_position(db: aiosqlite.Connection, sample_id: int) -> dict:
    """Get tags for a sample as a dictionary keyed by position."""
    tags = await get_sample_tags(db, sample_id)
    return {tag['position']: tag['tag_id'] for tag in tags}


async def identify_sample_by_tags(
    db: aiosqlite.Connection,
    detected_tags: list[int],
    min_match: int = 3
) -> Optional[int]:
    """
    Identify a sample based on detected AprilTag IDs.

    Uses a "best match" algorithm that finds the sample with the most
    matching tags. Requires at least min_match tags to match and the
    best match must have at least 1 more match than the second best.

    Args:
        db: Database connection
        detected_tags: List of detected AprilTag IDs
        min_match: Minimum number of tags that must match (default 3)

    Returns:
        Sample ID if identified, None if ambiguous or insufficient matches
    """
    if len(detected_tags) < min_match:
        return None

    detected_set = set(detected_tags)

    # Get all samples with their tags
    cursor = await db.execute(
        """
        SELECT sample_id, GROUP_CONCAT(tag_id) as tags
        FROM sample_tags
        GROUP BY sample_id
        """
    )
    rows = await cursor.fetchall()

    best_match = None
    best_score = 0
    second_best_score = 0

    for row in rows:
        sample_tags = set(int(t) for t in row['tags'].split(','))
        score = len(detected_set & sample_tags)

        if score > best_score:
            second_best_score = best_score
            best_score = score
            best_match = row['sample_id']
        elif score > second_best_score:
            second_best_score = score

    # Require minimum match and margin over second best
    if best_score >= min_match and (best_score - second_best_score) >= 1:
        return best_match

    return None
