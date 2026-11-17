#!/usr/bin/env python3
"""Build Carisma's Android TV APK using the official SDK and a local JDK.
No Gradle, Maven, pip or Android Studio project sync. Requires Internet only to
provision missing SDK packages. SDK licenses are shown, never auto-accepted.
Native SDK build and signing are verified; physical device testing is separate.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import urllib.request
import zipfile

ROOT=Path(__file__).resolve().parent
SOURCE=ROOT/'android-player'
DOWNLOADS={
    'win': ('commandlinetools-win-15859902_latest.zip','90ae805d20434428bffcb699c290860f19bb5f66a67e6b330067e3de801fb04a'),
    'linux': ('commandlinetools-linux-15859902_latest.zip','4e4c464f145a7512b57d088ac6c278c03c9eea610886b35a5e0804e74eedf583'),
}


def run(args, env=None):
    args=[str(x) for x in args]
    print('> '+subprocess.list2cmdline(args),flush=True)
    subprocess.run(args,check=True,env=env)


def safe_extract(archive,dest):
    dest=Path(dest).resolve()
    with zipfile.ZipFile(archive) as z:
        if sum(x.file_size for x in z.infolist())>1024**3: raise ValueError('Archivio SDK troppo grande')
        for info in z.infolist():
            name=info.filename.replace('\\','/')
            if name.startswith('/') or ':' in name or '..' in name.split('/'):
                raise ValueError('Percorso archivio non sicuro')
        z.extractall(dest)


def jdk():
    suffix='.exe' if os.name=='nt' else ''
    homes=[]
    if os.environ.get('JAVA_HOME'): homes.append(Path(os.environ['JAVA_HOME']))
    javac=shutil.which('javac')
    if javac: homes.append(Path(javac).resolve().parent.parent)
    if os.name=='nt':
        pf=Path(os.environ.get('ProgramFiles',r'C:\Program Files'))
        homes += [pf/'Android'/'Android Studio'/'jbr']
        for sub in ['Microsoft','Eclipse Adoptium','Java']:
            if (pf/sub).is_dir(): homes+=list((pf/sub).glob('*'))
    for home in homes:
        java=home/'bin'/('java'+suffix)
        if not java.is_file() or not (home/'bin'/('javac'+suffix)).is_file(): continue
        try:
            version=subprocess.run([str(java),'-version'],capture_output=True,text=True,timeout=10)
            m=re.search(r'version "(\d+)',version.stderr+version.stdout)
            if m and int(m.group(1))>=17: return home
        except (OSError,subprocess.TimeoutExpired): pass
    raise RuntimeError('JDK 17+ non trovato. Installa un JDK (non solo JRE), per esempio Microsoft OpenJDK 21, o Android Studio; poi ripeti. Non serve un account Google.')


def fetch_checked(url,dest,sha):
    dest=Path(dest)
    if dest.is_file() and hashlib.sha256(dest.read_bytes()).hexdigest()==sha:return
    part=dest.with_suffix(dest.suffix+'.part')
    try:
        with urllib.request.urlopen(url,timeout=60) as src,part.open('wb') as dst:
            size=0
            while True:
                block=src.read(1024*1024)
                if not block:break
                size+=len(block)
                if size>350*1024*1024:raise ValueError('Download oltre il limite previsto')
                dst.write(block)
        if hashlib.sha256(part.read_bytes()).hexdigest()!=sha:
            raise ValueError('Checksum SDK non valido: file non utilizzato. Verifica la pagina ufficiale Android, non saltare il controllo.')
        part.replace(dest)
    finally:part.unlink(missing_ok=True)


def prepare_sdk(path,install,env):
    path=Path(path).resolve(); platform=path/'platforms'/'android-35'/'android.jar';tools=path/'build-tools'/'35.0.0'
    if platform.is_file() and (tools/('aapt2.exe' if os.name=='nt' else 'aapt2')).is_file():return path
    if not install:raise RuntimeError('SDK incompleto. Ripeti con --install-sdk (licenze interattive) oppure imposta --sdk con il tuo SDK.')
    system='win' if os.name=='nt' else 'linux' if sys.platform.startswith('linux') else ''
    if not system:raise RuntimeError('Provisioning automatico solo Windows/Linux. Su macOS usa --sdk con SDK gia installato.')
    manager=path/'cmdline-tools'/'latest'/'bin'/('sdkmanager.bat' if os.name=='nt' else 'sdkmanager')
    if not manager.is_file():
        folder=ROOT/'.setup'/'android-downloads';folder.mkdir(parents=True,exist_ok=True)
        name,sha=DOWNLOADS[system];archive=folder/name
        print('Scaricamento SDK ufficiale Google, controllo SHA-256...')
        fetch_checked('https://dl.google.com/android/repository/'+name,archive,sha)
        unpack=folder/'unpacked'
        if unpack.exists():shutil.rmtree(unpack)
        safe_extract(archive,unpack)
        manager.parent.parent.parent.mkdir(parents=True,exist_ok=True)
        if manager.parent.parent.exists():shutil.rmtree(manager.parent.parent)
        shutil.move(str(unpack/'cmdline-tools'),str(manager.parent.parent))
        if os.name!='nt':
            for f in manager.parent.iterdir():f.chmod(0o755)
    print('Leggi le licenze Android SDK qui sotto e accetta soltanto se d\'accordo. Non rispondiamo automaticamente.')
    run([manager,'--sdk_root='+str(path),'--licenses'],env)
    run([manager,'--sdk_root='+str(path),'platforms;android-35','build-tools;35.0.0','platform-tools'],env)
    if not platform.is_file():raise RuntimeError('Installazione SDK non completata')
    return path


def build(args):
    try:
        home=jdk()
    except RuntimeError:
        if os.name!='nt' or not args.install_sdk or not shutil.which('winget'): raise
        answer=input('JDK mancante. Installare Microsoft OpenJDK 21 con winget? [s/N] ').strip().lower()
        if answer not in ('s','si'): raise RuntimeError('Installazione JDK non autorizzata. Nessuna build eseguita.')
        run(['winget','install','--id','Microsoft.OpenJDK.21','--exact','--source','winget'])
        home=jdk()
    env=os.environ.copy();env['JAVA_HOME']=str(home);env['PATH']=str(home/'bin')+os.pathsep+env.get('PATH','')
    sdk=prepare_sdk(args.sdk,args.install_sdk,env)
    tools=sdk/'build-tools'/'35.0.0';jar=sdk/'platforms'/'android-35'/'android.jar'
    exe='.exe' if os.name=='nt' else '';bat='.bat' if os.name=='nt' else ''
    out=ROOT/'android-build';out.mkdir(exist_ok=True)
    for name in ['generated','classes','dex']:
        d=out/name
        if d.exists():shutil.rmtree(d)
        d.mkdir()
    for f in ['player.html','physical_boot.js','branding.js','favicon.svg']:shutil.copy2(ROOT/f,SOURCE/'assets'/f)
    compiled=out/'resources.zip';compiled.unlink(missing_ok=True)
    run([tools/('aapt2'+exe),'compile','--dir',SOURCE/'res','-o',compiled],env)
    unsigned=out/'unsigned.apk'
    run([tools/('aapt2'+exe),'link','-o',unsigned,'-I',jar,'--manifest',SOURCE/'AndroidManifest.xml','-A',SOURCE/'assets','--java',out/'generated',compiled],env)
    files=list((SOURCE/'src').rglob('*.java'))+list((out/'generated').rglob('*.java'))
    run([home/'bin'/('javac'+exe),'-encoding','UTF-8','-source','8','-target','8','-classpath',jar,'-d',out/'classes']+files,env)
    classes=out/'classes.jar';run([home/'bin'/('jar'+exe),'cf',classes,'-C',out/'classes','.'],env)
    run([tools/('d8'+bat),'--lib',jar,'--min-api','26','--output',out/'dex',classes],env)
    with zipfile.ZipFile(unsigned,'a',compression=zipfile.ZIP_DEFLATED) as z:
        for f in (out/'dex').glob('*.dex'):z.write(f,f.name)
    aligned=out/'aligned.apk';run([tools/('zipalign'+exe),'-f','4',unsigned,aligned],env)
    keys=ROOT/'data'/'android-signing';keys.mkdir(parents=True,exist_ok=True)
    key=keys/'carisma.jks';password=keys/'password.txt'
    if not key.exists():
        import secrets
        password.write_text(secrets.token_urlsafe(32),encoding='utf-8');password.chmod(0o600)
        run([home/'bin'/('keytool'+exe),'-genkeypair','-keystore',key,'-storepass:file',password,'-keypass:file',password,'-alias','carisma','-keyalg','RSA','-keysize','3072','-validity','3650','-dname','CN=Carisma Local Player','-storetype','JKS'],env)
    if not password.exists():raise RuntimeError('Manca la password della chiave locale. Ripristina il backup, non generare una chiave diversa per aggiornare un APK esistente.')
    apk=out/'DisplayControl_Player_TV_v0.11.0-alpha.apk'
    # The generated key uses the store password; reading the same file twice consumes two lines.
    run([tools/('apksigner'+bat),'sign','--ks',key,'--ks-key-alias','carisma','--ks-pass','file:'+str(password),'--out',apk,aligned],env)
    run([tools/('apksigner'+bat),'verify','--verbose','--print-certs',apk],env)
    sha=hashlib.sha256(apk.read_bytes()).hexdigest();(out/'SHA256.txt').write_text(sha+'  '+apk.name+'\n',encoding='ascii')
    (ROOT/'.setup').mkdir(exist_ok=True);(ROOT/'.setup'/'android-sdk-path.txt').write_text(str(sdk),encoding='utf-8')
    print('\nAPK COMPILATO E FIRMA VERIFICATA: '+str(apk))
    print('Questo NON certifica avvio o riproduzione su Chromecast. Esegui il collaudo fisico della guida.')
    print('Conserva privatamente data/android-signing per gli aggiornamenti futuri. Non condividerla.')


def main():
    parser=argparse.ArgumentParser()
    default=os.environ.get('ANDROID_HOME') or os.environ.get('ANDROID_SDK_ROOT') or str(ROOT/'.setup'/'android-sdk')
    parser.add_argument('--sdk',default=default);parser.add_argument('--install-sdk',action='store_true')
    args=parser.parse_args()
    try:build(args);return 0
    except (OSError,ValueError,RuntimeError,subprocess.CalledProcessError,zipfile.BadZipFile) as e:
        print('\nBUILD NON COMPLETATA: '+str(e));return 1
if __name__=='__main__':sys.exit(main())
