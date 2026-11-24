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

import app.env_loader  # Automatically loads .env configuration securely

from app import create_app
from app.models import init_db
from app.seed_data import seed_database

import tempfile

# On Vercel, the filesystem is read-only except for /tmp
if os.environ.get('VERCEL'):
    _tmp_dir = '/tmp' if os.path.isdir('/tmp') else tempfile.gettempdir()
    db_path = os.path.join(_tmp_dir, 'skillsync_listings.db')
else:
    db_path = os.path.join(root_dir, 'listings.db')


def initialize_environment():
    """Initializes and seeds database safely if needed, syncing from Supabase when cloud is enabled."""
    try:
        from app.supabase_client import is_cloud_enabled, sync_cloud_to_local_listings
        cloud_active = is_cloud_enabled()

        from app.models import query_db

        needs_init = not os.path.exists(db_path) or os.path.getsize(db_path) == 0
        if needs_init:
            init_db(db_path)

        p_cnt_row = query_db("SELECT COUNT(*) as count FROM projects", one=True, db_path=db_path)
        p_cnt = p_cnt_row['count'] if p_cnt_row else 0

        if p_cnt == 0:
            if cloud_active:
                # Hydrate projects from persistent Supabase
                sync_cloud_to_local_listings(db_path)
                p_cnt_after = query_db("SELECT COUNT(*) as count FROM projects", one=True, db_path=db_path)
                # If Supabase has no projects or is not yet configured, seed baseline cohort
                if not p_cnt_after or p_cnt_after['count'] == 0:
                    seed_database(db_path)
            else:
                seed_database(db_path)
        elif cloud_active:
            # Sync any new or updated cloud projects on warm start
            sync_cloud_to_local_listings(db_path)
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


# Ensure /tmp DB exists and is populated before processing requests in ephemeral serverless instances
@app.before_request
def ensure_db_exists():
    if os.environ.get('VERCEL'):
        if not os.path.exists(db_path) or os.path.getsize(db_path) == 0:
            initialize_environment()
        else:
            try:
                from app.models import query_db
                cnt = query_db("SELECT COUNT(*) as c FROM projects", one=True, db_path=db_path)
                if not cnt or cnt['c'] == 0:
                    initialize_environment()
            except Exception:
                initialize_environment()


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print(f"Starting SkillSync server on http://127.0.0.1:{port}")
    app.run(host='0.0.0.0', port=port, debug=True)
