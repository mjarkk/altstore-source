#!/usr/bin/env python3
import argparse
import datetime
import json
import shutil
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "source.json"
ADPS_API = "https://api.altstore.io/adps"
# api.altstore.io answers 403 to urllib's default User-Agent.
USER_AGENT = "add-version.py (+https://github.com/mjarkk/altstore-source)"


def request(url, data=None, headers=None):
    return urllib.request.Request(url, data=data, headers={"User-Agent": USER_AGENT, **(headers or {})})


def adp_info(adp_id):
    try:
        with urllib.request.urlopen(request(f"{ADPS_API}/{adp_id}")) as res:
            return json.load(res)
    except urllib.error.HTTPError as err:
        if err.code == 404:
            return {}
        raise


def request_processing(adp_id):
    body = json.dumps({"adpID": adp_id}).encode()
    urllib.request.urlopen(request(ADPS_API, body, {"Content-Type": "application/json"})).close()


def download_adp(adp_id, dest):
    info = adp_info(adp_id)
    url = info.get("downloadURL")
    if not url or info.get("downloadExpired"):
        request_processing(adp_id)
        sys.exit(
            f"AltStore PAL has no download ready for {adp_id} (status: {info.get('status', 'unknown')}). "
            "Asked it to process the package; run this again in a few minutes."
        )
    archive = dest / "adp.zip"
    with urllib.request.urlopen(request(url)) as res, open(archive, "wb") as out:
        shutil.copyfileobj(res, out)
    with zipfile.ZipFile(archive) as zf:
        zf.extractall(dest / "adp")
    return dest / "adp"


def find_app(source, manifest):
    bundle_id = manifest["bundleId"]
    app = next((a for a in source["apps"] if a["bundleIdentifier"] == bundle_id), None)
    if app is None:
        sys.exit(f"source.json has no app with bundleIdentifier {bundle_id}; add one first (see README.md).")
    marketplace_id = str(manifest["appleItemId"])
    if app.get("marketplaceID", marketplace_id) != marketplace_id:
        sys.exit(f"{bundle_id} has marketplaceID {app['marketplaceID']} in source.json, but the package says {marketplace_id}.")
    return app


def github_repo():
    return subprocess.run(
        ["gh", "repo", "view", "--json", "nameWithOwner", "-q", ".nameWithOwner"],
        cwd=ROOT, check=True, capture_output=True, text=True,
    ).stdout.strip()


def publish_release(repo, tag, title, files):
    exists = subprocess.run(
        ["gh", "release", "view", tag, "--repo", repo], cwd=ROOT, capture_output=True
    ).returncode == 0
    if exists:
        cmd = ["gh", "release", "upload", tag, "--repo", repo, "--clobber"]
    else:
        cmd = ["gh", "release", "create", tag, "--repo", repo, "--title", title, "--notes", ""]
    subprocess.run(cmd + [str(f) for f in files], cwd=ROOT, check=True)


def add_version(app, manifest, repo, tag, files):
    base = f"https://github.com/{repo}/releases/download/{tag}"
    # Release assets are flat (no variant/ folder), so AltStore looks each ADP file up here by name.
    asset_urls = {f.stem: f"{base}/{f.name}" for f in files}
    version = {
        "version": manifest["shortVersionString"],
        "buildVersion": manifest["bundleVersion"],
        "date": datetime.date.today().isoformat(),
        "downloadURL": asset_urls["manifest"],
        "assetURLs": asset_urls,
        "size": max(v["variantDetails"]["compressedSize"] for v in manifest["variants"]),
        "minOSVersion": manifest["minimumSystemVersions"]["ios"],
    }
    same = (version["version"], version["buildVersion"])
    app["marketplaceID"] = str(manifest["appleItemId"])
    app["versions"] = [version] + [v for v in app["versions"] if (v["version"], v["buildVersion"]) != same]
    return version


def main():
    parser = argparse.ArgumentParser(
        description="Publish a notarized app version: download its package from AltStore PAL, "
        "upload it to a GitHub release in this repo and add the version to source.json."
    )
    parser.add_argument("adp_id", help="Alternative Distribution Package ID (App Store Connect → app → Distribution → History)")
    args = parser.parse_args()

    source = json.loads(SOURCE.read_text())
    repo = github_repo()
    with tempfile.TemporaryDirectory() as tmp:
        adp = download_adp(args.adp_id, Path(tmp))
        manifest = json.loads((adp / "manifest.json").read_text())
        app = find_app(source, manifest)
        tag = f"{manifest['bundleId']}-{manifest['shortVersionString']}-{manifest['bundleVersion']}"
        files = [adp / "manifest.json", adp / "signature", *sorted((adp / "variant").glob("*.ipa"))]
        publish_release(repo, tag, f"{app['name']} {manifest['shortVersionString']} ({manifest['bundleVersion']})", files)
        version = add_version(app, manifest, repo, tag, files)

    SOURCE.write_text(json.dumps(source, indent=2, ensure_ascii=False) + "\n")
    print(
        f"\nAdded {app['name']} {version['version']} ({version['buildVersion']}) to source.json.\n"
        "If this version added entitlements or NS…UsageDescription keys, add them to its appPermissions.\n"
        "Then commit and push source.json."
    )


if __name__ == "__main__":
    main()
