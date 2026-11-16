#!/usr/bin/env python3
"""Windows dependency repair; no pip, winget or permanent PATH modifications.

Only the explicit 'repair' command downloads or installs software. 'launch'
loads saved, project-local paths and starts the existing server. NDI's official
installer remains interactive so the user can review its licence and UAC prompt.
"""
from __future__ import annotations
import argparse
from contextlib import contextmanager
import hashlib
import http.client
import json
import logging
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import ssl
import stat
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from diagnose_ndi import check, print_report, probe_ffmpeg, probe_ndi
from ndi.gateway import ffmpeg_binary

FFMPEG_URL = 'https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip'
FFMPEG_HASH_URL = FFMPEG_URL + '.sha256'
NDI_URL = 'https://ndi.link/NDIRedistV6'
MAX_DOWNLOAD = 600 * 1024 * 1024
MAX_UNPACKED = 2 * 1024 * 1024 * 1024
SETTINGS_NAME = 'dependencies.json'
LOG = logging.getLogger('carisma.setup')


class SetupError(RuntimeError):
    pass


def say(message: str) -> None:
    print(message, flush=True)
    LOG.info(message)


class HTTPSOnlyRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if urllib.parse.urlsplit(newurl).scheme.lower() != 'https':
            raise SetupError('Download rifiutato: redirect verso una connessione non HTTPS.')
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def download(url: str, destination: Path, max_bytes: int = MAX_DOWNLOAD,
             attempts: int = 3) -> None:
    """TLS verified, bounded size, partial-file cleanup and atomic completion."""
    if urllib.parse.urlsplit(url).scheme.lower() != 'https':
        raise SetupError('I download devono usare HTTPS.')
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    opener = urllib.request.build_opener(
        HTTPSOnlyRedirect(), urllib.request.HTTPSHandler(context=ssl.create_default_context()))
    request = urllib.request.Request(url, headers={'User-Agent': 'Carisma-Setup/0.4.1'})
    last_error = ''
    for attempt in range(attempts):
        fd, partial_name = tempfile.mkstemp(prefix=destination.name + '.', suffix='.part', dir=destination.parent)
        partial = Path(partial_name)
        os.close(fd)
        try:
            with opener.open(request, timeout=30) as response, partial.open('wb') as out:
                if urllib.parse.urlsplit(response.geturl()).scheme != 'https':
                    raise SetupError('Il server ha restituito un URL non HTTPS.')
                total = int(response.headers.get('Content-Length') or 0)
                if total > max_bytes:
                    raise SetupError('Download troppo grande: interrotto per sicurezza.')
                done, last_update = 0, 0.0
                while True:
                    chunk = response.read(1024 * 1024)
                    if not chunk:
                        break
                    done += len(chunk)
                    if done > max_bytes:
                        raise SetupError('Limite dimensione download superato.')
                    out.write(chunk)
                    if max_bytes > 1024 * 1024 and time.monotonic() - last_update > 2:
                        say('  Scaricati %.1f MB%s' % (done / 1048576,
                            (' / %.1f MB' % (total / 1048576)) if total else ''))
                        last_update = time.monotonic()
                if not done or (total and done != total):
                    raise SetupError('Download incompleto; nessun file verra eseguito.')
            os.replace(partial, destination)
            return
        except (OSError, ValueError, urllib.error.URLError, http.client.HTTPException, SetupError) as exc:
            last_error = str(exc)
            if attempt + 1 < attempts:
                say('  Download non riuscito, nuovo tentativo %d/%d.' % (attempt + 2, attempts))
                time.sleep(1)
        finally:
            partial.unlink(missing_ok=True)
    raise SetupError('Download fallito: %s\n%s\nControlla Internet, proxy o certificati. TLS non e stato disabilitato.' % (url, last_error))


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def parse_sha256(text: str) -> str:
    matches = re.findall(r'(?<![0-9a-fA-F])[0-9a-fA-F]{64}(?![0-9a-fA-F])', text)
    if len(matches) != 1:
        raise SetupError('Checksum SHA-256 mancante o ambiguo: installazione bloccata.')
    return matches[0].lower()


