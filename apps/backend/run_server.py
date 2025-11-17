import uvicorn
import sys
import os
import shutil
from pathlib import Path

# Windows-specific: Allocate console window when --console is used
if sys.platform == "win32" and getattr(sys, 'frozen', False):
    import ctypes
    kernel32 = ctypes.windll.kernel32
    
    def allocate_console():
        """Allocate a console window for Windows GUI applications"""
        try:
            # Try to attach to parent console if running from terminal
            if kernel32.AttachConsole(-1):  # ATTACH_PARENT_PROCESS
                return True
        except:
            pass
        
        try:
            # Otherwise, allocate a new console
            if kernel32.AllocConsole():
                # Reopen stdout/stderr to the new console
                sys.stdout = open('CONOUT$', 'w')
                sys.stderr = open('CONOUT$', 'w')
                return True
        except:
            pass
        
        return False

# When frozen by Nuitka, use the bundled app directly
# With --standalone: executable directory contains all bundled files
# Nuitka doesn't use sys._MEIPASS, use os.path.dirname(sys.executable) instead
if getattr(sys, 'frozen', False):
    # Running as Nuitka bundle
    # Get bundle directory and add it to sys.path so we can import main.py
    import os
    bundle_dir = Path(os.path.dirname(sys.executable))
    if str(bundle_dir) not in sys.path:
        sys.path.insert(0, str(bundle_dir))
    
    # Import from the bundled package (main.py is included via --include-data-file)
    from main import app
    
    # Ensure user data directories exist on first run
    from core.config import settings
    
    # Create base user data directory
    settings.user_data_dir.mkdir(parents=True, exist_ok=True)
    
    # Create writable directories (these will be empty initially, ready for user data)
    settings.models_dir.mkdir(parents=True, exist_ok=True)
    settings.datasets_dir.mkdir(parents=True, exist_ok=True)
    settings.logs_dir.mkdir(parents=True, exist_ok=True)
    
    # Get bundle directory (Nuitka: directory containing the executable)
    # For Nuitka, sys.executable points to the EXE, so we get its directory
    # (bundle_dir already set above)
    
    # Copy bundled resources to user data directory on first run
    bundled_resources = bundle_dir / "resources"
    user_resources_root = settings.user_data_dir / "resources"
    
    # Resource subdirectories that should be copied (read-only templates/icons)
    read_only_subdirs = ["templates", "icons"]
    # Writable subdirectories (models/datasets - copy initial content if any)
    writable_subdirs = ["models", "datasets"]
    
    # Copy main resources directory structure if it doesn't exist (silently for speed)
    if bundled_resources.exists() and not user_resources_root.exists():
        # Silent setup - no prints to speed up startup
        user_resources_root.mkdir(parents=True, exist_ok=True)
        
        # Copy read-only subdirectories (templates, icons)
        for subdir in read_only_subdirs:
            bundled_subdir = bundled_resources / subdir
            user_subdir = user_resources_root / subdir
            if bundled_subdir.exists() and bundled_subdir.is_dir():
                shutil.copytree(bundled_subdir, user_subdir, dirs_exist_ok=False)
        
        # For writable subdirectories, copy initial content but allow overwrites
        for subdir in writable_subdirs:
            bundled_subdir = bundled_resources / subdir
            user_subdir = user_resources_root / subdir
            if bundled_subdir.exists() and bundled_subdir.is_dir():
                # Only copy if user directory doesn't exist (preserve user data)
                if not user_subdir.exists():
                    shutil.copytree(bundled_subdir, user_subdir, dirs_exist_ok=False)
        
        # Copy any other files in resources root (if any)
        for item in bundled_resources.iterdir():
            if item.is_file() and not any(item.name.startswith(s) for s in read_only_subdirs + writable_subdirs):
                user_file = user_resources_root / item.name
                if not user_file.exists():
                    shutil.copy2(item, user_file)
    
    # Ensure writable subdirectories exist even if resources weren't copied
    for subdir in writable_subdirs:
        user_subdir = user_resources_root / subdir
        user_subdir.mkdir(parents=True, exist_ok=True)
    
    # Directory structure verified (silent for speed)
else:
    # Running as script in dev
    PROJECT_ROOT = Path(__file__).resolve().parents[2]
    if str(PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(PROJECT_ROOT))
    from apps.backend.main import app
    from core.config import settings


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="CraftML Studio Backend Server")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind to (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=5000, help="Port to bind to (default: 5000)")
    parser.add_argument("--log-level", default="info", choices=["debug", "info", "warning", "error"], help="Log level (default: info)")
    parser.add_argument("--console", action="store_true", help="Enable console output (for standalone testing)")
    
    args = parser.parse_args()
    
    # Allocate console window on Windows if --console is used
    if args.console and sys.platform == "win32" and getattr(sys, 'frozen', False):
        if allocate_console():
            print("Console window allocated for debugging output...")
        else:
            print("Warning: Could not allocate console window. Output may not be visible.")
    
    # Detect if running standalone (not from Tauri)
    # When CRAFTML_ENV=prod, it's running from Tauri (silent mode)
    # Otherwise, or with --console flag, show output
    is_standalone = args.console or os.environ.get("CRAFTML_ENV") != "prod"
    
    if is_standalone:
        # Show startup info when running standalone
        print("=" * 70)
        print("CraftML Studio Backend Server")
        print("=" * 70)
        if getattr(sys, 'frozen', False):
            print(f"Running as: Nuitka bundle")
            print(f"User data directory: {settings.user_data_dir}")
            print(f"Logs directory: {settings.logs_dir}")
        else:
            print(f"Running as: Development script")
        print(f"Starting server on http://{args.host}:{args.port}")
        print(f"Log level: {args.log_level}")
        print("=" * 70)
        print()
    
    # Keep localhost/5000 for the desktop app integration
    # Optimize for fast startup: single worker, no access log, minimal logging
    uvicorn.run(
        app, 
        host=args.host, 
        port=args.port, 
        log_level=args.log_level,
        access_log=is_standalone,  # Enable access logs when running standalone
        workers=1,  # Single worker for desktop app
        loop="asyncio"  # Use asyncio for better performance
    )


