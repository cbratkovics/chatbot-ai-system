"""Test CLI commands."""

import os
import json
from unittest.mock import MagicMock, patch

# Ensure test environment is set before imports
os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("DATABASE_URL", "postgresql://postgres:test123@localhost:5432/test_db")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/15")

import pytest
from click.testing import CliRunner

# Skip all CLI tests if CLI module not available
pytest.importorskip("chatbot_ai_system.cli")
from chatbot_ai_system.cli import cli


class TestCLICommands:
    """Test CLI commands"""

    def test_version_command(self):
        """Test version command."""
        with patch("chatbot_ai_system.cli.get_version", return_value="1.0.0"):
            runner = CliRunner()
            result = runner.invoke(cli, ["version"])

            assert result.exit_code == 0
            assert "1.0.0" in result.output

    def test_version_json_format(self):
        """Test version command with JSON format."""
        with patch("chatbot_ai_system.cli.get_version", return_value="1.0.0"):
            runner = CliRunner()
            result = runner.invoke(cli, ["version", "--format", "json"])

            assert result.exit_code == 0
            output = json.loads(result.output)
            assert output["version"] == "1.0.0"

    def test_help_command(self):
        """Test help command."""
        runner = CliRunner()
        result = runner.invoke(cli, ["--help"])

        assert result.exit_code == 0
        assert "Usage:" in result.output

    def test_serve_command(self):
        """Test serve command."""
        with patch("chatbot_ai_system.cli.run_server") as mock_run:
            runner = CliRunner()
            result = runner.invoke(cli, ["serve", "--port", "3000"])

            mock_run.assert_called_once()
            assert result.exit_code == 0  # Use result variable

    def test_serve_with_reload(self):
        """Test serve command with reload flag."""
        with patch("chatbot_ai_system.cli.run_server") as mock_run:
            runner = CliRunner()
            result = runner.invoke(cli, ["serve", "--reload"])

            mock_run.assert_called_once()
            assert result.exit_code == 0  # Use result variable

    def test_demo_command(self):
        """Test demo command."""
        with patch("chatbot_ai_system.cli.run_demo") as mock_demo:
            runner = CliRunner()
            result = runner.invoke(cli, ["demo"])

            mock_demo.assert_called_once()
            assert result.exit_code == 0  # Use result variable

    def test_bench_command(self):
        """Test benchmark command."""
        with patch("chatbot_ai_system.cli.run_benchmark") as mock_bench:
            runner = CliRunner()
            result = runner.invoke(cli, ["bench", "--requests", "10"])

            mock_bench.assert_called_once()
            assert result.exit_code == 0  # Use result variable
