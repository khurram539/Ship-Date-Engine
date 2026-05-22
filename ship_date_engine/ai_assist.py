from __future__ import annotations

import json
import os

from .models import InvoiceData, ShippingDecision, ValidationResult


DEFAULT_ACTIVE_MODELS = [
    "amazon.nova-lite-v1:0",
    "anthropic.claude-3-5-haiku-20241022-v1:0",
    "anthropic.claude-3-haiku-20240307-v1:0",
]


def generate_bedrock_insight(
    invoices: list[InvoiceData],
    validation: ValidationResult,
    decision: ShippingDecision,
) -> str:
    try:
        import boto3  # type: ignore
    except ImportError as exc:
        raise RuntimeError("AI assist requires boto3. Install it with: pip install boto3") from exc

    requested_model_id = os.getenv("BEDROCK_MODEL_ID", "").strip()
    region = os.getenv("AWS_REGION", os.getenv("AWS_DEFAULT_REGION", "us-east-1"))

    prompt_payload = {
        "invoices": [i.to_dict() for i in invoices],
        "validation": {
            "errors": validation.errors,
            "warnings": validation.warnings,
        },
        "decision": decision.to_dict(),
    }

    prompt = (
        "You are an operations assistant for shipping. "
        "Given this shipping decision payload, provide:\n"
        "1) A brief confidence statement.\n"
        "2) Any risks or assumptions.\n"
        "3) A recommended next action.\n"
        "Keep the response under 120 words.\n\n"
        f"Payload:\n{json.dumps(prompt_payload, indent=2)}"
    )

    client = boto3.client("bedrock-runtime", region_name=region)

    def _invoke_anthropic(model_id: str) -> str:
        body = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 260,
            "temperature": 0.2,
            "messages": [
                {
                    "role": "user",
                    "content": [{"type": "text", "text": prompt}],
                }
            ],
        }
        response = client.invoke_model(modelId=model_id, body=json.dumps(body))
        raw = response["body"].read().decode("utf-8")
        payload = json.loads(raw)
        content = payload.get("content", [])
        text_parts = [part.get("text", "") for part in content if isinstance(part, dict)]
        return "\n".join(p.strip() for p in text_parts if p.strip()).strip()

    def _invoke_nova(model_id: str) -> str:
        body = {
            "messages": [{"role": "user", "content": [{"text": prompt}]}],
            "inferenceConfig": {
                "maxTokens": 260,
                "temperature": 0.2,
            },
        }
        response = client.invoke_model(modelId=model_id, body=json.dumps(body))
        raw = response["body"].read().decode("utf-8")
        payload = json.loads(raw)

        output = payload.get("output", {})
        message = output.get("message", {}) if isinstance(output, dict) else {}
        content = message.get("content", []) if isinstance(message, dict) else []
        text_parts: list[str] = []
        for part in content:
            if not isinstance(part, dict):
                continue
            text = part.get("text")
            if isinstance(text, str):
                text_parts.append(text)
        return "\n".join(p.strip() for p in text_parts if p.strip()).strip()

    models_to_try = [requested_model_id] if requested_model_id else DEFAULT_ACTIVE_MODELS
    errors: list[str] = []

    for model_id in models_to_try:
        if not model_id:
            continue
        try:
            if model_id.startswith("amazon.nova"):
                insight = _invoke_nova(model_id)
            else:
                insight = _invoke_anthropic(model_id)

            if insight:
                return insight
            errors.append(f"{model_id}: returned empty output")
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{model_id}: {exc}")

    raise RuntimeError(
        "Unable to generate AI assist from Bedrock. "
        "Set BEDROCK_MODEL_ID to a model enabled in your account and region. "
        f"Tried: {', '.join(models_to_try)}. "
        f"Errors: {' | '.join(errors)}"
    )