def verified_ffmpeg_archive(cache: Path) -> Path:
    """Reuse an already verified cache; otherwise fetch hash and archive together."""
    cache.mkdir(parents=True, exist_ok=True)
    archive = cache / 'ffmpeg-release-essentials.zip'
    checksum = cache / 'ffmpeg-release-essentials.zip.sha256'
    if archive.is_file() and checksum.is_file():
        try:
            if sha256(archive) == parse_sha256(checksum.read_text(encoding='utf-8')):
                say('FFmpeg: uso il pacchetto gia scaricato; SHA-256 verificato.')
                return archive
        except (OSError, ValueError, SetupError):
            pass
    # A publisher can update a floating download URL between two requests.
    # Retry the pair once; never install a mismatching or incomplete archive.
    for attempt in range(2):
        say('FFmpeg: scarico checksum e build Windows x64 da gyan.dev.')
        download(FFMPEG_HASH_URL, checksum, max_bytes=16384)
        expected = parse_sha256(checksum.read_text(encoding='utf-8'))
        download(FFMPEG_URL, archive)
        if sha256(archive) == expected:
            say('FFmpeg: checksum SHA-256 OK.')
            return archive
        say('FFmpeg: checksum NON coincidente. Il file non viene usato.')
    raise SetupError('SHA-256 FFmpeg non valido dopo due tentativi. Nessun eseguibile installato.')


def safe_extract(archive: Path, target: Path) -> None:
    """Reject ZIP traversal, Windows drive paths, special files and zip bombs."""
    target = Path(target)
    with zipfile.ZipFile(archive) as z:
        items = z.infolist()
        if len(items) > 20000 or sum(i.file_size for i in items) > MAX_UNPACKED:
            raise SetupError('Archivio ZIP oltre i limiti di estrazione.')
        seen = set()
        for item in items:
            name = item.filename.replace('\\', '/')
            parts = PurePosixPath(name).parts
            mode = item.external_attr >> 16
            if (not parts or name.startswith('/') or '..' in parts or
                    any(':' in p or p.rstrip('. ') != p or
                        re.fullmatch(r'(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\..*)?', p, re.I)
                        for p in parts) or
                    (stat.S_IFMT(mode) not in (0, stat.S_IFREG, stat.S_IFDIR))):
                raise SetupError('Percorso ZIP non sicuro: ' + item.filename)
            normalized = '/'.join(parts).casefold()
            if normalized in seen:
                raise SetupError('Percorso ZIP duplicato: ' + item.filename)
            seen.add(normalized)
        target.mkdir(parents=True, exist_ok=True)
        for item in items:
            parts = PurePosixPath(item.filename.replace('\\', '/')).parts
            out = target.joinpath(*parts)
            if item.is_dir():
                out.mkdir(parents=True, exist_ok=True)
            else:
                out.parent.mkdir(parents=True, exist_ok=True)
                with z.open(item) as src, out.open('xb') as dst:
                    shutil.copyfileobj(src, dst)


def install_ffmpeg(root: Path) -> str:
    archive = verified_ffmpeg_archive(root / '.setup' / 'downloads')
    target = root / 'bin' / 'ffmpeg'
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.ffmpeg-stage-', dir=target.parent) as folder:
        stage = Path(folder)
        safe_extract(archive, stage)
        executables = [p for p in stage.rglob('*') if p.is_file() and
                       p.name.lower() == 'ffmpeg.exe' and p.parent.name.lower() == 'bin']
        if len(executables) != 1:
            raise SetupError('La struttura del pacchetto FFmpeg non e quella attesa.')
        exe = executables[0]
        report = probe_ffmpeg(str(exe), smoke=True)
        if not report['available']:
            raise SetupError('La nuova build FFmpeg non funziona su questo PC: ' + report['error'])
        backup = None
        if target.exists():
            backup = target.with_name('ffmpeg.backup-' + time.strftime('%Y%m%d-%H%M%S') + '-' + str(time.time_ns()))
            target.rename(backup)
        try:
            exe.parent.parent.rename(target)
        except OSError:
            if backup is not None and backup.exists() and not target.exists():
                backup.rename(target)
            raise
        if backup:
            say('Vecchia cartella FFmpeg conservata in: ' + str(backup))
    path = target / 'bin' / 'ffmpeg.exe'
    say('FFmpeg installato nel progetto: ' + str(path))
    return str(path)


def resolve_path(root: Path, value: str) -> str:
    if not value or not isinstance(value, str):
        return ''
    path = Path(value)
    if not path.is_absolute():
        path = root / path
    return str(path.resolve()) if path.is_file() else ''


def portable_path(root: Path, value: str) -> str:
    if not value:
        return ''
    path = Path(value).resolve()
    try:
        return str(path.relative_to(root.resolve()))
    except ValueError:
        return str(path)


