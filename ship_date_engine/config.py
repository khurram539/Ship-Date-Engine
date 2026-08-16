"""
Configuration module for Ship Date Engine.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class Settings:
    """Application settings."""
    
    host: str = "127.0.0.1"
    port: int = 8000
    
    # Database configuration
    db_path: str = field(default_factory=lambda: Path(__file__).parent.parent / "ship_date.db")
    
    # API settings
    api_version: str = "v1"
    max_upload_size_mb: int = 25
    
    # AI/Bedrock settings
    aws_region: Optional[str] = None
    bedrock_model_id: Optional[str] = field(default_factory=lambda: "amazon.nova-lite-v1:0")
    
    # Logging
    log_level: str = "INFO"


class Config:
    """Singleton configuration."""
    
    _instance: Optional[Settings] = None
    
    @classmethod
    def get(cls) -> Settings:
        """Get singleton config instance."""
        if cls._instance is None:
            cls._instance = cls._load()
        return cls._instance
    
    @classmethod
    def reload(cls) -> None:
        """Reload configuration from environment."""
        cls._instance = None
    
    @classmethod
    def _load(cls) -> Settings:
        """Load settings from environment variables with defaults."""
        # Host/Port
        host = os.getenv("SHIP_DATE_HOST", "127.0.0.1")
        port_str = os.getenv("SHIP_DATE_PORT")
        port = int(port_str) if port_str else 8000
        
        # Database
        db_path = os.getenv("SHIP_DATE_DB_PATH")
        if db_path:
            db_path = Path(db_path).as_posix()
        
        # API version
        api_version = os.getenv("SHIP_DATE_API_VERSION", "v1")
        
        # AWS/Bedrock
        aws_region = os.getenv("AWS_REGION", os.getenv("AWS_DEFAULT_REGION"))
        bedrock_model_id = os.getenv("BEDROCK_MODEL_ID")
        
        # Logging
        log_level = os.getenv("LOG_LEVEL", "INFO")
        
        return Settings(
            host=host,
            port=port,
            db_path=db_path or str(Path(__file__).parent.parent / "ship_date.db"),
            api_version=api_version,
            aws_region=aws_region,
            bedrock_model_id=bedrock_model_id,
            log_level=log_level,
        )
