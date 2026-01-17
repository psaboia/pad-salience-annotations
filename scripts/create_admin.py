#!/usr/bin/env python3
"""
Script to create the initial admin user.
Usage: python scripts/create_admin.py [email] [name] [password]
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.database import init_db, get_db_context, create_user, get_user_by_email
from app.services.auth import hash_password


async def create_admin(email: str, name: str, password: str):
    """Create an admin user."""
    await init_db()

    async with get_db_context() as db:
        # Check if user already exists
        existing = await get_user_by_email(db, email)
        if existing:
            print(f"User with email {email} already exists!")
            return False

        # Create user
        password_hash = hash_password(password)
        user_id = await create_user(
            db,
            email=email,
            name=name,
            password_hash=password_hash,
            role="admin"
        )

        print(f"Admin user created successfully!")
        print(f"  ID: {user_id}")
        print(f"  Email: {email}")
        print(f"  Name: {name}")
        print(f"  Role: admin")
        return True


async def create_specialist(email: str, name: str, password: str, expertise: str = None):
    """Create a specialist user."""
    await init_db()

    async with get_db_context() as db:
        existing = await get_user_by_email(db, email)
        if existing:
            print(f"User with email {email} already exists!")
            return False

        password_hash = hash_password(password)
        user_id = await create_user(
            db,
            email=email,
            name=name,
            password_hash=password_hash,
            role="specialist",
            expertise_level=expertise
        )

        print(f"Specialist user created successfully!")
        print(f"  ID: {user_id}")
        print(f"  Email: {email}")
        print(f"  Name: {name}")
        print(f"  Role: specialist")
        return True


def main():
    if len(sys.argv) < 4:
        print("Usage: python scripts/create_admin.py <email> <name> <password>")
        print("       python scripts/create_admin.py --specialist <email> <name> <password>")
        print()
        print("Examples:")
        print("  python scripts/create_admin.py admin@example.com 'Admin User' secretpass")
        print("  python scripts/create_admin.py --specialist spec@example.com 'Dr. Smith' password123")
        sys.exit(1)

    if sys.argv[1] == "--specialist":
        if len(sys.argv) < 5:
            print("Usage: python scripts/create_admin.py --specialist <email> <name> <password>")
            sys.exit(1)
        email = sys.argv[2]
        name = sys.argv[3]
        password = sys.argv[4]
        asyncio.run(create_specialist(email, name, password))
    else:
        email = sys.argv[1]
        name = sys.argv[2]
        password = sys.argv[3]
        asyncio.run(create_admin(email, name, password))


if __name__ == "__main__":
    main()
