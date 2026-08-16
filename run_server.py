"""
Run Ship Date Engine Backend Server.

This script starts the FastAPI REST API server for the Ship Date Engine application.
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Run Ship Date Engine Backend API Server"
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Host address to bind (default: 127.0.0.1)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port number (default: 8000)",
    )
    parser.add_argument(
        "--reload",
        action="store_true",
        help="Enable auto-reload during development",
    )
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Logging level (default: INFO)",
    )
    return parser.parse_args()


def main() -> None:
    """Main entry point."""
    args = parse_args()
    
    # Setup logging
    log_level = getattr(logging, args.log_level.upper())
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    logger = logging.getLogger(__name__)
    
    # Validate dependencies
    try:
        from fastapi import FastAPI
        from uvicorn import run
        logger.info("✅ Required packages available: fastapi, uvicorn")
    except ImportError as e:
        logger.error("❌ Missing required package: %s", e)
        logger.error("Install with: pip install -r requirements.txt")
        sys.exit(1)
    
    # Import and create the API app
    try:
        from ship_date_engine.api import create_app, create_database_tables
        from ship_date_engine.config import Config
        
        # Initialize database tables
        logger.info("Initializing database...")
        create_database_tables()
        
        # Create application
        app = create_app()
        
        config = Config.get()
        
        # Override settings from arguments if provided
        if args.host != "127.0.0.1":
            config.host = args.host
        if args.port != 8000:
            config.port = args.port
        
        logger.info(
            f"🚀 Starting Ship Date Engine API server on http://{config.host}:{config.port}"
        )
        logger.info(f"   Auto-reload: {args.reload}")
        logger.info("   Press Ctrl+C to stop the server")
        
        # Start uvicorn server
        run(
            app="ship_date_engine.api:create_app",
            host=config.host,
            port=config.port,
            reload=args.reload,
            log_level=args.log_level.lower(),
        )
        
    except ImportError as e:
        logger.error("❌ Failed to import ship_date_engine modules: %s", e)
        logger.error("Please ensure all dependencies are installed")
        sys.exit(1)
    except Exception as e:
        logger.error("❌ Server startup failed: %s", e)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
