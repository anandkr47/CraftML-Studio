"""
Verify that production paths are correctly set up after installation
Run this script to check the folder structure in %APPDATA%
"""

import sys
import os
from pathlib import Path

def verify_production_paths():
    """Verify all production paths exist and are writable"""
    print("="*70)
    print("CraftML Studio - Production Path Verification")
    print("="*70)
    
    # Simulate frozen environment
    sys.frozen = True
    
    from core.config import settings
    
    print(f"\n📁 User Data Directory: {settings.user_data_dir}")
    print(f"   Exists: {settings.user_data_dir.exists()}")
    
    print(f"\n📁 Resources Root: {settings.resources_root}")
    print(f"   Exists: {settings.resources_root.exists()}")
    
    print(f"\n📁 Models Directory: {settings.models_dir}")
    print(f"   Exists: {settings.models_dir.exists()}")
    print(f"   Writable: {os.access(settings.models_dir, os.W_OK) if settings.models_dir.exists() else 'N/A'}")
    
    print(f"\n📁 Datasets Directory: {settings.datasets_dir}")
    print(f"   Exists: {settings.datasets_dir.exists()}")
    print(f"   Writable: {os.access(settings.datasets_dir, os.W_OK) if settings.datasets_dir.exists() else 'N/A'}")
    
    print(f"\n📁 Logs Directory: {settings.logs_dir}")
    print(f"   Exists: {settings.logs_dir.exists()}")
    print(f"   Writable: {os.access(settings.logs_dir, os.W_OK) if settings.logs_dir.exists() else 'N/A'}")
    
    # Check for resource subdirectories
    print(f"\n📂 Resource Subdirectories:")
    for subdir in ["templates", "icons", "models", "datasets"]:
        subdir_path = settings.resources_root / subdir
        print(f"   {subdir}: {subdir_path.exists()}")
    
    # Test write permissions
    print(f"\n✍️  Testing Write Permissions:")
    
    # Test models directory
    test_file = settings.models_dir / ".test_write"
    try:
        test_file.write_text("test")
        test_file.unlink()
        print(f"   ✓ Models directory is writable")
    except Exception as e:
        print(f"   ✗ Models directory write failed: {e}")
    
    # Test logs directory
    test_file = settings.logs_dir / ".test_write"
    try:
        test_file.write_text("test")
        test_file.unlink()
        print(f"   ✓ Logs directory is writable")
    except Exception as e:
        print(f"   ✗ Logs directory write failed: {e}")
    
    print("\n" + "="*70)
    print("Verification complete!")
    print("="*70)

if __name__ == "__main__":
    verify_production_paths()

