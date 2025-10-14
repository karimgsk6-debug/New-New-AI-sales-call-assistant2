# prompt_moderation.py
import re
import json
from datetime import datetime
from typing import Dict, Any, Optional

AUDIT_LOG = "prompt_audit_log.jsonl"

# --- CONFIG: Customize for your organisation ---
BLACKLIST_TERMS = [
    r"\boff-?label\b", r"\bunapproved\b", r"\bunauthoriz(?:ed|ed)\b",
    r"\bcure\b", r"\bmiracle\b", r"\bfree trial\b", r"\bdiscount\b",
    r"\bprice\b", r"\bcompare\b.*\bcompetitor\b", r"\bdosage\b", r"\bprescribe\b",
    # financial/commercial language to avoid promotional content
    r"\bbuy\b", r"\bdiscount\b", r"\bounce\b"
]

SENSITIVE_PATIENT_PATTERNS = [
    r"\bdiagnos(?:e|is|ing)\b", r"\bprescrib(?:e|ing|ed)\b",
    r"\bpatient\b", r"\bunder-?\d+\b", r"\bchild(?:ren)?\b", r"\bgender\b", r"\bage\b"
]

BYPASS_PATTERNS = [
    r"ignore (?:previous|earlier) instructions",
    r"disregard (?:rules|policy)",
    r"bypass (?:filter|moderation)",
    r"act as if you are"
]

# Approved templates / whitelisted starting phrases (encouraged)
ALLOWED_STARTS = [
    "Explain the approved indications for",
    "Summarise approved clinical evidence for",
    "List contraindications for",
    "Provide the approved dosing guidance for"
]

# Simple mapping to suggest rewrites for common blocked intents
REWRITE_TEMPLATES = {
    "age_question": "Provide approved age indications and age-based guidance for the product.",
    "off_label": "Provide only approved indications and evidence; do not include off-label uses.",
    "prescribe": "Provide high-level educational information; do not provide prescribing advice."
}

