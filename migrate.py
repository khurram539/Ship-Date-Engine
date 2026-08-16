"""Database migration script."""
import sys
import os


def main():
    """Initialize database tables."""
    print("Initializing Ship Date Engine database...")
    
    # Add project root to Python path for import
    project_root = os.path.dirname(os.path.abspath(__file__))
    sys.path.insert(0, project_root)
    
    from ship_date_engine.db import init_db
    init_db()
    print("✅ Database initialized successfully!")
    return True


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
