"""Adapters de webhook para providers de cobrança.

Os handlers validam assinatura no corpo bruto, gravam o event_id antes de
processar e aplicam transições idempotentes de entitlements. Checkout real
continua desligado até os segredos do provider serem configurados.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import time
from typing import Any

from . import billing


class WebhookVerificationError(RuntimeError):
    pass


class WebhookPayloadError(RuntimeError):
    pass


def _secret(name: str) -> str:
    return os.environ.get(name, "").strip()


def _hmac_hex(secret: str, message: bytes) -> str:
    return hmac.new(secret.encode("utf-8"), message, hashlib.sha256).hexdigest()


def verify_stripe_signature(payload: bytes, signature_header: str | None, secret: str | None = None, *, tolerance_seconds: int = 300) -> None:
    signing_secret = (secret or _secret("STRIPE_WEBHOOK_SECRET")).strip()
    if not signing_secret or not signature_header:
        raise WebhookVerificationError("Assinatura Stripe ausente ou não configurada.")
    pairs: dict[str, list[str]] = {}
    for item in signature_header.split(","):
        name, separator, value = item.partition("=")
        if separator:
            pairs.setdefault(name.strip(), []).append(value.strip())
    try:
        timestamp = int((pairs.get("t") or [""])[0])
    except ValueError as exc:
        raise WebhookVerificationError("Assinatura Stripe inválida.") from exc
    if abs(int(time.time()) - timestamp) > max(1, int(tolerance_seconds)):
        raise WebhookVerificationError("Assinatura Stripe expirada.")
    expected = _hmac_hex(signing_secret, f"{timestamp}.".encode("ascii") + payload)
    if not any(hmac.compare_digest(expected, candidate) for candidate in pairs.get("v1", [])):
        raise WebhookVerificationError("Assinatura Stripe inválida.")


def verify_mercado_pago_signature(
    payload: bytes,
    signature_header: str | None,
    request_id: str | None,
    data_id: str | None,
    secret: str | None = None,
    *,
    tolerance_seconds: int = 300,
) -> None:
    signing_secret = (secret or _secret("MERCADO_PAGO_WEBHOOK_SECRET") or _secret("MERCADOPAGO_WEBHOOK_SECRET")).strip()
    if not signing_secret or not signature_header:
        raise WebhookVerificationError("Assinatura Mercado Pago ausente ou não configurada.")
    values: dict[str, str] = {}
    for item in signature_header.split(","):
        name, separator, value = item.strip().partition("=")
        if separator:
            values[name.strip()] = value.strip()
    try:
        timestamp = int(values.get("ts", "0"))
    except ValueError as exc:
        raise WebhookVerificationError("Assinatura Mercado Pago inválida.") from exc
    if abs(int(time.time()) - timestamp) > max(1, int(tolerance_seconds)):
        raise WebhookVerificationError("Assinatura Mercado Pago expirada.")
    manifest = f"id:{data_id or ''};request-id:{request_id or ''};ts:{timestamp};"
    expected = _hmac_hex(signing_secret, manifest.encode("utf-8"))
    if not hmac.compare_digest(expected, values.get("v1", "")):
        raise WebhookVerificationError("Assinatura Mercado Pago inválida.")


def _json_payload(raw: bytes) -> dict[str, Any]:
    try:
        parsed = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise WebhookPayloadError("Payload de webhook inválido.") from exc
    if not isinstance(parsed, dict):
        raise WebhookPayloadError("Payload de webhook inválido.")
    return parsed


def _nested(value: Any, *keys: str) -> Any:
    current = value
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def _account_and_plan(obj: dict[str, Any]) -> tuple[str | None, str]:
    metadata = obj.get("metadata") if isinstance(obj.get("metadata"), dict) else {}
    account_id = metadata.get("account_id") or obj.get("client_reference_id") or obj.get("external_reference")
    plan_code = str(metadata.get("plan_code") or metadata.get("plan") or "starter").lower()
    return (str(account_id) if account_id else None), plan_code


def process_stripe(raw: bytes, *, signature_header: str | None) -> dict[str, Any]:
    verify_stripe_signature(raw, signature_header)
    event = _json_payload(raw)
    event_id = str(event.get("id") or "")
    event_type = str(event.get("type") or "")
    if not event_id or not event_type:
        raise WebhookPayloadError("Evento Stripe sem id ou tipo.")
    obj = _nested(event, "data", "object")
    if not isinstance(obj, dict):
        obj = {}
    account_id, plan_code = _account_and_plan(obj)
    if not account_id and isinstance(obj.get("subscription_details"), dict):
        account_id, plan_code = _account_and_plan(obj["subscription_details"])
    payload_hash = hashlib.sha256(raw).hexdigest()
    first_seen = billing.record_webhook_event("stripe", event_id, event_type, account_id=account_id, payload_hash=payload_hash)
    if not first_seen:
        return {"accepted": True, "duplicate": True, "event_id": event_id}

    status = "active"
    if event_type in {"customer.subscription.deleted", "customer.subscription.paused"}:
        status = "canceled" if event_type.endswith("deleted") else "paused"
    elif event_type == "invoice.payment_failed":
        status = "past_due"
    elif event_type in {"customer.subscription.updated", "customer.subscription.created"}:
        status = str(obj.get("status") or "active").lower()
    elif event_type == "invoice.paid":
        status = "active"
    elif event_type == "checkout.session.completed":
        status = "active"

    if account_id:
        if event_type.startswith("customer.subscription") or event_type in {"checkout.session.completed", "invoice.paid", "invoice.payment_failed"}:
            customer_id = obj.get("customer")
            subscription_id = obj.get("subscription") or obj.get("id") if event_type.startswith("customer.subscription") else obj.get("subscription")
            period_start = obj.get("current_period_start")
            period_end = obj.get("current_period_end")
            billing.set_subscription(
                account_id,
                plan_code=plan_code if plan_code in billing.PLAN_CATALOG else "starter",
                status=status,
                provider="stripe",
                provider_customer_id=str(customer_id) if customer_id else None,
                provider_subscription_id=str(subscription_id) if subscription_id else None,
                metadata={"stripe_event_id": event_id, "event_type": event_type},
            )
    billing.mark_webhook_processed("stripe", event_id)
    return {"accepted": True, "duplicate": False, "event_id": event_id, "event_type": event_type, "account_mapped": bool(account_id)}


def process_mercado_pago(raw: bytes, *, signature_header: str | None, request_id: str | None, data_id: str | None) -> dict[str, Any]:
    verify_mercado_pago_signature(raw, signature_header, request_id, data_id)
    event = _json_payload(raw)
    event_id = str(event.get("id") or data_id or "")
    event_type = str(event.get("type") or event.get("action") or "")
    if not event_id or not event_type:
        raise WebhookPayloadError("Evento Mercado Pago sem id ou tipo.")
    data = event.get("data") if isinstance(event.get("data"), dict) else {}
    account_id = data.get("account_id") or event.get("external_reference")
    payload_hash = hashlib.sha256(raw).hexdigest()
    first_seen = billing.record_webhook_event("mercado_pago", event_id, event_type, account_id=str(account_id) if account_id else None, payload_hash=payload_hash)
    if not first_seen:
        return {"accepted": True, "duplicate": True, "event_id": event_id}
    billing.mark_webhook_processed("mercado_pago", event_id, status="received_unmapped" if not account_id else "processed")
    return {"accepted": True, "duplicate": False, "event_id": event_id, "event_type": event_type, "account_mapped": bool(account_id)}
