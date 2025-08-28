#!/usr/bin/env python3
"""Test requirements files for conflicts."""

import subprocess
import sys
from pathlib import Path


def test_requirements(req_file):
    """Test if requirements file can be installed."""
    print(f"\n{'='*60}")
    print(f"Testing: {req_file}")
    print('='*60)
    
    cmd = [
        sys.executable, "-m", "pip", "install", 
        "--dry-run", "--quiet",
        "-r", str(req_file)
    ]
    
    try:
        result = subprocess.run(
            cmd, 
            capture_output=True, 
            text=True, 
            timeout=30
        )
        
        if result.returncode == 0:
            print(f"✅ {req_file.name} - No conflicts detected")
            return True
        else:
            print(f"❌ {req_file.name} - Conflicts found:")
            # Extract error messages
            errors = [line for line in result.stderr.split('\n') 
                     if 'ERROR' in line or 'conflict' in line.lower()]
            for error in errors[:5]:  # Show first 5 errors
                print(f"   {error}")
            return False
            
    except subprocess.TimeoutExpired:
        print(f"⚠️ {req_file.name} - Timeout during testing")
        return False
    except Exception as e:
        print(f"⚠️ {req_file.name} - Error: {e}")
        return False

def main():
    """Test all requirements files."""
    base_dir = Path(__file__).parent.parent
    req_dir = base_dir / "config" / "requirements"
    
    files_to_test = [
        req_dir / "base.txt",
        req_dir / "dev.txt",
        req_dir / "prod.txt",
    ]
    
    results = {}
    
    for req_file in files_to_test:
        if req_file.exists():
            results[req_file.name] = test_requirements(req_file)
        else:
            print(f"⚠️ File not found: {req_file}")
            results[req_file.name] = False
    
    # Summary
    print(f"\n{'='*60}")
    print("SUMMARY")
    print('='*60)
    
    for name, success in results.items():
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status}: {name}")
    
    # Check combined installation
    print(f"\n{'='*60}")
    print("Testing combined installation (base + dev)")
    print('='*60)
    
    # Create temporary requirements file
    temp_req = base_dir / "temp_combined.txt"
    with open(temp_req, 'w') as f:
        f.write("-r config/requirements/base.txt\n")
        f.write("-r config/requirements/dev.txt\n")
    
    combined_success = test_requirements(temp_req)
    temp_req.unlink()  # Remove temp file
    
    if combined_success:
        print("\n✅ All requirements are compatible!")
    else:
        print("\n❌ There are dependency conflicts that need resolution")
        sys.exit(1)

if __name__ == "__main__":
    main()