#!/usr/bin/env python3
"""Check training jobs in database"""

from db.models import SessionLocal, TrainingJob
import json

session = SessionLocal()
jobs = session.query(TrainingJob).all()

print(f"\n=== Total jobs in DB: {len(jobs)} ===\n")

for job in jobs:
    print(f"Job ID: {job.job_id}")
    print(f"  Status: {job.status}")
    print(f"  Created: {job.created_at}")
    
    # Parse params
    try:
        params = json.loads(job.params) if isinstance(job.params, str) else {}
        print(f"  Model: {params.get('model_name', 'from scratch')}")
        print(f"  Dataset: {params.get('dataset_path', 'unknown')}")
    except:
        print(f"  Params: (error parsing)")
    
    # Parse progress
    try:
        if job.progress:
            progress = json.loads(job.progress) if isinstance(job.progress, str) else {}
            print(f"  Progress: {progress}")
        else:
            print(f"  Progress: None")
    except:
        print(f"  Progress: (error parsing)")
    
    print()

session.close()

