"""StreamBridge admin tool — manage authorized users.

Usage:
    python admin_users.py add <email>              Pre-authorize a new paid user
    python admin_users.py remove <email>           Remove authorization (soft delete)
    python admin_users.py deactivate <email>       Set active=false (revoke license)
    python admin_users.py activate <email>         Set active=true (re-enable)
    python admin_users.py reset-machine <email>    Clear machine_id so user can re-activate on new PC
    python admin_users.py list                     Show all users

Requires SUPABASE_SERVICE_ROLE_KEY in .env file.
"""

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

SUPABASE_URL = "https://rcmdvucxtpvmlfnphcjn.supabase.co"
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))


def load_env() -> None:
    env_path = os.path.join(PROJECT_DIR, ".env")
    if not os.path.isfile(env_path):
        return
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                k, _, v = line.partition("=")
                os.environ.setdefault(k.strip(), v.strip())


def _headers() -> dict:
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
    if not key:
        print("ERROR: SUPABASE_SERVICE_ROLE_KEY not set in .env")
        sys.exit(1)
    return {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }


def _request(method: str, path: str, body: dict | None = None) -> list:
    url = f"{SUPABASE_URL}/rest/v1/{path}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, headers=_headers(), method=method)
    try:
        resp = urllib.request.urlopen(req, timeout=10).read()
        return json.loads(resp) if resp else []
    except urllib.error.HTTPError as e:
        print(f"HTTP {e.code}: {e.read().decode()}")
        sys.exit(1)


def cmd_add(email: str) -> None:
    email = email.strip().lower()
    # Check if exists
    existing = _request("GET", f"licenses?email=eq.{urllib.parse.quote(email)}&select=*")
    if existing:
        # Just authorize the existing row
        _request("PATCH", f"licenses?email=eq.{urllib.parse.quote(email)}",
                 {"authorized": True, "active": True})
        print(f"OK: {email} is now authorized (was already in DB)")
    else:
        _request("POST", "licenses", {
            "email": email,
            "username": email,
            "authorized": True,
            "active": True,
        })
        print(f"OK: {email} added and authorized")


def cmd_remove(email: str) -> None:
    email = email.strip().lower()
    _request("PATCH", f"licenses?email=eq.{urllib.parse.quote(email)}",
             {"authorized": False})
    print(f"OK: {email} authorization removed")


def cmd_deactivate(email: str) -> None:
    email = email.strip().lower()
    _request("PATCH", f"licenses?email=eq.{urllib.parse.quote(email)}",
             {"active": False})
    print(f"OK: {email} deactivated")


def cmd_activate(email: str) -> None:
    email = email.strip().lower()
    _request("PATCH", f"licenses?email=eq.{urllib.parse.quote(email)}",
             {"active": True})
    print(f"OK: {email} activated")


def cmd_reset_machine(email: str) -> None:
    email = email.strip().lower()
    _request("PATCH", f"licenses?email=eq.{urllib.parse.quote(email)}",
             {"machine_id": None, "machine_name": None, "code_verified": False})
    print(f"OK: {email} machine reset — user can re-activate on a new PC")


def cmd_list() -> None:
    rows = _request("GET", "licenses?select=email,authorized,active,machine_name,code_verified,last_seen&order=email")
    if not rows:
        print("(no users)")
        return
    print(f"{'Email':<40} {'Auth':<6} {'Active':<8} {'Verified':<10} {'Machine':<25} {'Last seen'}")
    print("-" * 120)
    for r in rows:
        print(f"{r.get('email','?'):<40} "
              f"{'YES' if r.get('authorized') else 'NO':<6} "
              f"{'YES' if r.get('active') else 'NO':<8} "
              f"{'YES' if r.get('code_verified') else 'NO':<10} "
              f"{(r.get('machine_name') or '-')[:24]:<25} "
              f"{(r.get('last_seen') or '-')[:19]}")


def main() -> None:
    load_env()
    parser = argparse.ArgumentParser(description="StreamBridge admin tool")
    sub = parser.add_subparsers(dest="command", required=True)

    for cmd in ("add", "remove", "deactivate", "activate", "reset-machine"):
        p = sub.add_parser(cmd)
        p.add_argument("email")

    sub.add_parser("list")

    args = parser.parse_args()

    if args.command == "add":
        cmd_add(args.email)
    elif args.command == "remove":
        cmd_remove(args.email)
    elif args.command == "deactivate":
        cmd_deactivate(args.email)
    elif args.command == "activate":
        cmd_activate(args.email)
    elif args.command == "reset-machine":
        cmd_reset_machine(args.email)
    elif args.command == "list":
        cmd_list()


if __name__ == "__main__":
    main()
