#!/usr/bin/env python3
"""Desktop-session browser supervisor; scoped profile, local shell, bounded log."""
import argparse
import json
import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
import signal
import subprocess
import time
import urllib.request


def browser_args(browser, state, url):
    return [browser, '--kiosk', '--no-first-run', '--disable-session-crashed-bubble',
            '--disable-extensions', '--disable-background-networking',
            '--autoplay-policy=no-user-gesture-required', '--renderer-process-limit=2',
            '--disk-cache-size=67108864', '--user-data-dir=' + str(state / 'browser'), url]


def ready(url):
    try:
        with urllib.request.urlopen(url + 'prompt_shared.js', timeout=1) as response:
            return response.status == 200
    except OSError:
        return False


def run(state, browser, url):
    import fcntl
    state.mkdir(parents=True, exist_ok=True)
    lock = (state / 'kiosk.lock').open('a+')
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        return 0
    if not os.environ.get('DISPLAY') and not os.environ.get('WAYLAND_DISPLAY'):
        raise RuntimeError('No desktop session. Start from the Raspberry desktop or log in graphically.')
    logger = logging.getLogger('displaycontrol.kiosk')
    logger.setLevel(logging.INFO)
    handler = RotatingFileHandler(state / 'kiosk.log', maxBytes=512 * 1024, backupCount=2)
    handler.setFormatter(logging.Formatter('%(asctime)s %(message)s'))
    logger.addHandler(handler)
    running = True
    child = None
    def stop(*_):
        nonlocal running
        running = False
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    def close_browser():
        nonlocal child
        if child and child.poll() is None:
            try:
                os.killpg(child.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            try:
                child.wait(timeout=8)
            except subprocess.TimeoutExpired:
                try:
                    os.killpg(child.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                child.wait(timeout=3)
        child = None
    (state / 'kiosk-status.json').write_text(json.dumps({'pid': os.getpid()}), encoding='utf-8')
    try:
        logger.info('Supervisor started')
        while running:
            if (state.parent / 'PAUSED').exists():
                close_browser()
                time.sleep(1)
                continue
            if child and child.poll() is not None:
                logger.warning('Browser exited (%s); retrying', child.returncode)
                child = None
                time.sleep(3)
            if child is None and ready(url):
                # Browser stderr can contain URLs/tokens; do not persist it.
                child = subprocess.Popen(browser_args(browser, state, url),
                                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                         start_new_session=True)
                logger.info('Browser started')
            time.sleep(1)
    finally:
        close_browser()
        (state / 'kiosk-status.json').unlink(missing_ok=True)
        handler.close()
        logger.removeHandler(handler)
        lock.close()
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('run', 'start', 'stop', 'restart', 'status'))
    parser.add_argument('--state-dir', required=True, type=Path)
    parser.add_argument('--browser')
    parser.add_argument('--url', default='http://127.0.0.1:8877/')
    args = parser.parse_args()
    state = args.state_dir.resolve()
    state.mkdir(parents=True, exist_ok=True)
    if args.action == 'run':
        if not args.browser:
            parser.error('--browser is required for run')
        return run(state, args.browser, args.url)
    if args.action in ('stop', 'restart'):
        (state.parent / 'PAUSED').touch(mode=0o600)
        if args.action == 'restart':
            time.sleep(3)
    if args.action in ('start', 'restart'):
        (state.parent / 'PAUSED').unlink(missing_ok=True)
    if args.action == 'status':
        active = False
        try:
            pid = json.loads((state / 'kiosk-status.json').read_text())['pid']
            os.kill(pid, 0)
            active = True
        except (OSError, ValueError, KeyError):
            pass
        print('Browser supervisor: ' + ('running' if active else 'not running'))
        print('Browser: ' + ('paused' if (state.parent / 'PAUSED').exists() else 'enabled'))
        print('Local shell: ' + ('reachable' if ready(args.url) else 'unreachable'))
    else:
        print('Browser action saved. If the supervisor is not running, log out/in or reboot.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
