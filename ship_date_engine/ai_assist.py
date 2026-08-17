from __future__ import annotations

import json
import os

from .models import InvoiceData, ShippingDecision, ValidationResult


# ── Model defaults ────────────────────────────────────────────────────────────

DEFAULT_ANTHROPIC_MODEL = "claude-haiku-4-5-20251001"

DEFAULT_BEDROCK_MODELS = [
    "amazon.nova-lite-v1:0",
    "anthropic.claude-3-5-haiku-20241022-v1:0",
    "anthropic.claude-3-haiku-20240307-v1:0",
]


# ── Shared prompt builder ─────────────────────────────────────────────────────

def _build_prompt(
    invoices: list[InvoiceData],
    validation: ValidationResult,
    decision: ShippingDecision,
) -> str:
    payload = {
        "invoices": [i.to_dict() for i in invoices],
        "validation": {
            "errors": validation.errors,
            "warnings": validation.warnings,
        },
        "decision": decision.to_dict(),
    }
    return (
        "You are an operations assistant for shipping. "
        "Given this shipping decision payload, provide:\n"
        "1) A brief confidence statement.\n"
        "2) Any risks or assumptions.\n"
        "3) A recommended next action.\n"
        "Keep the response under 120 words.\n\n"
        f"Payload:\n{json.dumps(payload, indent=2)}"
    )


# ── Direct Anthropic API backend ──────────────────────────────────────────────

def generate_anthropic_insight(
    invoices: list[InvoiceData],
    validation: ValidationResult,
    decision: ShippingDecision,
) -> str:
    """Generate insight using the direct Anthropic API.

    Requires:
    - ``pip install anthropic``
    - ``ANTHROPIC_API_KEY`` environment variable

    Override the model with ``ANTHROPIC_MODEL_ID``.
    """
    try:
        import anthropic  # type: ignore
    except ImportError as exc:
        raise RuntimeError(
            "Direct Anthropic API requires the 'anthropic' package. "
            "Install it with: pip install anthropic"
        ) from exc

    api_key = os.getenv("ANTHROPIC_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError(
            "ANTHROPIC_API_KEY environment variable must be set to use the direct Anthropic API."
        )

    model_id = os.getenv("ANTHROPIC_MODEL_ID", DEFAULT_ANTHROPIC_MODEL)
    prompt = _build_prompt(invoices, validation, decision)

    client = anthropic.Anthropic(api_key=api_key)
    message = client.messages.create(
        model=model_id,
        max_tokens=260,
        messages=[{"role": "user", "content": prompt}],
    )

    if not message.content:
        raise RuntimeError("Anthropic API returned an empty response.")

    return message.content[0].text.strip()


# ── AWS Bedrock backend ───────────────────────────────────────────────────────

def generate_bedrock_insight(
    invoices: list[InvoiceData],
    validation: ValidationResult,
    decision: ShippingDecision,
) -> str:
    """Generate insight via AWS Bedrock.

    Requires:
    - ``pip install boto3``
    - AWS credentials in environment (``AWS_ACCESS_KEY_ID``, ``AWS_SECRET_ACCESS_KEY``, etc.)

    Override the model with ``BEDROCK_MODEL_ID``.
    Override the region with ``AWS_REGION`` or ``AWS_DEFAULT_REGION``.
    """
    try:
        import boto3  # type: ignore
    except ImportError as exc:
        raise RuntimeError(
            "AWS Bedrock AI assist requires boto3. Install it with: pip install boto3"
        ) from exc

    requested_model_id = os.getenv("BEDROCK_MODEL_ID", "").strip()
    region = os.getenv("AWS_REGION", os.getenv("AWS_DEFAULT_REGION", "us-east-1"))
    prompt = _build_prompt(invoices, validation, decision)

    client = boto3.client("bedrock-runtime", region_name=region)

    def _invoke_anthropic(model_id: str) -> str:
        body = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 260,
            "temperature": 0.2,
            "messages": [{"role": "user", "content": [{"type": "text", "text": prompt}]}],
        }
        response = client.invoke_model(modelId=model_id, body=json.dumps(body))
        raw = response["body"].read().decode("utf-8")
        payload = json.loads(raw)
        content = payload.get("content", [])
        parts = [p.get("text", "") for p in content if isinstance(p, dict)]
        return "\n".join(p.strip() for p in parts if p.strip()).strip()

    def _invoke_nova(model_id: str) -> str:
        body = {
            "messages": [{"role": "user", "content": [{"text": prompt}]}],
            "inferenceConfig": {"maxTokens": 260, "temperature": 0.2},
        }
        response = client.invoke_model(modelId=model_id, body=json.dumps(body))
        raw = response["body"].read().decode("utf-8")
        payload = json.loads(raw)
        output = payload.get("output", {})
        message = output.get("message", {}) if isinstance(output, dict) else {}
        content = message.get("content", []) if isinstance(message, dict) else []
        parts = [p.get("text", "") for p in content if isinstance(p, dict)]
        return "\n".join(p.strip() for p in parts if p.strip()).strip()

    models_to_try = [requested_model_id] if requested_model_id else DEFAULT_BEDROCK_MODELS
    errors: list[str] = []

    for model_id in models_to_try:
        if not model_id:
            continue
        try:
            insight = _invoke_nova(model_id) if model_id.startswith("amazon.nova") else _invoke_anthropic(model_id)
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


# ── Auto-selecting entry point ────────────────────────────────────────────────

def generate_insight(
    invoices: list[InvoiceData],
    validation: ValidationResult,
    decision: ShippingDecision,
) -> str:
    """Generate an AI insight, choosing the backend automatically.

    Selection order:
    1. Direct Anthropic API — if ``ANTHROPIC_API_KEY`` is set.
    2. AWS Bedrock — uses ``BEDROCK_MODEL_ID`` or the built-in fallback list.
    """
    if os.getenv("ANTHROPIC_API_KEY", "").strip():
        return generate_anthropic_insight(invoices, validation, decision)
    return generate_bedrock_insight(invoices, validation, decision)
