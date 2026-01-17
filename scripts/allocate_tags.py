#!/usr/bin/env python3
"""
AprilTag Allocation Script

Allocates unique AprilTag combinations to samples, ensuring a minimum
Hamming distance of 2 between any pair of samples. This enables robust
image identification via eye-tracking systems.

See docs/apriltag-identification-system.md for design decisions.

Usage:
    python scripts/allocate_tags.py                    # Allocate tags to all samples without tags
    python scripts/allocate_tags.py --sample-id 5      # Allocate tags to specific sample
    python scripts/allocate_tags.py --reallocate-all   # Reallocate all tags (WARNING: destructive)
    python scripts/allocate_tags.py --dry-run          # Show what would be allocated without saving
"""

import asyncio
import sys
from pathlib import Path
from itertools import combinations
from typing import Set, List, Optional, Tuple

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.database import init_db, get_db_context

# AprilTag configuration
APRILTAG_FAMILY = "tag36h11"
TOTAL_TAGS = 587  # IDs 0-586
TAGS_PER_SAMPLE = 4
MIN_DISTANCE = 2  # Minimum number of different tags between any two samples
POSITIONS = ['top-left', 'top-right', 'bottom-left', 'bottom-right']


def calculate_distance(set1: Set[int], set2: Set[int]) -> int:
    """Calculate the number of different tags between two sets."""
    return len(set1.symmetric_difference(set2)) // 2


def is_valid_allocation(candidate: Set[int], existing: List[Set[int]], min_distance: int = MIN_DISTANCE) -> bool:
    """Check if a candidate allocation has minimum distance from all existing allocations."""
    for existing_set in existing:
        shared = len(candidate & existing_set)
        # Distance = tags that differ = 4 - shared (for 4-tag sets)
        # We want at least min_distance different, so shared <= 4 - min_distance
        if shared > TAGS_PER_SAMPLE - min_distance:
            return False
    return True


def allocate_tags_greedy(existing_allocations: List[Set[int]], count: int = 1) -> List[Set[int]]:
    """
    Allocate tag sets using a greedy algorithm.

    This is faster than exhaustive search but may not find the optimal solution.
    For most practical cases with < 1000 samples, this works well.
    """
    all_tags = list(range(TOTAL_TAGS))
    new_allocations = []
    all_existing = existing_allocations.copy()

    for _ in range(count):
        # Try to find a valid combination
        # Start with tags not heavily used
        tag_usage = {}
        for alloc in all_existing:
            for tag in alloc:
                tag_usage[tag] = tag_usage.get(tag, 0) + 1

        # Sort tags by usage (prefer less used)
        sorted_tags = sorted(all_tags, key=lambda t: tag_usage.get(t, 0))

        found = False
        # Try combinations starting with least used tags
        for combo in combinations(sorted_tags[:100], TAGS_PER_SAMPLE):  # Limit search space
            candidate = set(combo)
            if is_valid_allocation(candidate, all_existing):
                new_allocations.append(candidate)
                all_existing.append(candidate)
                found = True
                break

        if not found:
            # Fallback: try all combinations (slower but guaranteed)
            for combo in combinations(all_tags, TAGS_PER_SAMPLE):
                candidate = set(combo)
                if is_valid_allocation(candidate, all_existing):
                    new_allocations.append(candidate)
                    all_existing.append(candidate)
                    found = True
                    break

        if not found:
            raise ValueError(
                f"Cannot allocate more tags. Maximum capacity reached with {len(all_existing)} samples. "
                f"Consider using a larger tag family or reducing MIN_DISTANCE."
            )

    return new_allocations


async def get_existing_allocations(db) -> dict:
    """Get all existing tag allocations from the database."""
    cursor = await db.execute("""
        SELECT sample_id, GROUP_CONCAT(tag_id) as tags
        FROM sample_tags
        GROUP BY sample_id
    """)
    rows = await cursor.fetchall()

    allocations = {}
    for row in rows:
        tags = set(int(t) for t in row['tags'].split(','))
        allocations[row['sample_id']] = tags

    return allocations


async def get_samples_without_tags(db) -> List[dict]:
    """Get all samples that don't have tags allocated."""
    cursor = await db.execute("""
        SELECT s.id, s.drug_name_display, s.card_id
        FROM samples s
        LEFT JOIN sample_tags st ON s.id = st.sample_id
        WHERE st.id IS NULL
        ORDER BY s.id
    """)
    return await cursor.fetchall()


