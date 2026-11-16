"""Build our fake C ABI with GCC or the installed Windows Visual C compiler."""
import os
from pathlib import Path
import shutil
import subprocess

ROOT=Path(__file__).resolve().parents[1]
def visual_cpp_environment():
    for key,default in [('ProgramFiles(x86)','C:/Program Files (x86)'),('ProgramFiles','C:/Program Files')]:
        root=Path(os.environ.get(key,default))/'Microsoft Visual Studio'
        found=sorted(root.glob('*/*/VC/Auxiliary/Build/vcvars64.bat'),reverse=True)
        if found:return found[0]
    return Path('visual-cpp-not-installed')

VARS=visual_cpp_environment()

def compiler_available():
    return bool(shutil.which('gcc') or (os.name=='nt' and VARS.is_file()))

def build_fixture(folder):
    folder=Path(folder)
    lib=folder/('fake.dll' if os.name=='nt' else 'fake.so')
    if shutil.which('gcc'):
        subprocess.run(['gcc','-shared','-fPIC',str(ROOT/'tests/fake_ndi.c'),'-o',str(lib),'-lm'],check=True,capture_output=True)
    else:
        # Initialize compiler environment with vcvars; change no system settings.
        setup=folder/'compiler_env.cmd'
        setup.write_text('@echo off\ncall "'+str(VARS)+'" >nul\nif errorlevel 1 exit /b 1\nset\n')
        result=subprocess.run(['cmd','/d','/c',str(setup)],capture_output=True,text=True,check=True)
        env={k.upper():v for k,v in os.environ.items()}
        for line in result.stdout.splitlines():
            if '=' in line and not line.startswith('='):
                key,value=line.split('=',1);env[key.upper()]=value
        compiler=shutil.which('cl',path=env.get('PATH'))
        if not compiler:raise RuntimeError('Visual C compiler not found after vcvars64')
        subprocess.run([compiler,'/nologo','/LD','/std:c11',str(ROOT/'tests/fake_ndi.c'),'/link','/OUT:'+str(lib)],
                       env=env,cwd=folder,check=True,capture_output=True)
    return lib
