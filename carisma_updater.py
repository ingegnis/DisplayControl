#!/usr/bin/env python3
"""Carisma offline-capable, operator-approved release updater.

This tool never checks for updates, downloads code, or changes system services
without an explicit operator command. It is deliberately separate from server.py.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import sys
import tempfile
import time
import zipfile

MAX_FILES = 5000
MAX_BYTES = 500 * 1024 * 1024
REQUIRED = ("server.py", "prompt_module.py", "prompt_player.html")


def fail(message):
    raise RuntimeError(message)


def digest(path):
    value = hashlib.sha256()
    with open(path, "rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def paths(home):
    root = Path(home).expanduser().resolve()
    return root, root / "releases", root / "shared" / "data", root / "current"


def prepare(home):
    root, releases, data, current = paths(home)
    releases.mkdir(parents=True, exist_ok=True)
    data.mkdir(parents=True, exist_ok=True)
    (root / "backups").mkdir(parents=True, exist_ok=True)
    return root, releases, data, current


def release_name(raw):
    if not raw or len(raw) > 70 or not all(c.isalnum() or c in ".-_" for c in raw):
        fail("Release name must be 1-70 letters/numbers/.-_")
    if raw.startswith(".") or raw in (".", ".."):
        fail("Invalid release name")
    return raw


def extract(archive, destination):
    with zipfile.ZipFile(archive) as z:
        members = [entry for entry in z.infolist() if not entry.is_dir()]
        if len(members) > MAX_FILES or sum(x.file_size for x in members) > MAX_BYTES:
            fail("Archive exceeds safety limits")
        names = []
        for item in z.infolist():
            p = PurePosixPath(item.filename)
            if (p.is_absolute() or not p.parts or ".." in p.parts
                    or "\\" in item.filename or ":" in item.filename
                    or item.flag_bits & 0x1
                    or ((item.external_attr >> 16) & 0o170000) == 0o120000):
                fail("Unsafe ZIP entry: " + item.filename)
            names.append(p.parts)
        roots = {p[0] for p in names}
        wrapped = len(roots) == 1 and all(len(p) > 1 for p in [PurePosixPath(e.filename).parts for e in members])
        for entry in members:
            parts = PurePosixPath(entry.filename).parts
            relative = parts[1:] if wrapped else parts
            if not relative:
                continue
            # Operational files and secrets are never accepted from a release.
            if relative[0] in ("data", ".git", ".controller-venv", "__pycache__"):
                fail("Archive contains an operational directory")
            if relative[0] in ("cluster.json", "station.json", "Config_Locale.bat"):
                fail("Archive contains local configuration")
            target = destination.joinpath(*relative)
            target.parent.mkdir(parents=True, exist_ok=True)
            with z.open(entry) as source, open(target, "xb") as sink:
                shutil.copyfileobj(source, sink)
    for name in REQUIRED:
        if not (destination / name).is_file():
            fail("Missing required application file: " + name)


def stage(home, archive, sha256, name):
    root, releases, data, current = prepare(home)
    archive = Path(archive).expanduser().resolve()
    if not archive.is_file() or len(sha256) != 64 or any(c not in "0123456789abcdefABCDEF" for c in sha256):
        fail("Specify an existing ZIP and its full 64-character SHA-256")
    actual = digest(archive)
    if actual.lower() != sha256.lower():
        fail("SHA-256 mismatch: staging aborted")
    name = release_name(name)
    target = releases / name
    if target.exists() or target.is_symlink():
        fail("Release already exists; refusing to overwrite it")
    with tempfile.TemporaryDirectory(prefix=".carisma-stage-", dir=releases) as tmp:
        staged = Path(tmp) / "app"
        staged.mkdir()
        extract(archive, staged)
        (staged / "data").symlink_to(data, target_is_directory=True)
        (staged / "UPDATER_MANIFEST.json").write_text(
            json.dumps({"archive_sha256": actual, "name": name, "staged_at": int(time.time())}, indent=2) + "\n")
        os.rename(staged, target)
    print("Staged:", target)
    print("No running service or active release was changed.")


def current_release(current, releases):
    if not current.is_symlink():
        if current.exists():
            fail("'current' exists but is not an updater-managed symlink")
        return None
    resolved = current.resolve(strict=True)
    if resolved.parent != releases or not resolved.is_dir():
        fail("'current' points outside managed releases")
    return resolved


def switch(current, target):
    tmp = current.parent / ".current-next"
    if tmp.exists() or tmp.is_symlink():
        fail("Stale .current-next exists; inspect manually")
    tmp.symlink_to(target, target_is_directory=True)
    os.replace(tmp, current)


def systemctl(action, unit):
    result = subprocess.run(["systemctl", action, unit], check=False, text=True,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=40)
    if result.returncode:
        fail("systemctl " + action + " failed: " + result.stderr.strip())


def backup_data(root, data):
    stamp = time.strftime("%Y%m%d-%H%M%S", time.gmtime())
    destination = root / "backups" / ("data-" + stamp + "-" + str(os.getpid()))
    shutil.copytree(data, destination, symlinks=False)
    return destination


def activate(home, name, unit):
    root, releases, data, current = prepare(home)
    target = releases / release_name(name)
    if not target.is_dir() or target.is_symlink() or not (target / "UPDATER_MANIFEST.json").is_file():
        fail("Release is not staged by this updater")
    previous = current_release(current, releases)
    if previous == target:
        fail("Release is already active")
    if unit:
        systemctl("stop", unit)
    try:
        backup = backup_data(root, data)
    except Exception:
        if unit:
            systemctl("start", unit)
        raise
    state_path = root / "previous.json"
    state = {"from": previous.name if previous else None, "to": target.name,
             "backup": str(backup), "time": int(time.time())}
    state_path.write_text(json.dumps(state, indent=2) + "\n")
    switch(current, target)
    if unit:
        try:
            systemctl("start", unit)
            systemctl("is-active", unit)
        except Exception:
            if previous:
                systemctl("stop", unit)
                switch(current, previous)
                systemctl("start", unit)
            else:
                systemctl("stop", unit)
                current.unlink()
            raise
    print("Active:", target)
    print("Data backup:", backup)
    print("Service health and player behavior still require operator acceptance.")


def rollback(home, unit):
    root, releases, data, current = prepare(home)
    state_file = root / "previous.json"
    if not state_file.is_file():
        fail("No previous release recorded")
    state = json.loads(state_file.read_text())
    previous = state.get("from")
    if not previous:
        fail("No prior release to restore")
    target = releases / release_name(previous)
    if not target.is_dir() or target.is_symlink():
        fail("Previous release directory missing")
    active = current_release(current, releases)
    if active is None or active.name != state.get("to"):
        fail("Release changed since activation: refusing unsafe rollback")
    print("Code rollback only. Data migrations may require manual restore from:", state["backup"])
    if unit:
        systemctl("stop", unit)
    switch(current, target)
    if unit:
        systemctl("start", unit)
    print("Rolled back to:", previous)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--home", default="/opt/carisma", help="Managed installation directory")
    sub = parser.add_subparsers(dest="command", required=True)
    s = sub.add_parser("stage", help="Verify a downloaded ZIP and stage it without activation")
    s.add_argument("--archive", required=True)
    s.add_argument("--sha256", required=True, help="Full independently verified SHA-256 of ZIP")
    s.add_argument("--name", required=True)
    a = sub.add_parser("activate", help="Operator-approved activation; back up data first")
    a.add_argument("--name", required=True)
    a.add_argument("--service", help="Explicit systemd unit name, e.g. carisma-core.service")
    b = sub.add_parser("rollback", help="Rollback code to the previous active release")
    b.add_argument("--service", help="Explicit systemd unit name")
    sub.add_parser("status")
    args = parser.parse_args()
    try:
        if args.command == "stage":
            stage(args.home, args.archive, args.sha256, args.name)
        elif args.command == "activate":
            activate(args.home, args.name, args.service)
        elif args.command == "rollback":
            rollback(args.home, args.service)
        else:
            root, releases, data, current = paths(args.home)
            active = current_release(current, releases)
            print("Active release:", active.name if active else "none")
            print("Data:", data)
            print("Standalone processes not managed by this updater are unaffected.")
    except (RuntimeError, OSError, ValueError, zipfile.BadZipFile, subprocess.TimeoutExpired) as e:
        print("Updater error:", e, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
