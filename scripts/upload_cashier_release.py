"""Upload Cashier Mode ZIP as an asset to a GitHub Release."""

import argparse
import json
import mimetypes
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


API_ROOT = "https://api.github.com"
UPLOAD_ROOT = "https://uploads.github.com"


def request_json(url, token, method="GET", payload=None):
    data = None
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "ZAY-POS-Release-Tool",
    }
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"

    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            body = response.read()
            return response.status, json.loads(body.decode("utf-8")) if body else {}
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        try:
            details = json.loads(body)
        except json.JSONDecodeError:
            details = {"message": body}
        return exc.code, details


def get_or_create_release(repo, version, token):
    tag = f"v{version}"
    status, release = request_json(
        f"{API_ROOT}/repos/{repo}/releases/tags/{urllib.parse.quote(tag)}",
        token,
    )
    if status == 200:
        return release
    if status != 404:
        raise RuntimeError(f"Could not read GitHub release: {release}")

    payload = {
        "tag_name": tag,
        "name": f"ZAY POS v{version}",
        "body": f"ZAY POS release v{version}",
        "draft": False,
        "prerelease": False,
    }
    status, release = request_json(
        f"{API_ROOT}/repos/{repo}/releases",
        token,
        method="POST",
        payload=payload,
    )
    if status not in (200, 201):
        raise RuntimeError(f"Could not create GitHub release: {release}")
    return release


def delete_existing_asset(repo, release, asset_name, token, replace):
    for asset in release.get("assets", []):
        if asset.get("name") != asset_name:
            continue
        if not replace:
            raise RuntimeError(
                f"Release asset already exists: {asset_name}. "
                "Enable the replace/recreate option to overwrite it."
            )
        status, result = request_json(
            f"{API_ROOT}/repos/{repo}/releases/assets/{asset['id']}",
            token,
            method="DELETE",
        )
        if status not in (204,):
            raise RuntimeError(f"Could not delete existing asset: {result}")
        print(f"Deleted existing asset: {asset_name}")
        return


def upload_asset(repo, release_id, zip_path, token):
    asset_name = zip_path.name
    query = urllib.parse.urlencode({"name": asset_name})
    url = f"{UPLOAD_ROOT}/repos/{repo}/releases/{release_id}/assets?{query}"
    content_type = mimetypes.guess_type(asset_name)[0] or "application/zip"
    data = zip_path.read_bytes()
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "ZAY-POS-Release-Tool",
        "Content-Type": content_type,
        "Content-Length": str(len(data)),
    }
    request = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=600) as response:
            result = json.loads(response.read().decode("utf-8"))
            print(f"Uploaded Cashier release asset: {result.get('browser_download_url', asset_name)}")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"GitHub upload failed ({exc.code}): {body}") from exc


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", required=True)
    parser.add_argument("--zip", required=True)
    parser.add_argument("--repo", required=True)
    parser.add_argument("--replace", action="store_true")
    args = parser.parse_args()

    token = os.getenv("GITHUB_TOKEN", "").strip()
    if not token:
        raise RuntimeError("GITHUB_TOKEN is not set.")

    zip_path = Path(args.zip).resolve()
    if not zip_path.is_file():
        raise FileNotFoundError(f"Cashier ZIP not found: {zip_path}")

    release = get_or_create_release(args.repo, args.version, token)
    delete_existing_asset(
        args.repo, release, zip_path.name, token, args.replace
    )
    upload_asset(args.repo, release["id"], zip_path, token)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
