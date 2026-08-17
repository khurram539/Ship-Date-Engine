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
    configured_model = os.getenv("BEDROCK_MODEL_ID")
    config = {
        "region": os.getenv("AWS_REGION", AWS_REGION),
        "models": [configured_model] if configured_model else DEFAULT_MODELS,
    }
    return config
