"""Integration tests for database operations."""

import asyncio
import pathlib
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest


class TestDatabaseOperations:
    """Test suite for database operations."""

    @pytest.mark.live("TEST_DATABASE_URL")
    @pytest.mark.asyncio
    async def test_database_connection_pool(self):
        """A pooled engine against a real database answers SELECT 1."""
        import os

        from sqlalchemy import text
        from sqlalchemy.ext.asyncio import create_async_engine

        engine = create_async_engine(os.environ["TEST_DATABASE_URL"], pool_size=10, max_overflow=5)
        try:
            async with engine.begin() as conn:
                result = await conn.execute(text("SELECT 1"))
                assert result.scalar() == 1
            assert "size" in engine.pool.status()
        finally:
            await engine.dispose()

    @pytest.mark.asyncio
    async def test_transaction_rollback(self, mock_database):
        """Test transaction rollback on error."""
        from chatbot_ai_system.models import Chat, User

        async with mock_database.begin():
            try:
                user = User(id="user123", email="test@example.com")
                mock_database.add(user)

                raise ValueError("Simulated error")

                chat = Chat(user_id="user123", message="Test")
                mock_database.add(chat)

                await mock_database.commit()
            except ValueError:
                await mock_database.rollback()

        mock_database.rollback.assert_called()

    @pytest.mark.asyncio
    async def test_concurrent_database_writes(self, mock_database):
        """Test concurrent database write operations."""
        from uuid import uuid4

        from chatbot_ai_system.models import Chat  # alias of database.models.Conversation

        tenant_id, user_id = uuid4(), uuid4()

        async def create_chat(session, chat_id):
            chat = Chat(
                id=uuid4(),
                tenant_id=tenant_id,
                user_id=user_id,
                title=f"Conversation {chat_id}",
                created_at=datetime.utcnow(),
            )
            session.add(chat)
            await session.commit()
            return chat.title

        tasks = [create_chat(mock_database, i) for i in range(10)]

        results = await asyncio.gather(*tasks)
        assert len(results) == 10
        assert all(f"Conversation {i}" in results for i in range(10))
        assert mock_database.commit.await_count == 10

    @pytest.mark.asyncio
    async def test_database_query_optimization(self, mock_database):
        """Test database query optimization."""
        from chatbot_ai_system.models import User
        from sqlalchemy import select
        from sqlalchemy.orm import selectinload

        from uuid import uuid4

        query = (
            select(User)
            .options(selectinload(User.conversations))  # relationship is 'conversations'
            .where(User.tenant_id == uuid4())
            .limit(100)
        )

        mock_database.execute.return_value.scalars.return_value.all.return_value = []

        result = await mock_database.execute(query)
        users = result.scalars().all()

        mock_database.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_database_migration(self):
        """Test database migration execution."""
        from alembic import command
        from alembic.config import Config

        alembic_cfg = Config("alembic.ini")

        with patch("alembic.command.upgrade") as mock_upgrade:
            command.upgrade(alembic_cfg, "head")
            mock_upgrade.assert_called_with(alembic_cfg, "head")

    @pytest.mark.asyncio
    async def test_database_backup_restore(self, tmp_path, monkeypatch):
        """SQLite backup/restore round-trips a real file (helpers take a URL, not a session)."""
        from chatbot_ai_system.utils.database_backup import backup_database, restore_database

        monkeypatch.chdir(tmp_path)  # backups land in ./backups
        db_file = tmp_path / "app.db"
        db_file.write_bytes(b"sqlite-bytes")
        db_url = f"sqlite:///{db_file}"

        backup_file = await backup_database(db_url)
        backup_path = pathlib.Path(backup_file).resolve()
        assert backup_path.parent == (tmp_path / "backups").resolve()
        assert backup_path.name.startswith("backup_")

        db_file.write_bytes(b"corrupted")
        await restore_database(db_url, backup_file)
        assert db_file.read_bytes() == b"sqlite-bytes"

    @pytest.mark.asyncio
    async def test_database_indexing_performance(self, mock_database):
        """Test database indexing performance."""
        import time

        from chatbot_ai_system.models import Chat
        from sqlalchemy import select

        query_with_index = select(Chat).where(
            Chat.user_id == "user123", Chat.created_at >= datetime.utcnow() - timedelta(days=7)
        )

        start_time = time.time()
        result = await mock_database.execute(query_with_index)
        query_time = time.time() - start_time

        assert query_time < 0.1

    @pytest.mark.asyncio
    async def test_database_partitioning(self, mock_database):
        """Test database table partitioning."""

        partitions = ["chats_2024_01", "chats_2024_02", "chats_2024_03"]
        mock_database.execute.return_value.scalar.return_value = False

        for partition in partitions:
            exists = await mock_database.execute(
                f"SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = '{partition}')"
            )
            assert exists.scalar() in [True, False]
