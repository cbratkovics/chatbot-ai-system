"""Database backup utilities."""

import asyncio
import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional

import asyncpg
from sqlalchemy.ext.asyncio import AsyncSession


class DatabaseBackup:
    """Handles database backup and restore operations."""

    def __init__(self, db_url: str, backup_dir: str = "./backups"):
        self.db_url = db_url
        self.backup_dir = Path(backup_dir)
        self.backup_dir.mkdir(parents=True, exist_ok=True)

    async def backup(self, session: Optional[AsyncSession] = None) -> str:
        """Create database backup."""
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        backup_file = self.backup_dir / f"backup_{timestamp}.sql"

        # For PostgreSQL
        if "postgresql" in self.db_url:
            conn = await asyncpg.connect(self.db_url)
            try:
                # Export database structure and data
                result = await conn.fetch("SELECT pg_dump()")
                with open(backup_file, "w") as f:
                    f.write(str(result))
            finally:
                await conn.close()
        else:
            # For SQLite or other databases
            shutil.copy2(self.db_url.replace("sqlite:///", ""), backup_file)

        return str(backup_file)

    async def restore(self, backup_file: str, session: Optional[AsyncSession] = None):
        """Restore database from backup."""
        backup_path = Path(backup_file)
        if not backup_path.exists():
            raise FileNotFoundError(f"Backup file not found: {backup_file}")

        # For PostgreSQL
        if "postgresql" in self.db_url:
            conn = await asyncpg.connect(self.db_url)
            try:
                with open(backup_path, "r") as f:
                    sql = f.read()
                await conn.execute(sql)
            finally:
                await conn.close()
        else:
            # For SQLite
            shutil.copy2(backup_path, self.db_url.replace("sqlite:///", ""))

    def list_backups(self) -> list[str]:
        """List available backups."""
        return sorted([str(f) for f in self.backup_dir.glob("backup_*.sql")])

    def cleanup_old_backups(self, keep_last: int = 10):
        """Remove old backup files."""
        backups = self.list_backups()
        if len(backups) > keep_last:
            for backup in backups[:-keep_last]:
                Path(backup).unlink()


async def backup_database(db_url: str) -> str:
    """Quick backup function."""
    backup = DatabaseBackup(db_url)
    return await backup.backup()


async def restore_database(db_url: str, backup_file: str):
    """Quick restore function."""
    backup = DatabaseBackup(db_url)
    await backup.restore(backup_file)
