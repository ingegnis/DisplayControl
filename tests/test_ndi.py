"""Unit/integration tests without a physical NDI sender.
Fake ABI tests do NOT certify compatibility with the licensed runtime / network.
"""
import ctypes as C
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
import unittest
from ndi.native import VideoFrame, AudioFrame, copy_video, copy_audio, fourcc, Runtime, NDIError
from ndi.gateway import Gateway, GatewayError, parse_playlist, codec_string
from ndi_fixture import compiler_available, build_fixture
ROOT=Path(__file__).resolve().parents[1]

class BufferTests(unittest.TestCase):
    def test_video_stride_and_format(self):
        buf=C.create_string_buffer(bytes(range(24)))
        f=VideoFrame();f.width=2;f.height=2;f.fourcc=fourcc('BGRX');f.stride=12;f.data=C.addressof(buf)
        data,w,h,fmt=copy_video(f)
        self.assertEqual(data,bytes(range(8))+bytes(range(12,20)))
        self.assertEqual((w,h,fmt),(2,2,'bgr0'))
        f.stride=3
        with self.assertRaises(NDIError):copy_video(f)
    def test_audio_interleaving(self):
        buf=(C.c_float*4)(.1,.2,.3,.4)
        f=AudioFrame();f.sample_rate=48000;f.channels=2;f.samples=2;f.data=C.addressof(buf);f.stride=8
        out=(C.c_float*4).from_buffer_copy(copy_audio(f,2))
        for actual,expected in zip(out,[.1,.3,.2,.4]):self.assertAlmostEqual(actual,expected,places=5)
    def test_64_bit_layout(self):
        self.assertEqual(C.sizeof(VideoFrame),72)
        self.assertEqual(C.sizeof(AudioFrame),56)
    def test_playlist_validation(self):
        text='#EXT-X-MEDIA-SEQUENCE:9\n#EXTINF:1.0,\nseg_000000009.m4s\n'
        self.assertEqual(parse_playlist(text)[0]['sequence'],9)
        with self.assertRaises(GatewayError):parse_playlist(text.replace('seg_000000009.m4s','../../secret'))
    def test_missing_runtime(self):
        r=Runtime(ROOT,library='/nonexistent/carisma-test.so')
        self.assertFalse(r.status()['available'])
        with self.assertRaises(NDIError):r.sources()

@unittest.skipUnless(shutil.which('ffmpeg'),'FFmpeg required')
class GatewayTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.g=Gateway(ROOT,Path(self.temp.name),library='/nonexistent/carisma-test.so',max_streams=1)
    def tearDown(self):
        self.g.close();self.temp.cleanup()
    def wait_ready(self,key,timeout=12):
        end=time.monotonic()+timeout
        while time.monotonic()<end:
            m=self.g.get(key).manifest()
            if m.get('ready') and m['healthy']:return m
            time.sleep(.2)
        self.fail('Gateway did not become ready: '+str(self.g.get(key).status()))
    def test_testpattern_shared_and_security(self):
        a=self.g.start({'test':True,'profile':'light'})
        b=self.g.start({'test':True,'profile':'light'})
        self.assertEqual(a['id'],b['id'])
        m=self.wait_ready(a['id'])
        self.assertIn('avc1.',m['mime'])
        self.assertIn('mp4a.40.2',m['mime'])
        init=self.g.media(a['id'],m['generation'],'init.mp4')
        self.assertEqual(codec_string(init),m['mime'])
        with self.assertRaises(GatewayError):self.g.media(a['id'],m['generation'],'../../access.key')
        with self.assertRaises(GatewayError):self.g.start({'test':True,'profile':'standard'})
        s=self.g.get(a['id']);s._test_paused=True;s.last_frame_at=time.monotonic()-5
        self.assertFalse(s.manifest()['healthy'])
        self.g.stop(a['id'])
        with self.assertRaises(GatewayError):self.g.get(a['id'])
    def test_input_validation_and_runtime_failure(self):
        for body in [{},{'sourceName':'x','profile':'injected'},{'sourceName':'x\0y'}]:
            with self.assertRaises(GatewayError):self.g.start(body)
        with self.assertRaises(GatewayError) as e:self.g.start({'sourceName':'Missing (NDI)'})
        self.assertEqual(e.exception.status,503)

@unittest.skipUnless(compiler_available() and shutil.which('ffmpeg'),'C compiler and FFmpeg required')
class FakeABITests(unittest.TestCase):
    def test_native_binding_and_encoder(self):
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder);lib=build_fixture(p)
            import sys
            r=subprocess.run([sys.executable,str(ROOT/'tests/fake_ndi_check.py'),str(lib),str(p)],
                             capture_output=True,text=True,timeout=65)
            self.assertEqual(r.returncode,0,r.stdout+'\n'+r.stderr)

if __name__=='__main__':unittest.main()
