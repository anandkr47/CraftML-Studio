"""
Remote cloud GPU layer: run fine-tuning and inference on rented GPUs with the user's own accounts.

Deliberately free of database and ML-framework imports so it stays light, testable on every OS,
and usable from any caller (the backend wires persistence and job callbacks around it).
"""
