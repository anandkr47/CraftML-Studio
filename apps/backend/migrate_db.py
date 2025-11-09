"""
Database Migration Script
Adds missing columns to training_jobs table
"""

import sqlite3
from pathlib import Path

def migrate_database():
    """Add new columns to training_jobs table"""
    db_path = Path(__file__).parent / "craftml.db"
    
    if not db_path.exists():
        print(f"✓ Database doesn't exist yet, will be created on first run")
        return
    
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    
    # Check existing columns
    cursor.execute("PRAGMA table_info(training_jobs)")
    existing_columns = {row[1] for row in cursor.fetchall()}
    
    print(f"Existing columns: {existing_columns}")
    
    # Add missing columns
    columns_to_add = {
        'progress': 'TEXT',
        'error': 'TEXT',
        'completed_at': 'DATETIME',
    }
    
    # Rename columns if needed
    if 'started_at' not in existing_columns and 'created_at' not in existing_columns:
        # Table might have old schema
        print("! Old schema detected, will be recreated")
    
    if 'finished_at' in existing_columns:
        # Rename finished_at to completed_at
        print("→ Renaming 'finished_at' to 'completed_at'")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS training_jobs_new (
                id INTEGER PRIMARY KEY,
                job_id TEXT UNIQUE,
                status TEXT,
                params TEXT,
                logs TEXT,
                progress TEXT,
                error TEXT,
                created_at DATETIME,
                completed_at DATETIME
            )
        """)
        
        # Copy data
        cursor.execute("""
            INSERT INTO training_jobs_new (id, job_id, status, params, logs, created_at, completed_at)
            SELECT id, job_id, status, params, logs, started_at, finished_at
            FROM training_jobs
        """)
        
        # Drop old table and rename new one
        cursor.execute("DROP TABLE training_jobs")
        cursor.execute("ALTER TABLE training_jobs_new RENAME TO training_jobs")
        print("✓ Table recreated with new schema")
    else:
        # Add columns individually
        for column, col_type in columns_to_add.items():
            if column not in existing_columns:
                try:
                    cursor.execute(f"ALTER TABLE training_jobs ADD COLUMN {column} {col_type}")
                    print(f"✓ Added column: {column}")
                except sqlite3.OperationalError as e:
                    if "duplicate column" in str(e).lower():
                        print(f"→ Column {column} already exists")
                    else:
                        print(f"✗ Error adding {column}: {e}")
    
    conn.commit()
    conn.close()
    print("✓ Database migration complete!")

if __name__ == "__main__":
    migrate_database()

