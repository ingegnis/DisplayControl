"""Isolated process: release the fake Windows DLL before temporary cleanup."""
import os
from pathlib import Path
import subprocess
import sys
import time
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from ndi.gateway import Gateway


def run(library, folder):
    folder=Path(folder);signal=folder/'signal.txt';signal.write_text('1')
    os.environ['CARISMA_FAKE_SIGNAL_FILE']=str(signal)
    g=Gateway(ROOT,folder,library=library)
    try:
        assert g.sources()['sources'][0]['name']=='CARISMA TEST (ABI NON NDI)'
        started=g.start({'sourceName':'CARISMA TEST (ABI NON NDI)'})
        stream=g.get(started['id'])
        def wait(check,timeout=18):
            until=time.monotonic()+timeout
            trace=[];next_trace=0
            while time.monotonic()<until:
                m=stream.manifest()
                if check(m):return m
                if time.monotonic()>next_trace:
                    trace.append({k:m.get(k) for k in ['stage','frames','restarts','error','healthy']});next_trace=time.monotonic()+2
                time.sleep(.15)
            raise AssertionError(str(stream.status())+'\n'+str(trace)+'\n'+stream.error_tail())
        m=wait(lambda m:m.get('ready') and m['healthy'] and m['frames']>=120 and len(m.get('segments',[]))>=4)
        assert m['frames']>5
        # Decode a bounded capture, rather than following an open-ended live playlist.
        combined=folder/'abi-capture.mp4'
        combined.write_bytes((stream.folder/'init.mp4').read_bytes()+b''.join((stream.folder/x['name']).read_bytes() for x in m['segments'][-3:]))
        decoded=subprocess.run(['ffmpeg','-v','error','-i',str(combined),'-f','null','-'],capture_output=True,timeout=15)
        assert decoded.returncode==0,decoded.stderr.decode(errors='replace')
        signal.write_text('0');wait(lambda m:not m['healthy'],timeout=10)
        signal.write_text('1');wait(lambda m:m.get('ready') and m['healthy'],timeout=18)
        print('Fake ABI: receive, video/audio decode, signal loss and recovery passed. NOT physical NDI.')
    finally:g.close()

if __name__=='__main__':run(sys.argv[1],sys.argv[2])
