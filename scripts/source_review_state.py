from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_STATE_PATH = ROOT / "data" / "source_review_states.json"

ALLOWED_REVIEW_STATES = {"open", "reviewed", "needs_reextract", "deferred"}


def source_review_item_id(item: dict[str, Any]) -> str:
    parts = [
        str(item.get("stem") or ""),
        str(item.get("source_url") or ""),
        str(item.get("admission_year") or ""),
        str(item.get("status") or ""),
        str(item.get("new_sha256") or ""),
    ]
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()[:20]


def load_source_review_states(path: Path | None = None) -> dict[str, Any]:
    state_path = path or DEFAULT_STATE_PATH
    if not state_path.exists():
        return {}
    payload = json.loads(state_path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def update_source_review_state(
    item_id: str,
    review_status: str,
    *,
    note: str = "",
    path: Path | None = None,
    now: str | None = None,
) -> dict[str, Any]:
    if review_status not in ALLOWED_REVIEW_STATES:
        raise ValueError(f"review_status must be one of {sorted(ALLOWED_REVIEW_STATES)}")
    state_path = path or DEFAULT_STATE_PATH
    states = load_source_review_states(state_path)
    entry = {
        "item_id": item_id,
        "review_status": review_status,
        "note": str(note or "").strip(),
        "updated_at": now or _now_iso(),
    }
    states[item_id] = entry
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps(states, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    return entry


def accept_source_review_receipt(
    item: dict[str, Any],
    *,
    root: Path = ROOT,
    now: str | None = None,
) -> dict[str, Any]:
    stem = str(item.get("stem") or "").strip()
    new_sha256 = str(item.get("new_sha256") or "").strip()
    if not stem:
        raise ValueError("source review item has no stem")
    if not new_sha256:
        raise ValueError("source review item has no new source hash")

    receipt_path = root / "quality_sources" / f"{stem}.source.json"
    try:
        payload = json.loads(receipt_path.read_text(encoding="utf-8")) if receipt_path.exists() else {}
    except Exception:
        payload = {}
    if not isinstance(payload, dict):
        payload = {}

    old_sha256 = str(payload.get("sha256") or item.get("old_sha256") or "").strip()
    accepted_at = now or _now_iso()
    payload["sha256"] = new_sha256
    payload["checked_at"] = str(item.get("checked_at") or accepted_at)
    payload["source_url"] = str(item.get("final_url") or item.get("source_url") or payload.get("source_url") or "").strip()
    payload["last_accepted_old_sha256"] = old_sha256
    payload["accepted_at"] = accepted_at
    payload["accepted_review_status"] = str(item.get("status") or "")
    payload["accepted_review_item_id"] = source_review_item_id(item)

    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    receipt_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    return {
        "stem": stem,
        "old_sha256": old_sha256,
        "sha256": new_sha256,
        "accepted_at": accepted_at,
        "receipt_path": str(receipt_path),
        "confirmed_records_unchanged": True,
    }
