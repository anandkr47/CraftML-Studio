# Writable Directories Guide

## Overview
After installation, the application extracts resources and creates writable directories in the user's data directory. This ensures all user data (models, datasets, logs, database) is stored in a writable location outside the installation directory.

## Directory Structure After Installation

### Windows
```
%APPDATA%\CraftML Studio\
├── craftml.db                    # SQLite database (writable)
├── resources\                    # Extracted resources (writable)
│   ├── templates\               # Configuration templates (read-only after copy)
│   ├── icons\                    # Icon files (read-only after copy)
│   ├── models\                   # Trained models (WRITABLE)
│   └── datasets\                 # User datasets (WRITABLE)
└── logs\                         # Application logs (WRITABLE)
    ├── backend.log
    ├── training_service.log
    ├── inference_service.log
    └── ...
```

### macOS
```
~/Library/Application Support/CraftML Studio/
└── (same structure as Windows)
```

### Linux
```
~/.local/share/CraftML Studio/
└── (same structure as Windows)
```

## What Gets Extracted

### 1. **Resources Folder** (`resources/`)
Extracted on first run to `%APPDATA%\CraftML Studio\resources\`

**Read-Only Subdirectories** (copied once, not overwritten):
- `templates/` - Configuration templates
- `icons/` - Icon files

**Writable Subdirectories** (initial content copied, then user can modify):
- `models/` - For storing trained models
- `datasets/` - For storing user datasets

### 2. **Logs Directory** (`logs/`)
Created automatically at `%APPDATA%\CraftML Studio\logs\`

**Log Files:**
- `backend.log` - Main backend logs
- `training_service.log` - Training job logs
- `inference_service.log` - Model inference logs
- `crawler_service.log` - Web crawler logs
- `dedup_service.log` - Deduplication logs
- `compression_service.log` - Model compression logs
- `deployment_service.log` - Deployment logs
- `dedup_engine.log` - Deduplication engine logs

### 3. **Database** (`craftml.db`)
Created automatically at `%APPDATA%\CraftML Studio\craftml.db`

**Contains:**
- Training jobs
- Dataset metadata
- Job status and progress

## Extraction Process

The extraction happens automatically when the backend starts (first run):

1. **Check if resources already extracted**
   - If `%APPDATA%\CraftML Studio\resources\` exists, skip extraction
   - This preserves user data across app updates

2. **Extract read-only resources**
   - Copy `templates/` and `icons/` from bundled resources
   - These are copied once and not modified

3. **Initialize writable directories**
   - Create `models/` and `datasets/` directories
   - Copy initial content if present in bundled resources
   - Preserve existing user data if directories already exist

4. **Create logs directory**
   - Create `logs/` directory
   - Ready for log file writing

5. **Verify writability**
   - All directories are created with write permissions
   - Application can write models, datasets, and logs

## Code Implementation

### Extraction Logic (`apps/backend/run_server.py`)

```python
# When frozen by PyInstaller
if getattr(sys, 'frozen', False):
    from core.config import settings
    
    # Create base directories
    settings.user_data_dir.mkdir(parents=True, exist_ok=True)
    settings.models_dir.mkdir(parents=True, exist_ok=True)
    settings.datasets_dir.mkdir(parents=True, exist_ok=True)
    settings.logs_dir.mkdir(parents=True, exist_ok=True)
    
    # Extract resources on first run
    bundled_resources = Path(sys._MEIPASS) / "resources"
    user_resources_root = settings.user_data_dir / "resources"
    
    if bundled_resources.exists() and not user_resources_root.exists():
        # Copy templates and icons (read-only)
        # Copy initial models/datasets content (writable)
        # Preserve user data
```

### Settings Configuration (`core/config/settings.py`)

```python
def get_user_data_dir() -> Path:
    """Get platform-specific user data directory"""
    if getattr(sys, 'frozen', False):
        if os.name == 'nt':  # Windows
            return Path(os.environ.get('APPDATA')) / 'CraftML Studio'
        elif sys.platform == 'darwin':  # macOS
            return Path.home() / 'Library' / 'Application Support' / 'CraftML Studio'
        else:  # Linux
            return Path(os.environ.get('XDG_DATA_HOME', Path.home() / '.local' / 'share')) / 'CraftML Studio'
```

### Database Path (`apps/backend/db/models.py`)

```python
def _resolve_db_path() -> str:
    """Resolve DB path for production"""
    if is_frozen or is_prod_env:
        app_dir = base_dir / "CraftML Studio"
        app_dir.mkdir(parents=True, exist_ok=True)
        return str(app_dir / "craftml.db")
```

## Verification

Run the verification script to check all directories:

```bash
python apps/backend/verify_production_paths.py
```

This will:
- ✅ Check all directories exist
- ✅ Verify write permissions
- ✅ Test file creation/deletion
- ✅ Display directory structure

## Important Notes

1. **First Run**: Resources are extracted on first run only
2. **Updates**: User data is preserved across app updates
3. **Permissions**: All directories are created with write permissions
4. **Platform-Specific**: Paths are automatically adjusted per platform
5. **Database**: Fresh database created per user installation (not shared)

## Troubleshooting

### Directories Not Created
- Check `%APPDATA%\CraftML Studio\` exists
- Verify write permissions on user data directory
- Check backend startup logs for extraction messages

### Resources Not Extracted
- Ensure `resources/` folder is bundled with PyInstaller
- Check `--add-data "resources;resources"` in build script
- Verify `sys._MEIPASS` contains resources

### Write Permission Errors
- Ensure user has write access to `%APPDATA%`
- Check antivirus isn't blocking writes
- Verify directory permissions on Linux/macOS

## Summary

✅ **Resources**: Extracted to `%APPDATA%\CraftML Studio\resources\`  
✅ **Logs**: Created at `%APPDATA%\CraftML Studio\logs\`  
✅ **Database**: Created at `%APPDATA%\CraftML Studio\craftml.db`  
✅ **Models**: Writable at `%APPDATA%\CraftML Studio\resources\models\`  
✅ **Datasets**: Writable at `%APPDATA%\CraftML Studio\resources\datasets\`  

All directories are automatically created and made writable on first run!

