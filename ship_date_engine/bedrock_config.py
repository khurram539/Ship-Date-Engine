import json
import os
from pathlib import Path

# AWS Bedrock configuration
AWS_REGION = "us-east-1"
DEFAULT_MODELS = [
    "amazon.nova-lite-v1:0",
    "anthropic.claude-3-5-haiku-20241022-v1:0",
]

def get_bedrock_config():
    """Load Bedrock configuration from environment or defaults."""
    config = {
        "region": os.getenv("AWS_REGION", AWS_REGION),
        "models": [m for m in DEFAULT_MODELS if os.getenv("BEDROCK_MODEL_ID") == ""],
    }
    return config
