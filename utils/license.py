"""Email-based license system for StreamBridge with Supabase backend.

Each license is tied to an email. Only 1 machine can be active at a time.
Flow: user enters email → receives code via email → enters code → activated.
Legacy HMAC-based licenses (username without @) are still supported.
"""

import base64
import hashlib
import hmac
import json
import logging
import os
import platform
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request

from models.config import APP_DATA_DIR

logger = logging.getLogger(__name__)

LICENSE_FILE = os.path.join(APP_DATA_DIR, "license.json")


def _deobfuscate(encoded: str, key: int = 0x5A) -> str:
    raw = base64.b64decode(encoded)
    return bytes(b ^ key for b in raw).decode()


# Legacy HMAC secret (kept for backward compat with old licenses)
_SECRET = _deobfuscate("CS4oPzs3GCgzPj0/d2hqaGx3CDs+MzUbLy41NzsuMzU0").encode()
_SUPABASE_URL = _deobfuscate("Mi4uKilgdXUoOTc+LC85Ii4qLDc2PDQqMjkwNHQpLyo7ODspP3Q5NQ==")
_SUPABASE_KEY = _deobfuscate("KTgFKi84NjMpMjs4Nj8FIiMUbw8rOQAdOC07HS4zbRRqDWlvCwVvIAtqag4XLA==")


# ---------------------------------------------------------------------------
# Supabase helpers
# ---------------------------------------------------------------------------

def _supabase_headers() -> dict:
    return {
        "apikey": _SUPABASE_KEY,
        "Authorization": f"Bearer {_SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }


def _supabase_request(method: str, endpoint: str, data: dict = None) -> dict | list | None:
    """Make a request to Supabase REST API."""
    url = f"{_SUPABASE_URL}/rest/v1/{endpoint}"
    body = json.dumps(data).encode() if data else None
    req = urllib.request.Request(url, data=body, headers=_supabase_headers(), method=method)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode())
    except (urllib.error.URLError, json.JSONDecodeError, OSError) as e:
        logger.warning("Supabase request failed: %s", e)
        return None


def _supabase_function_call(function_name: str, data: dict) -> tuple[dict | None, str]:
    """Call a Supabase Edge Function. Returns (response_dict, error_string)."""
    url = f"{_SUPABASE_URL}/functions/v1/{function_name}"
    body = json.dumps(data).encode()
    headers = {
        "apikey": _SUPABASE_KEY,
        "Authorization": f"Bearer {_SUPABASE_KEY}",
        "Content-Type": "application/json",
    }
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read().decode())
            if result.get("success"):
                return result, ""
            return None, result.get("error", "Unknown server error")
    except urllib.error.HTTPError as e:
        try:
            err_body = json.loads(e.read().decode())
            return None, err_body.get("error", f"Server error ({e.code})")
        except Exception:
            return None, f"Server error ({e.code})"
    except (urllib.error.URLError, OSError) as e:
        logger.warning("Edge function call failed: %s", e)
        return None, "Could not connect to server. Check your internet."
    except json.JSONDecodeError:
        return None, "Invalid server response"


# ---------------------------------------------------------------------------
# Machine ID
# ---------------------------------------------------------------------------

