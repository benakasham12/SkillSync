"""
Command-line utility to initialize and seed the SkillSync SQLite database.
Usage: python seed.py
"""

from app.seed_data import seed_database

if __name__ == '__main__':
    print("Initializing SkillSync database with BMSIT&M CSE 13 cohort data...")
    seed_database()
    print("Done! Database ready.")
