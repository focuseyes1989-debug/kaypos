"""Upload a ZAY POS update package to GitHub Releases."""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path
from urllib.parse import quote


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


DEFAULT_REPO = "focuseyes1989-debug/ZAY_POS"
VERSION_RE = re.compile(r"^\d+\.\d+\.\d+$")


def get_project_root() -> Path:
    current_dir = Path(__file__).resolve().parent
    if current_dir.name == "scripts":
        return current_dir.parent
    return current_dir


PROJECT_ROOT = get_project_root()


def github_headers(token: str, content_type: str | None = None) -> dict[str, str]:
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if content_type:
        headers["Content-Type"] = content_type
    return headers


def print_github_error(action: str, exc) -> None:
    response = getattr(exc, "response", None)
    if response is None:
        print(f"ERROR: {action}: {exc}")
        return

    status_code = response.status_code
    print(f"ERROR: {action}: GitHub API returned {status_code}")
    try:
        body = response.json()
    except ValueError:
        body = {}

    message = body.get("message") if isinstance(body, dict) else ""
    if message:
        print(f"       Message: {message}")

    if status_code == 401:
        print("       Token is missing, invalid, expired, or was not passed to this script.")
    elif status_code == 403:
        print("       Token does not have permission. Use repo/content write access.")
    elif status_code == 404:
        print("       Repository not found, or this token cannot access it.")
    else:
        print(f"       {exc}")


def upload_release_asset(requests, upload_url: str, token: str, file_path: Path, content_type: str) -> None:
    asset_url = f"{upload_url}?name={quote(file_path.name)}"
    with file_path.open("rb") as handle:
        response = requests.post(
            asset_url,
            headers=github_headers(token, content_type),
            data=handle,
            timeout=300,
        )
        response.raise_for_status()


def prompt_delete_existing(version: str, recreate: bool) -> bool:
    if recreate:
        return True
    choice = input(f"Release v{version} already exists. Delete and recreate? (y/n): ")
    return choice.strip().lower() == "y"


