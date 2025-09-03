#!/usr/bin/env python3
"""
Final fix script to resolve ALL 200 remaining errors and get green CI.
"""

import os
import re


def fix_syntax_error_in_retry_handler():
    """Fix the corrupted import in retry_handler.py"""
    file_path = "src/chatbot_ai_system/orchestrator/retry_handler.py"
    if os.path.exists(file_path):
        with open(file_path, "r") as f:
            content = f.read()

        # Fix the corrupted line "from te, Anynacity import ("
        content = content.replace(
            "from te, Anynacity import (", "from tenacity import ("
        )

        with open(file_path, "w") as f:
            f.write(content)
        print(f"✅ Fixed syntax error in {file_path}")


def remove_unused_imports_from_init_files():
    """Remove ALL unused typing imports from __init__.py files"""
    init_files = []

    # Find all __init__.py files
    for root, dirs, files in os.walk("src/"):
        for file in files:
            if file == "__init__.py":
                init_files.append(os.path.join(root, file))

    for file_path in init_files:
        with open(file_path, "r") as f:
            lines = f.readlines()

        new_lines = []
        removed = False
        for line in lines:
            # Skip the problematic typing import line
            if (
                line.strip().startswith("from typing import")
                and "Any, Dict, List" in line
            ):
                removed = True
                continue
            new_lines.append(line)

        if removed:
            with open(file_path, "w") as f:
                f.writelines(new_lines)
            print(f"✅ Removed unused imports from {file_path}")


def add_missing_type_imports():
    """Add missing imports for Dict, Any, TypeVar, Generic, etc."""

    files_needing_fixes = {
        "src/chatbot_ai_system/core/models/model_factory.py": ["Dict"],
        "src/chatbot_ai_system/core/tenancy/tenant_manager.py": ["Dict"],
        "src/chatbot_ai_system/infrastructure/connection_pool.py": ["Generic"],
        "src/chatbot_ai_system/orchestrator/circuit_breaker.py": ["TypeVar"],
        "src/chatbot_ai_system/orchestrator/orchestrator.py": ["Dict", "List"],
        "src/chatbot_ai_system/providers/model_factory.py": ["Dict"],
        "src/chatbot_ai_system/orchestration/fallback_manager.py": ["Dict", "Any"],
        "src/chatbot_ai_system/orchestration/load_balancer.py": ["Dict"],
        "src/chatbot_ai_system/orchestration/model_router.py": ["Dict", "Any"],
        "src/chatbot_system_core/orchestration/fallback_manager.py": ["Any"],
        "src/chatbot_system_core/orchestration/model_router.py": ["Any"],
    }

    for file_path, needed_imports in files_needing_fixes.items():
        if not os.path.exists(file_path):
            continue

        with open(file_path, "r") as f:
            content = f.read()

        # Check if typing import exists
        if "from typing import" in content:
            # Add to existing import
            for import_name in needed_imports:
                if (
                    import_name
                    not in content.split("from typing import")[1].split("\n")[0]
                ):
                    content = re.sub(
                        r"(from typing import [^)]+)",
                        lambda m: (
                            m.group(1) + f", {import_name}"
                            if f", {import_name}" not in m.group(1)
                            else m.group(1)
                        ),
                        content,
                        count=1,
                    )
        else:
            # Add new import after docstring
            lines = content.split("\n")
            insert_idx = 0
            for i, line in enumerate(lines):
                if '"""' in line and i > 0:
                    insert_idx = i + 1
                    break

            import_line = f"from typing import {', '.join(needed_imports)}"
            lines.insert(insert_idx, import_line)
            content = "\n".join(lines)

        with open(file_path, "w") as f:
            f.write(content)
        print(f"✅ Added {', '.join(needed_imports)} to {file_path}")


def fix_bare_except():
    """Fix bare except in ws_manager.py"""
    file_path = "src/chatbot_ai_system/websocket/ws_manager.py"
    if os.path.exists(file_path):
        with open(file_path, "r") as f:
            content = f.read()

        # Replace bare except with Exception
        content = re.sub(r"(\s+)except:\n", r"\1except Exception:\n", content)

        with open(file_path, "w") as f:
            f.write(content)
        print(f"✅ Fixed bare except in {file_path}")


def main():
    print("🚀 Final fix for all 200 errors...")
    print("\n1️⃣ Fixing syntax error...")
    fix_syntax_error_in_retry_handler()

    print("\n2️⃣ Removing unused imports from __init__.py files...")
    remove_unused_imports_from_init_files()

    print("\n3️⃣ Adding missing type imports...")
    add_missing_type_imports()

    print("\n4️⃣ Fixing bare except...")
    fix_bare_except()

    print("\n✅ All fixes applied! Now commit and push:")
    print("  git add -A")
    print("  git commit -m 'fix: resolve all remaining linting errors'")
    print("  git push")
    print("\n🎉 Your CI should be green after this!")


if __name__ == "__main__":
    main()
