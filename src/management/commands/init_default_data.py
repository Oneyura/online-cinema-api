#!/usr/bin/env python3
"""
Initialize default data for the application.

This command creates essential default data like user groups and default admin
that are required for the application to function properly.

Usage:
    python -m src.management init-data
    python -m src.management init-data --prod
"""

import asyncio
import os
import sys
from pathlib import Path

# Add src to Python path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from src.config.settings import BaseAppSettings, ProductionSettings, Settings
from src.database.models.accounts import UserGroupEnum, UserGroupModel, UserModel


def get_settings() -> BaseAppSettings:
    """Get application settings based on the current environment."""
    # Check command line arguments for production flag
    if "--prod" in sys.argv:
        return ProductionSettings()
    
    environment = os.getenv("ENVIRONMENT", "developing")
    if environment == "production":
        return ProductionSettings()
    return Settings()


async def create_async_session() -> sessionmaker[AsyncSession]:
    """Create async session factory based on current environment."""
    settings = get_settings()
    print(f"🔧 Using environment: {settings.__class__.__name__}")
    
    # Create async engine
    engine = create_async_engine(
        settings.database_url,  # type: ignore
        echo=False,  # Don't echo SQL in management commands
        future=True,
    )
    
    # Create async session factory
    return sessionmaker[AsyncSession](  # type: ignore
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )


async def create_default_user_groups(db: AsyncSession) -> None:
    """Create default user groups if they don't exist."""
    print("🔧 Checking default user groups...")
    
    # Define default groups with their IDs
    default_groups = [
        (1, UserGroupEnum.USER),
        (2, UserGroupEnum.MODERATOR),
        (3, UserGroupEnum.ADMIN),
    ]
    
    created_count = 0
    
    for group_id, group_name in default_groups:
        # Check if group already exists
        existing_group = await db.scalar(
            select(UserGroupModel).where(UserGroupModel.name == group_name)
        )
        
        if not existing_group:
            # Create new group with specific ID
            new_group = UserGroupModel(id=group_id, name=group_name)
            db.add(new_group)
            created_count += 1
            print(f"  ✅ Created group: {group_name.value} (id={group_id})")
        else:
            print(f"  ℹ️  Group already exists: {group_name.value} (id={existing_group.id})")
    
    if created_count > 0:
        await db.commit()
        print(f"🎉 Successfully created {created_count} user groups!")
    else:
        print("✨ All default user groups already exist!")


async def create_default_admin(db: AsyncSession) -> None:
    """Create default admin user if no admin exists."""
    print("👤 Checking for admin users...")
    
    # Check if admin group exists
    admin_group = await db.scalar(
        select(UserGroupModel).where(UserGroupModel.name == UserGroupEnum.ADMIN)
    )
    
    if not admin_group:
        print("  ❌ Admin group not found! Cannot create admin user.")
        return
    
    # Check if any admin user exists
    existing_admin = await db.scalar(
        select(UserModel).where(UserModel.group_id == admin_group.id)
    )
    
    if existing_admin:
        print(f"  ℹ️  Admin user already exists: {existing_admin.email}")
        return
    
    # Default admin credentials
    DEFAULT_ADMIN_EMAIL = "admin@example.com"
    DEFAULT_ADMIN_PASSWORD = "CinemaAdmin2024!"
    
    try:
        # Create default admin user
        default_admin = UserModel.create(
            email=DEFAULT_ADMIN_EMAIL,
            raw_password=DEFAULT_ADMIN_PASSWORD,
            group_id=admin_group.id
        )
        default_admin.is_active = True  # Activate admin immediately
        
        db.add(default_admin)
        await db.commit()
        await db.refresh(default_admin)
        
        print(f"  ✅ Created default admin user!")
        print(f"     📧 Email: {DEFAULT_ADMIN_EMAIL}")
        print(f"     🔑 Password: {DEFAULT_ADMIN_PASSWORD}")
        print(f"     🆔 User ID: {default_admin.id}")
        print(f"     ⚠️  IMPORTANT: Change this password immediately after first login!")
        
    except Exception as e:
        print(f"  ❌ Failed to create admin user: {e}")
        await db.rollback()


async def init_default_data() -> None:
    """Initialize all default data."""
    print("🚀 Initializing default data for Online Cinema API...")
    
    try:
        AsyncSessionLocal = await create_async_session()
        
        async with AsyncSessionLocal() as db:
            await create_default_user_groups(db)
            await create_default_admin(db)
        
        print("✅ Default data initialization completed successfully!")
        
    except Exception as e:
        print(f"❌ Error during initialization: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


async def main():
    """Main entry point."""
    await init_default_data()


if __name__ == "__main__":
    asyncio.run(main()) 