# --------------------------
# Helper utilities
# --------------------------
def _log_audit(entry: Dict[str, Any]):
    entry["timestamp"] = datetime.utcnow().isoformat()
    with open(AUDIT_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")

def _matches_any(patterns, text):
    for p in patterns:
        if re.search(p, text, flags=re.IGNORECASE):
            return True, p
    return False, None

# --------------------------
# External moderation placeholder
# --------------------------
def external_moderation_check(prompt: str, provider: Optional[str] = None) -> Dict[str, Any]:
    """
    Optional: Add real external moderation logic here.
    provider can be 'openai', 'groq', etc. For now this returns neutral.
    Return format:
    { "flagged": False, "reasons": [], "score": 0.0 }
    """
    # Implement actual call to moderation API if configured.
    # Example (pseudo):
    # if provider == "openai":
    #     call openai.Moderation.create(...)
    # elif provider == "groq":
    #     call groq moderation endpoint...
    return {"flagged": False, "reasons": [], "score": 0.0}

# --------------------------
# Rewrite helpers
# --------------------------
def suggest_rewrite(prompt: str, tag: str) -> str:
    """Return a suggested compliant rewrite based on tag."""
    if tag == "age_question":
        return REWRITE_TEMPLATES["age_question"]
    if tag == "off_label":
        return REWRITE_TEMPLATES["off_label"]
    if tag == "prescribe":
        return REWRITE_TEMPLATES["prescribe"]
    # generic fallback: force an approved-scope informational prompt
    return "Provide a high-level, approved-scope summary relevant to the product and indications."

# --------------------------
# Main moderation function
# --------------------------
def moderate_prompt(prompt: str, user_id: Optional[str] = None, external_provider: Optional[str] = None) -> Dict[str, Any]:
    """
    Returns:
      {
        "action": "allow" | "block" | "rewrite" | "review",
        "reason": "short explanation",
        "rewrite": "<suggested prompt if action=='rewrite' else None>",
        "details": { ... }  # debug info for audit
      }
    """
    original = prompt or ""
    prompt_text = original.strip()

    # initial normalization
    prompt_norm = re.sub(r'\s+', ' ', prompt_text)

    # Layer 1: fast deterministic filters
    matched_black, black_pat = _matches_any(BLACKLIST_TERMS, prompt_norm)
    if matched_black:
        reason = f"Blacklisted term matched: {black_pat}"
        suggestion = suggest_rewrite(prompt_norm, "off_label")
        _log_audit({
            "prompt": original,
            "action": "block",
            "reason": reason,
            "rule": black_pat,
            "user_id": user_id
        })
        return {"action": "block", "reason": reason, "rewrite": suggestion, "details": {"matched_pattern": black_pat}}

    # detect bypass attempts
    matched_bypass, bypass_pat = _matches_any(BYPASS_PATTERNS, prompt_norm)
    if matched_bypass:
        reason = f"Bypass attempt detected: {bypass_pat}"
        _log_audit({
            "prompt": original,
            "action": "block",
            "reason": reason,
            "user_id": user_id
        })
        return {"action": "block", "reason": reason, "rewrite": None, "details": {"matched_pattern": bypass_pat}}

    # Layer 2: sensitive patient-specific checks
    matched_sensitive, sens_pat = _matches_any(SENSITIVE_PATIENT_PATTERNS, prompt_norm)
    if matched_sensitive:
        # For patient-specific clinical advice, require human review or rewrite
        reason = f"Sensitive clinical intent detected: {sens_pat}"
        suggestion = suggest_rewrite(prompt_norm, "prescribe")
        _log_audit({
            "prompt": original,
            "action": "review",
            "reason": reason,
            "rule": sens_pat,
            "user_id": user_id
        })
        return {"action": "review", "reason": reason, "rewrite": suggestion, "details": {"matched_pattern": sens_pat}}

    # Layer 2b: disallow direct competitor comparison or pricing negotiation
    comp_match = re.search(r'\b(compare|vs\.|versus)\b.*\b(competitor|brand name|price)\b', prompt_norm, flags=re.IGNORECASE)
    if comp_match:
        reason = "Competitive comparison or pricing request detected"
        _log_audit({"prompt": original, "action": "block", "reason": reason, "user_id": user_id})
        return {"action": "block", "reason": reason, "rewrite": None, "details": {"match": comp_match.group(0)}}

    # Layer 3: optional external moderation
    if external_provider:
        ext = external_moderation_check(prompt_norm, provider=external_provider)
        if ext.get("flagged"):
            reason = f"External moderation flagged: {ext.get('reasons')}"
            _log_audit({"prompt": original, "action": "block", "reason": reason, "details": ext, "user_id": user_id})
            return {"action": "block", "reason": reason, "rewrite": None, "details": ext}

    # Template / format checks (encourage approved starts)
    starts_ok = any(prompt_norm.lower().startswith(s.lower()) for s in ALLOWED_STARTS)
    if not starts_ok:
        # Allow but suggest rewrite if it's not starting with an allowed template AND it contains some risky words
        # We don't block here, but we can suggest improved prompt to the user
        suggestion = None
        # if prompt contains "how" + brand: suggest using an approved phrasing
        if re.search(r'\bhow\b.*\b(' + '|'.join([re.escape(k) for k in brand_terms()]) + r')\b', prompt_norm, flags=re.IGNORECASE):
            suggestion = "Please rephrase using approved template: 'Explain the approved indications for <product>.'"
        _log_audit({"prompt": original, "action": "allow_with_suggestion" if suggestion else "allow", "reason": "Template suggestion", "user_id": user_id})
        return {"action": "allow", "reason": "Prompt passed checks", "rewrite": suggestion, "details": {}}

    # default: allow
    _log_audit({"prompt": original, "action": "allow", "reason": "No issues detected", "user_id": user_id})
    return {"action": "allow", "reason": "No issues detected", "rewrite": None, "details": {}}

# --------------------------
# Small helper to derive product/brand terms if needed
# --------------------------
def brand_terms():
    # This would normally be dynamic: pull from your brand_data keys or product list
    return ["shingrix", "jemperli", "gsk"]

# --------------------------
# Stats loader (for dashboards)
# --------------------------
def load_moderation_stats(limit: int = 1000):
    """Return last N audit lines as list of dicts."""
    entries = []
    try:
        with open(AUDIT_LOG, "r", encoding="utf-8") as f:
            for i, line in enumerate(f):
                if i >= limit:
                    break
                try:
                    entries.append(json.loads(line))
                except:
                    pass
    except FileNotFoundError:
        pass
    return entries
