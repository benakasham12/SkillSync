"""
Vercel Serverless Function Entrypoint for SkillSync.
Exposes the WSGI `app` callable and handles database initialization in /tmp.
"""

import os
import sys

# Ensure root directory is in sys.path so app modules are discoverable
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from app import create_app
from app.models import init_db
from app.seed_data import seed_database

# On Vercel, the filesystem is read-only except for /tmp
if os.environ.get('VERCEL'):
    db_path = '/tmp/skillsync.db'
else:
    db_path = os.path.join(root_dir, 'skillsync.db')


def initialize_environment():
    """Initializes and seeds database safely if needed."""
    try:
        if not os.path.exists(db_path) or os.path.getsize(db_path) == 0:
            seed_database(db_path)
    except Exception as e:
        print(f"Database initialization warning: {e}")
        try:
            init_db(db_path)
        except Exception:
            pass


initialize_environment()

app = create_app(db_path=db_path)


# Add health check endpoint
@app.route('/api/health')
def health_check():
    return {
        "status": "healthy",
        "message": "SkillSync is running successfully on Vercel!",
        "database": "connected" if os.path.exists(db_path) else "initializing"
    }


# Ensure /tmp DB exists before processing requests in ephemeral serverless instances
@app.before_request
def ensure_db_exists():
    if os.environ.get('VERCEL'):
        if not os.path.exists(db_path) or os.path.getsize(db_path) == 0:
            initialize_environment()
