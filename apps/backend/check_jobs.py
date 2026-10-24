#!/usr/bin/env python3
"""Print all jobs recorded in the database."""

import json

from db.models import Job, SessionLocal

session = SessionLocal()
jobs = session.query(Job).order_by(Job.created_at.desc()).all()

print(f"\n=== Total jobs in DB: {len(jobs)} ===\n")

for job in jobs:
    print(f"Job ID: {job.job_id} ({job.job_type})")
    print(f"  Status: {job.status}")
    print(f"  Created: {job.created_at}")
    try:
        params = json.loads(job.params) if job.params else {}
        print(f"  Params: {params}")
        print(f"  Progress: {json.loads(job.progress) if job.progress else None}")
    except ValueError:
        print("  (error parsing params/progress)")
    print()

session.close()