def read_settings(root: Path) -> dict:
    path = root / '.setup' / SETTINGS_NAME
    if not path.is_file():
        return {}
    try:
        value = json.loads(path.read_text(encoding='utf-8-sig'))
        if not isinstance(value, dict) or value.get('schema') != 1:
            raise ValueError('schema non valido')
        return value
    except (OSError, ValueError) as exc:
        raise SetupError('Configurazione dipendenze non leggibile: %s. %s' % (path, exc))


def apply_settings(root: Path) -> None:
    # A successful repair records tested paths. They take precedence for these
    # project launchers only. Config_Locale.bat and the system are not edited.
    settings = read_settings(root)
    for key, variable in [('ffmpeg', 'CARISMA_FFMPEG'), ('ndi', 'CARISMA_NDI_LIBRARY')]:
        resolved = resolve_path(root, settings.get(key, ''))
        if resolved:
            os.environ[variable] = resolved


def save_settings(root: Path, ffmpeg: str = '', ndi: str = '') -> None:
    parent = root / '.setup'
    parent.mkdir(parents=True, exist_ok=True)
    settings = read_settings(root)
    settings.update({'schema': 1, 'python': sys.executable})
    if ffmpeg:
        settings['ffmpeg'] = portable_path(root, ffmpeg)
    if ndi:
        settings['ndi'] = portable_path(root, ndi)
    fd, name = tempfile.mkstemp(prefix='dependencies-', suffix='.json.tmp', dir=parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as file:
            json.dump(settings, file, ensure_ascii=True, indent=2)
            file.write('\n')
        os.replace(name, parent / SETTINGS_NAME)
    finally:
        Path(name).unlink(missing_ok=True)


def refresh_ndi_environment() -> None:
    """Installer changes registry variables, not this already running process."""
    if os.name != 'nt':
        return
    import winreg
    for hive, location in [
            (winreg.HKEY_LOCAL_MACHINE, r'SYSTEM\CurrentControlSet\Control\Session Manager\Environment'),
            (winreg.HKEY_CURRENT_USER, r'Environment')]:
        try:
            with winreg.OpenKey(hive, location) as key:
                for i in range(winreg.QueryInfoKey(key)[1]):
                    name, value, kind = winreg.EnumValue(key, i)
                    if name.startswith('NDI_RUNTIME_DIR_') and isinstance(value, str):
                        os.environ[name] = os.path.expandvars(value)
        except OSError:
            pass


def install_ndi(root: Path) -> None:
    cache = root / '.setup' / 'downloads'
    cache.mkdir(parents=True, exist_ok=True)
    installer = cache / 'NDI-Runtime-v6.exe'
    if not installer.is_file():
        say('NDI: scarico il runtime dal collegamento ufficiale ndi.link.')
        download(NDI_URL, installer)
    say('NDI: verifica firma digitale e apertura installer ufficiale.')
    say('Leggi e accetta la licenza nella finestra NDI. Windows puo chiedere conferma amministratore.')
    # No silent EULA acceptance and no untrusted command construction.
    helper = root / 'Windows_InstallatoreFirmato.ps1'
    p = subprocess.run(['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass',
                        '-File', str(helper), '-InstallerPath', str(installer), '-Product', 'NDI'],
                       check=False)
    if p.returncode not in (0, 3010):
        raise SetupError('Installazione NDI annullata o fallita (codice %s). Leggi il messaggio Windows; nessun successo dichiarato.' % p.returncode)
    if p.returncode == 3010:
        say('NDI richiede un riavvio. Il PC NON viene riavviato automaticamente.')
    refresh_ndi_environment()


@contextmanager
def without_env(key: str):
    old = os.environ.pop(key, None)
    try:
        yield
    finally:
        if old is not None:
            os.environ[key] = old


def find_working_ffmpeg(root: Path) -> dict:
    candidates = [ffmpeg_binary(root), str(root / 'bin' / 'ffmpeg.exe'),
                  str(root / 'bin' / 'ffmpeg' / 'bin' / 'ffmpeg.exe'), shutil.which('ffmpeg')]
    seen = set()
    for candidate in candidates:
        if candidate and candidate not in seen and Path(candidate).is_file():
            seen.add(candidate)
            result = probe_ffmpeg(candidate, smoke=True)
            if result['available']:
                return result
            say('FFmpeg rilevato ma non utilizzabile: ' + result['error'])
    return {'available': False, 'path': ''}


def repair(root: Path) -> dict:
    apply_settings(root)
    say('\nCARISMA / INSTALLAZIONE E VERIFICA NDI v0.4.1')
    say('Python %s a %d bit: gia presente; non viene reinstallato.' %
        (sys.version.split()[0], 64 if sys.maxsize > 2**32 else 32))
    ff = find_working_ffmpeg(root)
    if ff['available']:
        say('FFmpeg: gia disponibile, encoder e conversione di prova OK.')
    else:
        say('FFmpeg mancante o non utilizzabile: installazione locale automatica.')
        ff = probe_ffmpeg(install_ffmpeg(root), smoke=True)
        if not ff['available']:
            raise SetupError(ff['error'])
    os.environ['CARISMA_FFMPEG'] = ff['path']
    # Save completed work even if a later interactive NDI installation is cancelled.
    save_settings(root, ffmpeg=ff['path'])
    ndi = probe_ndi(root)
    if not ndi['available'] and os.environ.get('CARISMA_NDI_LIBRARY'):
        with without_env('CARISMA_NDI_LIBRARY'):
            alternative = probe_ndi(root)
        if alternative['available']:
            ndi = alternative
    if ndi['available']:
        say('NDI: gia disponibile; non viene reinstallato. ' + ndi['version'])
    else:
        say('NDI non utilizzabile: ' + ndi['error'])
        install_ndi(root)
        with without_env('CARISMA_NDI_LIBRARY'):
            ndi = probe_ndi(root)
        if not ndi['available']:
            raise SetupError('Installer terminato ma il runtime non si carica. ' + ndi['error'] +
                             '\nRiavvia se richiesto dal fornitore e ripeti la verifica.')
    if ndi.get('path'):
        os.environ['CARISMA_NDI_LIBRARY'] = ndi['path']
    save_settings(root, ffmpeg=ff['path'], ndi=ndi.get('path', ''))
    say('\nControllo finale e ricerca sorgenti sulla LAN...')
    report = check(root, seconds=5, smoke=True)
    print_report(report)
    if not report['dependencies_ok']:
        raise SetupError('Il controllo finale non e passato. Vedi .setup/install.log.')
    say('\nPRONTO. Ora puoi eseguire Avvia_Windows.bat.')
    say('Internet non serve durante il funzionamento normale. Nessuna modifica al PATH o al firewall.')
    return report


@contextmanager
def setup_lock(root: Path):
    """One repair at a time; the OS releases the lock if the process terminates."""
    import msvcrt
    folder = root / '.setup'
    folder.mkdir(parents=True, exist_ok=True)
    with (folder / 'install.lock').open('a+b') as file:
        file.seek(0, 2)
        if file.tell() == 0:
            file.write(b'0')
            file.flush()
        file.seek(0)
        try:
            msvcrt.locking(file.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError as exc:
            raise SetupError('Una verifica/installazione e gia in corso in questa cartella.') from exc
        try:
            yield
        finally:
            file.seek(0)
            msvcrt.locking(file.fileno(), msvcrt.LK_UNLCK, 1)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description='Setup delle dipendenze Carisma')
    parser.add_argument('action', choices=('repair', 'check', 'launch', 'launch-lan'))
    args = parser.parse_args(argv)
    root = Path(__file__).resolve().parent
    if sys.version_info < (3, 9) or sys.maxsize <= 2**32:
        print('Serve Python >= 3.9 a 64 bit. Avvia Verifica_NDI_Windows.bat.')
        return 1
    try:
        if args.action == 'repair':
            if os.name != 'nt':
                raise SetupError('La riparazione automatica e per Windows x64. Su Debian usa la guida Linux.')
            folder = root / '.setup'
            folder.mkdir(parents=True, exist_ok=True)
            from logging.handlers import RotatingFileHandler
            handler = RotatingFileHandler(folder / 'install.log', maxBytes=1024*1024,
                                          backupCount=2, encoding='utf-8')
            handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(message)s'))
            LOG.addHandler(handler)
            LOG.setLevel(logging.INFO)
            with setup_lock(root):
                repair(root)
            return 0
        apply_settings(root)
        if args.action == 'check':
            report = check(root, seconds=5, smoke=True)
            print_report(report)
            print('Sola verifica: nessun download o installazione.')
            return 0 if report['dependencies_ok'] else 1
        command = [sys.executable, str(root / 'server.py'), '--open']
        if args.action == 'launch-lan': command += ['--host', '0.0.0.0', '--prompt-osc-bind', '0.0.0.0']
        return subprocess.call(command, cwd=root)
    except KeyboardInterrupt:
        say('\nOperazione interrotta dall\'utente; nessun successo dichiarato.')
        return 130
    except (SetupError, OSError, ValueError, zipfile.BadZipFile) as exc:
        say('\nERRORE: ' + str(exc))
        LOG.exception('Setup non completato')
        print('Correggi il problema e rilancia: le dipendenze funzionanti non vengono reinstallate.')
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
