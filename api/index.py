"""
Vercel Serverless Function entrypoint for SkillSync.
Exposes the WSGI `app` object and handles /tmp database initialization on cold starts.
"""

import os
import sys

# Ensure root directory is on the python search path
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from app import create_app
from app.seed_data import seed_database

# On Vercel, the filesystem is read-only except for /tmp
if os.environ.get('VERCEL'):
    db_path = '/tmp/skillsync.db'
    if not os.path.exists(db_path) or os.path.getsize(db_path) == 0:
        seed_database(db_path)
    app = create_app(db_path=db_path)
else:
    app = create_app()

# Vercel looks for `app` in api/index.py
