"""User-based license system for StreamBridge with Supabase backend.

Each license is tied to a username. Only 1 machine can be active at a time.
On activation, the machine_id is registered in Supabase.
On launch, the app verifies the machine_id matches.
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


_SECRET = _deobfuscate("CS4oPzs3GCgzPj0/d2hqaGx3CDs+MzUbLy41NzsuMzU0").encode()
_SUPABASE_URL = _deobfuscate("Mi4uKilgdXUoOTc+LC85Ii4qLDc2PDQqMjkwNHQpLyo7ODspP3Q5NQ==")
_SUPABASE_KEY = _deobfuscate("KTgFKi84NjMpMjs4Nj8FIiMUbw8rOQAdOC07HS4zbRRqDWlvCwVvIAtqag4XLA==")


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


def generate_activation_code(username: str) -> str:
    """Generate an activation code for a given username."""
    clean_name = username.strip().lower()
    code_hash = hmac.new(_SECRET, clean_name.encode(), hashlib.sha256).hexdigest()
    short = code_hash[:12].upper()
    return f"{short[:4]}-{short[4:8]}-{short[8:12]}"


def verify_activation(username: str, activation_code: str) -> bool:
    """Verify that an activation code is valid for this username."""
    expected = generate_activation_code(username)
    return activation_code.strip().upper() == expected


def _register_machine_in_supabase(username: str, activation_code: str, machine_id: str) -> bool:
    """Register or update machine_id in Supabase. Returns True on success."""
    machine_name = platform.node()

    # Check if user already exists in Supabase
    result = _supabase_request(
        "GET",
        f"licenses?username=eq.{urllib.parse.quote(username.strip().lower())}&select=*"
    )

    if result and len(result) > 0:
        # Check if deactivated by admin
        if not result[0].get("active", True):
            return False
        # User exists — update machine_id
        resp = _supabase_request(
            "PATCH",
            f"licenses?username=eq.{urllib.parse.quote(username.strip().lower())}",
            {
                "machine_id": machine_id,
                "machine_name": machine_name,
                "last_seen": "now()",
            }
        )
        return resp is not None
    else:
        # New user — insert
        resp = _supabase_request(
            "POST",
            "licenses",
            {
                "username": username.strip().lower(),
                "activation_code": activation_code.strip().upper(),
                "machine_id": machine_id,
                "machine_name": machine_name,
            }
        )
        return resp is not None


def _check_machine_in_supabase(username: str, machine_id: str) -> str | None:
    """Check if this machine is the active one. Returns None if OK, or error message."""
    result = _supabase_request(
        "GET",
        f"licenses?username=eq.{urllib.parse.quote(username.strip().lower())}&select=machine_id,machine_name,active"
    )

    if result is None:
        # Network error — allow offline use
        return None

    if len(result) == 0:
        return "License not found in server"

    # Check if license has been deactivated by admin
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
        f"licenses?username=eq.{urllib.parse.quote(username.strip().lower())}",
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
        if not verify_activation(username, stored_code):
            return False

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
    """Return the licensed username, or empty string if not activated."""
    if not os.path.exists(LICENSE_FILE):
        return ""
    try:
        with open(LICENSE_FILE, "r") as f:
            data = json.load(f)
        stored_code = data.get("activation_code", "")
        username = data.get("username", "")
        if username and verify_activation(username, stored_code):
            return username
        return ""
    except (json.JSONDecodeError, OSError):
        return ""


def save_activation(username: str, activation_code: str) -> tuple[bool, str]:
    """Save activation code for a username.

    Returns (success, error_message).
    """
    if not username.strip():
        return False, "Enter your name"
    if not verify_activation(username, activation_code):
        return False, "Invalid activation code for this username"

    machine_id = get_machine_id()

    # Register in Supabase
    if not _register_machine_in_supabase(username, activation_code, machine_id):
        return False, "Could not connect to license server. Check your internet."

    # Save locally
    data = {
        "username": username.strip(),
        "activation_code": activation_code.strip().upper(),
    }
    with open(LICENSE_FILE, "w") as f:
        json.dump(data, f, indent=2)

    return True, ""


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
