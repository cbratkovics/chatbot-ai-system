#!/usr/bin/env python3
"""
Quick fix script for all linting errors in the CI/CD pipeline.
Handles both F401 (unused imports) and F821 (undefined names) errors.
"""

import os
import re
import subprocess
from pathlib import Path


def fix_undefined_dict_errors():
    """Add missing Dict import to files that need it."""

    # Files with F821 Dict errors based on the error log
    files_needing_dict = [
        "src/chatbot_system_core/orchestration/fallback_manager.py",
        "src/chatbot_system_core/orchestration/load_balancer.py",
        "src/chatbot_system_core/orchestration/model_router.py",
    ]

    for filepath in files_needing_dict:
        if not os.path.exists(filepath):
            print(f"⚠️  File not found: {filepath}")
            continue

        with open(filepath, "r") as f:
            content = f.read()

        # Check if Dict is already imported
        if (
            "from typing import" in content
            and "Dict" not in content.split("from typing import")[1].split("\n")[0]
        ):
            # Add Dict to existing typing import
            content = re.sub(
                r"(from typing import [^)]+)",
                lambda m: (
                    m.group(1) + ", Dict" if ", Dict" not in m.group(1) else m.group(1)
                ),
                content,
                count=1,
            )
        elif "from typing import" not in content:
            # Add new typing import after docstring
            lines = content.split("\n")
            insert_idx = 0

            # Find the right place to insert (after module docstring)
            in_docstring = False
            for i, line in enumerate(lines):
                if line.strip().startswith('"""'):
                    if not in_docstring:
                        in_docstring = True
                    else:
                        insert_idx = i + 1
                        break

            lines.insert(insert_idx, "from typing import Dict")
            content = "\n".join(lines)

        with open(filepath, "w") as f:
            f.write(content)

        print(f"✅ Fixed Dict import in: {filepath}")


def run_ruff_autofix():
    """Run ruff with --fix to auto-fix fixable errors."""
    print("\n🔧 Running ruff auto-fix...")
    result = subprocess.run(
        ["ruff", "check", "--fix", "src/"], capture_output=True, text=True
    )

    if result.returncode == 0:
        print("✅ Ruff auto-fix completed successfully")
    else:
        print(f"⚠️  Ruff fix completed with warnings")

    return result


def verify_fixes():
    """Run ruff check to verify all issues are fixed."""
    print("\n🔍 Verifying all fixes...")
    result = subprocess.run(
        ["ruff", "check", "src/", "--statistics"], capture_output=True, text=True
    )

    if result.returncode == 0:
        print("🎉 All linting errors fixed! Your CI/CD should pass now.")
    else:
        print("⚠️  Some issues may remain:")
        print(result.stdout)

    return result.returncode == 0


def main():
    print("🚀 Starting quick fix for all linting errors...")

    # Step 1: Fix undefined Dict errors first
    fix_undefined_dict_errors()

    # Step 2: Run ruff auto-fix for unused imports
    run_ruff_autofix()

    # Step 3: Verify all fixes
    success = verify_fixes()

    if success:
        print("\n✅ SUCCESS! Now run:")
        print("  git add -A")
        print("  git commit -m 'fix: resolve all linting errors in CI/CD'")
        print("  git push")
    else:
        print("\n⚠️  Some manual fixes may still be needed. Check the output above.")


if __name__ == "__main__":
    main()
