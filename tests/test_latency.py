"""Latency policy + real FFmpeg fragments; no physical NDI measurement."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from ndi.gateway import Gateway, Stream, PROFILES, playback_policy, keyframe_interval
ROOT=Path(__file__).resolve().parents[1]

class LatencyPolicyTests(unittest.TestCase):
    def test_default_is_responsive(self):
        with patch.dict(os.environ, {}, clear=True):
            p=playback_policy();self.assertEqual(p['mode'],'responsive')
            self.assertEqual(p['targetBufferSeconds'],.75)
    def test_environment_and_explicit_override(self):
        with patch.dict(os.environ, {'CARISMA_LIVE_MODE':'stable'}):
            self.assertEqual(playback_policy()['mode'],'stable')
            self.assertEqual(playback_policy('responsive')['mode'],'responsive')
    def test_invalid_mode_fails(self):
        for mode in ['fastest','', 'responsive --shell']:
            with self.assertRaises(ValueError):playback_policy(mode)
    def test_policy_copies_do_not_mutate_global(self):
        p=playback_policy('responsive');p['pollMs']=0
        self.assertEqual(playback_policy('responsive')['pollMs'],100)
    def test_keyframes_rounded_up_at_each_fps(self):
        for name,p in PROFILES.items():
            interval=keyframe_interval(name,playback_policy('responsive'))/p['fps']
            self.assertGreaterEqual(interval,.5);self.assertLess(interval,.6)
    def test_responsive_encoder_arguments(self):
        for name in PROFILES:
            stream=Stream(SimpleNamespace(playback=playback_policy('responsive')),'0'*16,'test',name,True)
            args=stream.output_args()
            self.assertEqual(args[args.index('-hls_time')+1],'0.5')
            self.assertEqual(args[args.index('-g')+1],str(keyframe_interval(name,stream.playback)))
            self.assertIn('zerolatency',args);self.assertEqual(args[args.index('-bf')+1],'0')
    def test_stable_encoder_arguments(self):
        stream=Stream(SimpleNamespace(playback=playback_policy('stable')),'0'*16,'test','light',True)
        args=stream.output_args()
        self.assertEqual(args[args.index('-hls_time')+1],'1.0')
        self.assertEqual(args[args.index('-g')+1],'15')

@unittest.skipUnless(shutil.which('ffmpeg') and shutil.which('ffprobe'),'FFmpeg/ffprobe required')
class RealFragmentTests(unittest.TestCase):
    def check_profile(self,profile,mode):
        with tempfile.TemporaryDirectory() as d:
            g=Gateway(ROOT,Path(d),library='/nonexistent/carisma-test.so',live_mode=mode)
            try:
                stream=g.start({'test':True,'profile':profile});s=g.get(stream['id'])
                until=time.monotonic()+15
                while time.monotonic()<until:
                    m=s.manifest()
                    if m.get('ready') and m['healthy'] and len(m['segments'])>=4:break
                    time.sleep(.1)
                self.assertTrue(m.get('ready'),m)
                self.assertEqual(m['playback']['mode'],mode)
                segments=m['segments'][-3:]
                expected=m['segmentNominalSeconds']
                for item in segments:
                    self.assertAlmostEqual(item['duration'],expected,places=4)
                    # Each fragment starts with a decodable keyframe.
                    temp=Path(d)/'fragment.mp4'
                    temp.write_bytes((s.folder/'init.mp4').read_bytes()+(s.folder/item['name']).read_bytes())
                    r=subprocess.run(['ffprobe','-v','error','-select_streams','v:0','-show_frames','-of','json',str(temp)],capture_output=True,text=True,timeout=8)
                    self.assertEqual(r.returncode,0,r.stderr)
                    frames=json.loads(r.stdout)['frames'];self.assertTrue(frames)
                    self.assertEqual(frames[0]['key_frame'],1)
                # Decode adjacent AV fragments together.
                combined=Path(d)/'combined.mp4'
                combined.write_bytes((s.folder/'init.mp4').read_bytes()+b''.join((s.folder/x['name']).read_bytes() for x in segments))
                r=subprocess.run(['ffmpeg','-v','error','-i',str(combined),'-f','null','-'],capture_output=True,timeout=10)
                self.assertEqual(r.returncode,0,r.stderr.decode(errors='replace'))
                # Keep standard HLS metadata valid alongside the JSON manifest.
                text=(s.folder/'stream.m3u8').read_text()
                duration=int(next(x.split(':')[1] for x in text.splitlines() if x.startswith('#EXT-X-TARGETDURATION:')))
                self.assertGreaterEqual(duration,1)
            finally:g.close()
    def test_responsive_360p(self):self.check_profile('light','responsive')
    def test_responsive_720p(self):self.check_profile('standard','responsive')
    def test_stable_360p(self):self.check_profile('light','stable')

if __name__=='__main__':unittest.main()