async def save_allocation(db, sample_id: int, tags: Set[int]) -> None:
    """Save a tag allocation to the database."""
    tag_list = sorted(tags)
    for i, position in enumerate(POSITIONS):
        await db.execute("""
            INSERT INTO sample_tags (sample_id, tag_id, position)
            VALUES (?, ?, ?)
        """, (sample_id, tag_list[i], position))
    await db.commit()


async def delete_allocation(db, sample_id: int) -> None:
    """Delete existing tag allocation for a sample."""
    await db.execute("DELETE FROM sample_tags WHERE sample_id = ?", (sample_id,))
    await db.commit()


async def allocate_all_samples(dry_run: bool = False, reallocate: bool = False) -> None:
    """Allocate tags to all samples that need them."""
    await init_db()

    async with get_db_context() as db:
        # Apply migration if needed
        await db.executescript(open(Path(__file__).parent.parent / "migrations" / "002_sample_tags.sql").read())
        await db.commit()

        if reallocate:
            print("Deleting all existing allocations...")
            await db.execute("DELETE FROM sample_tags")
            await db.commit()

        existing = await get_existing_allocations(db)
        samples_needing_tags = await get_samples_without_tags(db)

        if not samples_needing_tags:
            print("All samples already have tags allocated.")
            return

        print(f"Found {len(samples_needing_tags)} samples needing tag allocation.")
        print(f"Existing allocations: {len(existing)}")
        print(f"Using MIN_DISTANCE={MIN_DISTANCE} (samples differ by at least {MIN_DISTANCE} tags)")
        print()

        existing_sets = list(existing.values())

        for sample in samples_needing_tags:
            try:
                new_tags = allocate_tags_greedy(existing_sets, count=1)[0]
                existing_sets.append(new_tags)

                tag_str = ", ".join(str(t) for t in sorted(new_tags))
                print(f"Sample {sample['id']:3d} ({sample['drug_name_display']}, Card #{sample['card_id']}): tags [{tag_str}]")

                if not dry_run:
                    await save_allocation(db, sample['id'], new_tags)

            except ValueError as e:
                print(f"ERROR: {e}")
                break

        if dry_run:
            print("\n[DRY RUN] No changes were saved to the database.")
        else:
            print(f"\nSuccessfully allocated tags to {len(samples_needing_tags)} samples.")


async def allocate_single_sample(sample_id: int, dry_run: bool = False) -> None:
    """Allocate tags to a specific sample."""
    await init_db()

    async with get_db_context() as db:
        # Apply migration if needed
        await db.executescript(open(Path(__file__).parent.parent / "migrations" / "002_sample_tags.sql").read())
        await db.commit()

        # Check if sample exists
        cursor = await db.execute("SELECT * FROM samples WHERE id = ?", (sample_id,))
        sample = await cursor.fetchone()
        if not sample:
            print(f"ERROR: Sample {sample_id} not found.")
            return

        # Check if already has tags
        cursor = await db.execute("SELECT * FROM sample_tags WHERE sample_id = ?", (sample_id,))
        existing_tags = await cursor.fetchall()
        if existing_tags:
            print(f"Sample {sample_id} already has tags: {[t['tag_id'] for t in existing_tags]}")
            print("Use --reallocate-all to reallocate, or delete manually.")
            return

        existing = await get_existing_allocations(db)
        existing_sets = list(existing.values())

        new_tags = allocate_tags_greedy(existing_sets, count=1)[0]
        tag_str = ", ".join(str(t) for t in sorted(new_tags))
        print(f"Sample {sample_id} ({sample['drug_name_display']}, Card #{sample['card_id']}): tags [{tag_str}]")

        if not dry_run:
            await save_allocation(db, sample_id, new_tags)
            print("Saved to database.")
        else:
            print("[DRY RUN] Not saved.")


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Allocate AprilTags to samples")
    parser.add_argument("--sample-id", type=int, help="Allocate tags to specific sample")
    parser.add_argument("--reallocate-all", action="store_true", help="Delete and reallocate all tags")
    parser.add_argument("--dry-run", action="store_true", help="Show allocations without saving")
    args = parser.parse_args()

    if args.sample_id:
        asyncio.run(allocate_single_sample(args.sample_id, dry_run=args.dry_run))
    else:
        asyncio.run(allocate_all_samples(dry_run=args.dry_run, reallocate=args.reallocate_all))


if __name__ == "__main__":
    main()
