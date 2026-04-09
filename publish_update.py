"""Publish a new StreamBridge update.

Usage:
    python publish_update.py <new_version> [--notes "Release notes"]

Steps performed:
    1. Updates VERSION file
    2. Builds Windows exe with PyInstaller
    3. Creates installer with Inno Setup
    4. Uploads installer to GitHub Releases (requires `gh` CLI)
    5. Updates Supabase `app_versions` table

Requires:
    - gh CLI authenticated (`gh auth login`)
    - Supabase access token (env var SUPABASE_ACCESS_TOKEN or hardcoded below)
    - Inno Setup 6 installed at default path
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
import urllib.request

# --- Config ---
REPO = "eitan-ui/StreamBridge"
SUPABASE_URL = "https://rcmdvucxtpvmlfnphcjn.supabase.co"
INNO_SETUP = r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))


def load_env_file() -> None:
    """Load .env file into os.environ (if present)."""
    env_path = os.path.join(PROJECT_DIR, ".env")
    if not os.path.isfile(env_path):
        return
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, _, value = line.partition("=")
                os.environ.setdefault(key.strip(), value.strip())


def log(msg: str) -> None:
    print(f"[publish_update] {msg}")


def run(cmd: list[str] | str, **kwargs) -> subprocess.CompletedProcess:
    """Run a command and raise if it fails."""
    if isinstance(cmd, str):
        log(f"$ {cmd}")
        result = subprocess.run(cmd, shell=True, cwd=PROJECT_DIR, **kwargs)
    else:
        log(f"$ {' '.join(cmd)}")
        result = subprocess.run(cmd, cwd=PROJECT_DIR, **kwargs)
    if result.returncode != 0:
        raise RuntimeError(f"Command failed with exit code {result.returncode}")
    return result


def update_version_file(version: str) -> None:
    path = os.path.join(PROJECT_DIR, "VERSION")
    with open(path, "w") as f:
        f.write(version)
    log(f"VERSION file updated to {version}")


def build_exe() -> None:
    log("Building exe with PyInstaller...")
    dist_exe = os.path.join(PROJECT_DIR, "dist", "StreamBridge.exe")
    if os.path.exists(dist_exe):
        try:
            os.remove(dist_exe)
        except PermissionError:
            # In use, rename instead
            backup = dist_exe + ".old"
            if os.path.exists(backup):
                os.remove(backup)
            os.rename(dist_exe, backup)

    venv_python = os.path.join(PROJECT_DIR, "venv", "Scripts", "python.exe")
    python = venv_python if os.path.exists(venv_python) else sys.executable
    run([python, "-m", "PyInstaller", "streambridge_win.spec", "--noconfirm"])

    # Update portable folder
    portable_exe = os.path.join(PROJECT_DIR, "dist", "StreamBridge-Portable", "StreamBridge.exe")
    if os.path.isdir(os.path.dirname(portable_exe)):
        shutil.copy2(dist_exe, portable_exe)
        log("Copied exe to StreamBridge-Portable/")


def build_installer(version: str) -> str:
    log("Building installer with Inno Setup...")
    if not os.path.exists(INNO_SETUP):
        raise FileNotFoundError(f"Inno Setup not found at {INNO_SETUP}")

    iss_file = os.path.join(PROJECT_DIR, "installer", "streambridge.iss")
    run([INNO_SETUP, f"/DMyAppVersion={version}", iss_file])

    setup_file = os.path.join(PROJECT_DIR, "dist", f"StreamBridge-{version}-Setup.exe")
    if not os.path.exists(setup_file):
        raise FileNotFoundError(f"Installer not produced at {setup_file}")

    log(f"Installer created: {setup_file}")
    return setup_file


def build_portable_zip(version: str) -> str:
    log("Creating portable ZIP...")
    zip_file = os.path.join(PROJECT_DIR, "dist", f"StreamBridge-{version}-Portable.zip")
    if os.path.exists(zip_file):
        os.remove(zip_file)

    portable_dir = os.path.join(PROJECT_DIR, "dist", "StreamBridge-Portable")
    # PowerShell Compress-Archive
    run([
        "powershell", "-Command",
        f"Compress-Archive -Path '{portable_dir}\\*' -DestinationPath '{zip_file}'"
    ])
    log(f"Portable ZIP created: {zip_file}")
    return zip_file


def create_github_release(version: str, setup_file: str, zip_file: str,
                          notes: str) -> str:
    """Create a GitHub release and upload assets. Returns download URL for setup."""
    log(f"Creating GitHub release v{version}...")

    tag = f"v{version}"
    # Create release (will fail if tag exists — delete first if needed)
    try:
        run(["gh", "release", "create", tag,
             "--repo", REPO,
             "--title", f"StreamBridge {tag}",
             "--notes", notes or f"Release {tag}",
             setup_file, zip_file])
    except RuntimeError:
        log("Release may already exist — trying to upload assets...")
        run(["gh", "release", "upload", tag, setup_file, zip_file,
             "--repo", REPO, "--clobber"])

    # Construct download URL
    setup_name = os.path.basename(setup_file)
    download_url = f"https://github.com/{REPO}/releases/download/{tag}/{setup_name}"
    log(f"Download URL: {download_url}")
    return download_url


def update_supabase_version(version: str, download_url: str, notes: str) -> None:
    """Mark old versions as is_latest=false and insert new one.

    Uses SUPABASE_SERVICE_ROLE_KEY (from env or .env file) to bypass RLS.
    """
    log("Updating Supabase app_versions table...")

    service_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
    if not service_key:
        log("WARNING: SUPABASE_SERVICE_ROLE_KEY not set — skipping Supabase update")
        log("         Set it in .env or as an environment variable")
        return

    headers = {
        "apikey": service_key,
        "Authorization": f"Bearer {service_key}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }
    _SUPABASE_URL = SUPABASE_URL

    # Mark all existing as not latest
    req = urllib.request.Request(
        f"{_SUPABASE_URL}/rest/v1/app_versions?is_latest=eq.true",
        data=json.dumps({"is_latest": False}).encode(),
        headers=headers,
        method="PATCH",
    )
    try:
        urllib.request.urlopen(req, timeout=10).read()
        log("Marked old versions as not latest")
    except Exception as e:
        log(f"Could not update old versions: {e}")

    # Insert new version
    payload = {
        "version": version,
        "download_url": download_url,
        "release_notes": notes or f"Release v{version}",
        "is_latest": True,
    }
    req = urllib.request.Request(
        f"{_SUPABASE_URL}/rest/v1/app_versions",
        data=json.dumps(payload).encode(),
        headers=headers,
        method="POST",
    )
    try:
        urllib.request.urlopen(req, timeout=10).read()
        log(f"Inserted new version v{version} into Supabase")
    except Exception as e:
        log(f"Could not insert new version: {e}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Publish a StreamBridge update")
    parser.add_argument("version", help="New version (e.g., 1.0.1)")
    parser.add_argument("--notes", default="", help="Release notes")
    parser.add_argument("--skip-build", action="store_true", help="Skip exe/installer build")
    parser.add_argument("--skip-github", action="store_true", help="Skip GitHub release upload")
    parser.add_argument("--skip-supabase", action="store_true", help="Skip Supabase table update")
    args = parser.parse_args()

    load_env_file()

    version = args.version.lstrip("v")
    log(f"Publishing StreamBridge v{version}")

    update_version_file(version)

    if not args.skip_build:
        build_exe()
        setup_file = build_installer(version)
        zip_file = build_portable_zip(version)
    else:
        setup_file = os.path.join(PROJECT_DIR, "dist", f"StreamBridge-{version}-Setup.exe")
        zip_file = os.path.join(PROJECT_DIR, "dist", f"StreamBridge-{version}-Portable.zip")

    download_url = ""
    if not args.skip_github:
        download_url = create_github_release(version, setup_file, zip_file, args.notes)

    if not args.skip_supabase and download_url:
        update_supabase_version(version, download_url, args.notes)

    log(f"Done! StreamBridge v{version} published.")
    log("Next steps:")
    log("  - Commit the VERSION change: git add VERSION && git commit -m 'chore: bump version to {version}'")
    log("  - Push to GitHub: git push")


if __name__ == "__main__":
    main()
