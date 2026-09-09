"""ENABLE_VECTOR_SEARCH gate: Pinecone must never load unless the flag is on."""

import os
import subprocess
import sys

import pytest

from chatbot_ai_system.config.settings import Settings


def make_settings(**aliases):
    """Env-alias kwargs with dotenv disabled: explicit values must win over .env."""
    return Settings(_env_file=None, **aliases)


def test_app_import_does_not_load_pinecone_or_sklearn():
    # Fresh interpreter: other tests in this process legitimately import both libraries.
    code = (
        "import sys, chatbot_ai_system.server.main, chatbot_ai_system.vector_store;"
        "from chatbot_ai_system.vector_store import get_vector_store;"
        "from chatbot_ai_system.config.settings import Settings;"
        "assert get_vector_store(Settings(_env_file=None, ENABLE_VECTOR_SEARCH=False, PINECONE_API_KEY='k')) is None;"
        "heavy = [m for m in sys.modules if m.split('.')[0] in ('pinecone', 'sklearn')];"
        "print('HEAVY=' + ','.join(sorted(heavy)))"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        env={**os.environ, "ENVIRONMENT": "test", "ENABLE_VECTOR_SEARCH": "false"},
        timeout=120,
    )
    assert result.returncode == 0, result.stderr[-2000:]
    assert "HEAVY=\n" in result.stdout or result.stdout.strip().endswith("HEAVY="), result.stdout


def test_flag_on_without_key_is_a_clear_error():
    from chatbot_ai_system.vector_store import get_vector_store

    settings = make_settings(ENABLE_VECTOR_SEARCH=True, PINECONE_API_KEY="")
    with pytest.raises(RuntimeError, match="PINECONE_API_KEY"):
        get_vector_store(settings)


def test_is_vector_search_enabled_requires_flag_and_keys():
    assert make_settings(ENABLE_VECTOR_SEARCH=False).is_vector_search_enabled is False
    assert (
        make_settings(ENABLE_VECTOR_SEARCH=True, PINECONE_API_KEY="x", OPENAI_API_KEY="y")
    ).is_vector_search_enabled is True
