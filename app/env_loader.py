"""
Lightweight environment variable loader for SkillSync.
Loads key-value pairs from .env into os.environ without third-party dependencies.
"""

import os


def load_dotenv(env_path=None):
    """
    Read .env file and set environment variables if not already set.
    """
    if not env_path:
        root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        env_path = os.path.join(root_dir, '.env')

    if not os.path.exists(env_path):
        return

    try:
        with open(env_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                if '=' in line:
                    key, val = line.split('=', 1)
                    key = key.strip()
                    val = val.strip().strip("'").strip('"')
                    if key and key not in os.environ:
                        os.environ[key] = val
    except Exception:
        pass


# Automatically load upon import
load_dotenv()
