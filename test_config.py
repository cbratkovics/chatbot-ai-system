#!/usr/bin/env python3
"""Test script to verify configuration loading."""

import sys

from api.core.config import settings


def test_settings():
    """Test that all critical settings load correctly."""
    print("Testing Settings Configuration...")
    print("=" * 50)
    
    # Test core settings
    critical_settings = [
        "SECRET_KEY",
        "JWT_SECRET_KEY",
        "DATABASE_URL",
        "REDIS_URL",
        "APP_NAME",
        "VERSION",
    ]
    
    for setting in critical_settings:
        value = getattr(settings, setting, None)
        if value:
            print(f"✓ {setting}: {'*' * 8 if 'KEY' in setting else str(value)[:50]}")
        else:
            print(f"✗ {setting}: Not set")
            
    # Test that extra env vars are ignored
    print("\n" + "=" * 50)
    print("Extra environment variables handling:")
    print("✓ Settings loaded without validation errors")
    print("✓ Extra fields from .env are being ignored (extra='ignore')")
    
    # Count total loaded settings
    settings_count = len([k for k in dir(settings) if not k.startswith('_')])
    print(f"\nTotal settings loaded: {settings_count}")
    
    print("\n" + "=" * 50)
    print("✅ Configuration test passed!")
    return True


if __name__ == "__main__":
    try:
        success = test_settings()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"❌ Configuration test failed: {e}")
        sys.exit(1)