#!/usr/bin/env python3
"""
Automated MyPy Error Fixer Script
Fixes common type annotation issues in your codebase
"""

import os
import re
from pathlib import Path
from typing import List, Tuple


def fix_any_type_annotations(content: str) -> str:
    """Replace 'any' with 'typing.Any' in type annotations."""
    # Pattern to match type annotations with 'any'
    patterns = [
        (r":\s*dict\[([^,\]]+),\s*any\]", r": dict[\1, Any]"),
        (r":\s*Dict\[([^,\]]+),\s*any\]", r": Dict[\1, Any]"),
        (r"->\s*dict\[str,\s*any\]", r"-> Dict[str, Any]"),
        (r"->\s*tuple\[bool,\s*dict\[str,\s*any\]\]", r"-> Tuple[bool, Dict[str, Any]]"),
        (r"->\s*dict\[str,\s*dict\[str,\s*any\]\]", r"-> Dict[str, Dict[str, Any]]"),
    ]

    for pattern, replacement in patterns:
        content = re.sub(pattern, replacement, content)

    # Ensure typing imports are present
    if "from typing import" in content and "Any" not in content:
        content = re.sub(r"(from typing import[^\\n]+)", r"\1, Any", content)
    elif "import typing" not in content and "from typing" not in content:
        # Add typing import at the top
        lines = content.split("\n")
        for i, line in enumerate(lines):
            if line.startswith("import ") or line.startswith("from "):
                lines.insert(i, "from typing import Any, Dict, List, Tuple, Optional")
                break
        content = "\n".join(lines)

    return content


def fix_missing_type_annotations(content: str) -> str:
    """Add missing type annotations for common patterns."""
    patterns = [
        # Fix empty dict/list/set annotations
        (r"(\w+):\s*dict\s*=\s*\{\}", r"\1: Dict[str, Any] = {}"),
        (r"(\w+):\s*list\s*=\s*\[\]", r"\1: List[Any] = []"),
        (r"(\w+):\s*set\s*=\s*set\(\)", r"\1: set[str] = set()"),
        # Common variable patterns
        (r"permissions\s*=\s*set\(\)", r"permissions: set[str] = set()"),
        (r"model_usage\s*=\s*\{\}", r"model_usage: Dict[str, Any] = {}"),
        (r"strategy_usage\s*=\s*\{\}", r"strategy_usage: Dict[str, Any] = {}"),
        (r"_cache\s*=\s*\{\}", r"_cache: Dict[str, Any] = {}"),
        (r"reasons\s*=\s*\{\}", r"reasons: Dict[str, Any] = {}"),
        (r"rolling_window\s*=\s*\[\]", r"rolling_window: List[float] = []"),
        (r"consistent_hash_ring\s*=\s*\{\}", r"consistent_hash_ring: Dict[int, str] = {}"),
        (r"providers\s*=\s*\{\}", r"providers: Dict[str, Any] = {}"),
        (r"tenants_cache\s*=\s*\{\}", r"tenants_cache: Dict[str, Any] = {}"),
        (r"request_counts\s*=\s*defaultdict", r"request_counts: Dict[str, int] = defaultdict"),
        (
            r"request_timestamps\s*=\s*defaultdict",
            r"request_timestamps: Dict[str, List[float]] = defaultdict",
        ),
        (r"queue\s*=\s*asyncio\.Queue", r"queue: asyncio.Queue[Any] = asyncio.Queue"),
    ]

    for pattern, replacement in patterns:
        content = re.sub(pattern, replacement, content)

    return content


def fix_float_int_assignments(content: str) -> str:
    """Fix float/int type mismatches."""
    patterns = [
        # Common patterns where float is assigned to int
        (r"wait_time\s*=\s*0\b", r"wait_time = 0.0"),
        (r"(\w+_time)\s*:\s*int\s*=\s*([0-9.]+)", r"\1: float = \2"),
        # Convert float to int where needed
        (r'TokenBucket\(capacity=(\w+\["capacity"\])', r"TokenBucket(capacity=int(\1)"),
        (r"min\(self\.capacity,", r"min(float(self.capacity),"),
    ]

    for pattern, replacement in patterns:
        content = re.sub(pattern, replacement, content)

    return content


def fix_pydantic_field_issues(content: str) -> str:
    """Fix Pydantic v1 to v2 Field issues."""
    # Replace env parameter with alias or remove it
    content = re.sub(r'Field\(([^)]*),\s*env="([^"]+)"([^)]*)\)', r"Field(\1\3)", content)

    # Fix min_items/max_items to min_length/max_length for Pydantic v2
    content = re.sub(r"min_items=", r"min_length=", content)
    content = re.sub(r"max_items=", r"max_length=", content)

    return content


def fix_sqlalchemy_base_issues(content: str) -> str:
    """Fix SQLAlchemy Base class issues."""
    if "from sqlalchemy.ext.declarative import declarative_base" not in content:
        if "Base = declarative_base()" in content:
            # Add import
            lines = content.split("\n")
            for i, line in enumerate(lines):
                if "from sqlalchemy" in line:
                    lines.insert(i + 1, "from sqlalchemy.ext.declarative import declarative_base")
                    break
            content = "\n".join(lines)

    # Replace problematic Base references
    content = re.sub(r'Variable ".*\.Base" is not valid as a type', r"", content)

    return content


def fix_async_iterator_issues(content: str) -> str:
    """Fix async iterator issues."""
    # Fix __aiter__ on dict
    content = re.sub(
        r'(\w+)\["([^"]+)"\]\.__aiter__',
        r'(\1["\2"] if hasattr(\1["\2"], "__aiter__") else (\1["\2"] for _ in [])).__aiter__',
        content,
    )

    return content


def process_file(filepath: Path) -> Tuple[bool, List[str]]:
    """Process a single Python file and fix type issues."""
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            original_content = f.read()

        content = original_content

        # Apply all fixes
        content = fix_any_type_annotations(content)
        content = fix_missing_type_annotations(content)
        content = fix_float_int_assignments(content)
        content = fix_pydantic_field_issues(content)
        content = fix_sqlalchemy_base_issues(content)
        content = fix_async_iterator_issues(content)

        # Only write if content changed
        if content != original_content:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(content)
            return True, [f"Fixed {filepath}"]

        return False, []

    except Exception as e:
        return False, [f"Error processing {filepath}: {e}"]


def main():
    """Main function to process all Python files."""
    src_dir = Path("src")

    if not src_dir.exists():
        print("Error: 'src' directory not found. Run this script from project root.")
        return

    fixed_files = []
    errors = []

    # Process all Python files
    for py_file in src_dir.rglob("*.py"):
        # Skip __pycache__ and other generated files
        if "__pycache__" in str(py_file):
            continue

        success, messages = process_file(py_file)

        if success:
            fixed_files.extend(messages)
        elif messages:
            errors.extend(messages)

    # Print results
    print(f"\n✅ Fixed {len(fixed_files)} files:")
    for msg in fixed_files[:20]:  # Show first 20
        print(f"  - {msg}")

    if len(fixed_files) > 20:
        print(f"  ... and {len(fixed_files) - 20} more")

    if errors:
        for error in errors[:10]:
            print(f"  - {error}")


if __name__ == "__main__":
    main()