def upload_to_github(
    version: str,
    zip_path: str | os.PathLike[str],
    token: str,
    repo: str = DEFAULT_REPO,
    recreate: bool = False,
) -> bool:
    try:
        import requests
    except ImportError:
        print("ERROR: Missing dependency: requests")
        print("Run: python -m pip install -r requirements.txt")
        return False

    zip_file = Path(zip_path)
    releases_url = f"https://api.github.com/repos/{repo}/releases"
    headers = github_headers(token)

    print()
    print("=" * 60)
    print("UPLOADING TO GITHUB")
    print("=" * 60)
    print(f"Repo: {repo}")
    print(f"Version: v{version}")

    print(f"Checking if release v{version} already exists...")
    try:
        response = requests.get(
            releases_url,
            headers=headers,
            params={"per_page": 100},
            timeout=30,
        )
        response.raise_for_status()
    except requests.exceptions.RequestException as exc:
        print_github_error("Failed to check GitHub releases", exc)
        return False

    for release in response.json():
        if release.get("tag_name") != f"v{version}":
            continue

        if not prompt_delete_existing(version, recreate):
            print("Upload cancelled.")
            return False

        print(f"Deleting existing release v{version}...")
        try:
            delete_response = requests.delete(release["url"], headers=headers, timeout=30)
            delete_response.raise_for_status()
        except requests.exceptions.RequestException as exc:
            print_github_error("Failed to delete existing release", exc)
            return False
        print(f"Deleted existing release v{version}.")
        break

    print(f"Creating release v{version}...")
    release_body = (
        f"# ZAY POS v{version}\n\n"
        "## Installation\n"
        "1. Download the update zip\n"
        "2. Extract to your ZAY POS folder\n"
        "3. Run the launcher\n\n"
        "## Changes\n"
        f"- Updated to version {version}\n"
        "- Bug fixes and improvements"
    )
    data = {
        "tag_name": f"v{version}",
        "name": f"ZAY POS v{version}",
        "body": release_body,
        "draft": False,
        "prerelease": False,
    }

    try:
        response = requests.post(releases_url, headers=headers, json=data, timeout=30)
        response.raise_for_status()
    except requests.exceptions.RequestException as exc:
        print_github_error("Failed to create release", exc)
        return False

    release_data = response.json()
    upload_url = release_data["upload_url"].replace("{?name,label}", "")
    print(f"Release created: {release_data['html_url']}")

    print(f"Uploading {zip_file.name}...")
    try:
        upload_release_asset(requests, upload_url, token, zip_file, "application/zip")
    except requests.exceptions.RequestException as exc:
        print_github_error("Failed to upload zip", exc)
        return False
    print(f"Uploaded: {zip_file.name}")

    launcher_candidates = [
        PROJECT_ROOT / "dist_launcher" / "ZAY_POS_Launcher.exe",
        PROJECT_ROOT / "dist_launcher" / "ZAY_POS_Launcher" / "ZAY_POS_Launcher.exe",
        PROJECT_ROOT / f"dist/ZAY_POS_v{version}/ZAY_POS_Launcher.exe",
    ]
    launcher_path = next((path for path in launcher_candidates if path.exists()), None)
    if launcher_path is not None:
        print("Uploading ZAY_POS_Launcher.exe...")
        try:
            upload_release_asset(
                requests,
                upload_url,
                token,
                launcher_path,
                "application/x-msdownload",
            )
            print("Uploaded: ZAY_POS_Launcher.exe")
        except requests.exceptions.RequestException as exc:
            print_github_error("Failed to upload launcher", exc)

    print()
    print("=" * 60)
    print("UPLOAD COMPLETE")
    print("=" * 60)
    print(f"Release URL: {release_data['html_url']}")
    print(f"Update zip uploaded: {zip_file.name}")
    print("=" * 60)
    return True


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Upload ZAY POS update to GitHub")
    parser.add_argument("--version", help="Version to upload, for example 1.0.8")
    parser.add_argument("--zip", help="Path to update zip file")
    parser.add_argument("--token", help="GitHub token")
    parser.add_argument("--repo", default=DEFAULT_REPO, help="GitHub repo in owner/name format")
    parser.add_argument(
        "--recreate",
        action="store_true",
        help="Delete and recreate the release if the tag already exists",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if not args.version:
        while True:
            version = input("Enter version to upload (e.g., 1.0.8): ").strip()
            if VERSION_RE.match(version):
                args.version = version
                break
            print("Invalid version format.")

    if not args.zip:
        default_zip = PROJECT_ROOT / f"update_build/ZAY_POS_v{args.version}_update.zip"
        if default_zip.exists():
            args.zip = str(default_zip)
            print(f"Using: {args.zip}")
        else:
            args.zip = input("Enter path to zip file: ").strip()

    if not Path(args.zip).exists():
        print(f"ERROR: Zip file not found: {args.zip}")
        sys.exit(1)

    if not args.token:
        args.token = os.getenv("GITHUB_TOKEN", "").strip()
        if args.token:
            print("Using GitHub token from GITHUB_TOKEN.")

    if not args.token:
        print()
        print("=" * 60)
        print("GITHUB TOKEN REQUIRED")
        print("=" * 60)
        print("1. Go to: https://github.com/settings/tokens")
        print("2. Generate a token with repo/content write access")
        print("3. Copy the token")
        print("-" * 60)
        args.token = input("Enter GitHub token: ").strip()

    if not args.token:
        print("ERROR: GitHub token required.")
        sys.exit(1)

    success = upload_to_github(
        args.version,
        args.zip,
        args.token,
        args.repo,
        recreate=args.recreate,
    )
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    if Path(__file__).resolve().parent.name == "scripts":
        os.chdir(PROJECT_ROOT)
        print(f"Changed directory to: {os.getcwd()}")

    main()