def get_machine_id() -> str:
    """Generate a unique machine fingerprint."""
    parts = []
    parts.append(platform.node())

    if sys.platform == "win32":
        try:
            result = subprocess.run(
                ["wmic", "diskdrive", "get", "SerialNumber"],
                capture_output=True, timeout=5,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            serial = result.stdout.decode("utf-8", errors="replace").strip()
            lines = [l.strip() for l in serial.splitlines() if l.strip() and l.strip() != "SerialNumber"]
            if lines:
                parts.append(lines[0])
        except Exception:
            pass

        try:
            result = subprocess.run(
                ["wmic", "cpu", "get", "ProcessorId"],
                capture_output=True, timeout=5,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            cpu = result.stdout.decode("utf-8", errors="replace").strip()
            lines = [l.strip() for l in cpu.splitlines() if l.strip() and l.strip() != "ProcessorId"]
            if lines:
                parts.append(lines[0])
        except Exception:
            pass

    if sys.platform == "darwin":
        try:
            result = subprocess.run(
                ["system_profiler", "SPHardwareDataType"],
                capture_output=True, timeout=5,
            )
            for line in result.stdout.decode().splitlines():
                if "Hardware UUID" in line:
                    parts.append(line.split(":")[-1].strip())
                    break
        except Exception:
            pass

    raw = "|".join(parts)
    full_hash = hashlib.sha256(raw.encode()).hexdigest()
    short = full_hash[:12].upper()
    return f"{short[:4]}-{short[4:8]}-{short[8:12]}"


# ---------------------------------------------------------------------------
# Legacy HMAC functions (for old username-based licenses without @)
# ---------------------------------------------------------------------------

def _legacy_generate_code(username: str) -> str:
    """Generate an activation code using HMAC (legacy)."""
    clean_name = username.strip().lower()
    code_hash = hmac.new(_SECRET, clean_name.encode(), hashlib.sha256).hexdigest()
    short = code_hash[:12].upper()
    return f"{short[:4]}-{short[4:8]}-{short[8:12]}"


def _legacy_verify(username: str, activation_code: str) -> bool:
    """Verify HMAC-based activation code (legacy)."""
    expected = _legacy_generate_code(username)
    return activation_code.strip().upper() == expected


def _is_legacy_license(username: str) -> bool:
    """Check if this is a legacy license (username without @)."""
    return "@" not in username


# ---------------------------------------------------------------------------
# New email-based activation (via Edge Functions)
# ---------------------------------------------------------------------------

def request_activation_code(email: str) -> tuple[bool, str, str]:
    """Request an activation code for the given email.

    Returns (success, error_message, code).
    The code is returned directly from the server.
    """
    clean_email = email.strip().lower()
    if not clean_email or "@" not in clean_email:
        return False, "Enter a valid email address", ""

    result, error = _supabase_function_call("send-code", {"email": clean_email})
    if error:
        return False, error, ""
    code = result.get("code", "") if result else ""
    return True, "", code


def verify_activation_code(email: str, code: str) -> tuple[bool, str]:
    """Verify activation code and register this machine.

    Returns (success, error_message).
    """
    clean_email = email.strip().lower()
    clean_code = code.strip().upper()

    if not clean_email or "@" not in clean_email:
        return False, "Enter a valid email address"
    if not clean_code:
        return False, "Enter the activation code"

    machine_id = get_machine_id()
    machine_name = platform.node()

    _, error = _supabase_function_call("verify-code", {
        "email": clean_email,
        "code": clean_code,
        "machine_id": machine_id,
        "machine_name": machine_name,
    })
    if error:
        return False, error

    # Save locally
    data = {
        "username": clean_email,
        "activation_code": clean_code,
    }
    os.makedirs(os.path.dirname(LICENSE_FILE), exist_ok=True)
    with open(LICENSE_FILE, "w") as f:
        json.dump(data, f, indent=2)

    return True, ""


# ---------------------------------------------------------------------------
# Activation check (supports both legacy and email-based)
# ---------------------------------------------------------------------------

def _check_machine_in_supabase(username: str, machine_id: str) -> str | None:
    """Check if this machine is the active one. Returns None if OK, or error message."""
    field = "email" if "@" in username else "username"
    query_val = urllib.parse.quote(username.strip().lower())
    result = _supabase_request(
        "GET",
        f"licenses?{field}=eq.{query_val}&select=machine_id,machine_name,active"
    )

    if result is None:
        return None  # Network error — allow offline use

    if len(result) == 0:
        return "License not found in server"

    if not result[0].get("active", True):
        return "License has been deactivated. Contact support."

    stored_machine_id = result[0].get("machine_id", "")
    stored_machine_name = result[0].get("machine_name", "")

    if stored_machine_id and stored_machine_id != machine_id:
        return (
            f"License is active on another computer: {stored_machine_name}\n"
            f"Deactivate it there first, or re-activate here."
        )

    # Update last_seen
    _supabase_request(
        "PATCH",
        f"licenses?{field}=eq.{query_val}",
        {"last_seen": "now()"}
    )
    return None


def is_activated() -> bool:
    """Check if this installation is activated (local + Supabase)."""
    if not os.path.exists(LICENSE_FILE):
        return False
    try:
        with open(LICENSE_FILE, "r") as f:
            data = json.load(f)
        stored_code = data.get("activation_code", "")
        username = data.get("username", "")
        if not username:
            return False

        # Legacy license: verify HMAC locally
        if _is_legacy_license(username):
            if not _legacy_verify(username, stored_code):
                return False

        # Email-based license: no local HMAC check needed
        # (code was verified server-side during activation)

        # Check with Supabase if this machine is still the active one
        machine_id = get_machine_id()
        error = _check_machine_in_supabase(username, machine_id)
        if error:
            logger.warning("License check failed: %s", error)
            return False

        return True
    except (json.JSONDecodeError, OSError):
        return False


def get_license_error() -> str:
    """Return the reason activation failed, or empty string if OK."""
    if not os.path.exists(LICENSE_FILE):
        return ""
    try:
        with open(LICENSE_FILE, "r") as f:
            data = json.load(f)
        username = data.get("username", "")
        if not username:
            return ""
        machine_id = get_machine_id()
        error = _check_machine_in_supabase(username, machine_id)
        return error or ""
    except (json.JSONDecodeError, OSError):
        return ""


def get_licensed_username() -> str:
    """Return the licensed username/email, or empty string if not activated."""
    if not os.path.exists(LICENSE_FILE):
        return ""
    try:
        with open(LICENSE_FILE, "r") as f:
            data = json.load(f)
        username = data.get("username", "")
        if not username:
            return ""
        # Legacy: verify HMAC
        if _is_legacy_license(username):
            stored_code = data.get("activation_code", "")
            if not _legacy_verify(username, stored_code):
                return ""
        return username
    except (json.JSONDecodeError, OSError):
        return ""


# Legacy save_activation (kept for generate_license.py admin tool)
def save_activation(username: str, activation_code: str) -> tuple[bool, str]:
    """Save activation code for a username (legacy HMAC flow).

    Returns (success, error_message).
    """
    if not username.strip():
        return False, "Enter your name"
    if not _legacy_verify(username, activation_code):
        return False, "Invalid activation code for this username"

    machine_id = get_machine_id()
    machine_name = platform.node()

    # Register in Supabase
    query_val = urllib.parse.quote(username.strip().lower())
    result = _supabase_request(
        "GET",
        f"licenses?username=eq.{query_val}&select=*"
    )

    if result and len(result) > 0:
        if not result[0].get("active", True):
            return False, "License has been deactivated."
        _supabase_request(
            "PATCH",
            f"licenses?username=eq.{query_val}",
            {"machine_id": machine_id, "machine_name": machine_name, "last_seen": "now()"}
        )
    else:
        resp = _supabase_request(
            "POST", "licenses",
            {
                "username": username.strip().lower(),
                "activation_code": activation_code.strip().upper(),
                "machine_id": machine_id,
                "machine_name": machine_name,
            }
        )
        if resp is None:
            return False, "Could not connect to license server."

    # Save locally
    data = {
        "username": username.strip(),
        "activation_code": activation_code.strip().upper(),
    }
    os.makedirs(os.path.dirname(LICENSE_FILE), exist_ok=True)
    with open(LICENSE_FILE, "w") as f:
        json.dump(data, f, indent=2)

    return True, ""


# Keep generate_activation_code accessible for admin tool
generate_activation_code = _legacy_generate_code


def check_for_update(current_version: str) -> dict | None:
    """Check Supabase for a newer version.

    Returns dict with {version, download_url, release_notes} or None.
    """
    result = _supabase_request(
        "GET",
        "app_versions?is_latest=eq.true&select=version,download_url,release_notes"
    )
    if not result or len(result) == 0:
        return None

    latest = result[0]
    if latest["version"] != current_version and latest.get("download_url"):
        return latest
    return None
