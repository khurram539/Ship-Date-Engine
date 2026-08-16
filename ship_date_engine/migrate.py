"""Database migration script."""
import sys
sys.path.insert(0, '/home/kkhoja/Code/Ship-Date-Engine')


def main():
    """Initialize database tables."""
    print("Initializing Ship Date Engine database...")
    from ship_date_engine.db import init_db
    init_db()
    print("✅ Database initialized successfully!")
    return True


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
