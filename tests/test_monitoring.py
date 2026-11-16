"""Real HTTP permission tests and bounded thumbnail store tests. No NDI hardware."""
import base64
import copy
from pathlib import Path
import unittest
from monitoring import MonitorStore, jpeg_size
from ndi.gateway import GatewayError
import test_physical_players as helper

JPEG=(Path(__file__).parent/'fixtures/monitor.jpg').read_bytes()
ENCODED=base64.b64encode(JPEG).decode()
def report(sid='screen-a'):
    return dict(screenId=sid,jpeg=ENCODED,kind='frame',title='TEST / NON NDI',revision=1,mediaTime=2.1,bufferSeconds=.7)

class MonitorStoreTests(unittest.TestCase):
    def setUp(self):
        self.t=100.; self.store=MonitorStore(clock=lambda:self.t,wall=lambda:self.t+1000)
    def test_idle_no_images_collected(self):
        self.assertFalse(self.store.receive('screen-a',report())['stored'])
        self.assertEqual(self.store.frames,{})
    def test_watch_lease_expires(self):
        self.store.watch('viewer-001',2);self.assertTrue(self.store.policy()['enabled'])
        self.t+=12.1;self.assertFalse(self.store.policy()['enabled'])
    def test_multiple_viewers_minimum_interval_and_stop(self):
        self.store.watch('viewer-001',5);self.store.watch('viewer-002',1)
        self.assertEqual(self.store.policy()['interval'],1)
        self.store.stop('viewer-002');self.assertEqual(self.store.policy()['interval'],5)
        self.store.stop('viewer-001');self.assertFalse(self.store.policy()['enabled'])
    def test_invalid_viewer_interval_and_cap(self):
        for v,i in [('',2),('../../file',1),('viewer-001',.1),('viewer-001',9)]:
            with self.assertRaises(GatewayError):self.store.watch(v,i)
        for i in range(32):self.store.watch('viewer-'+str(i).zfill(3),2)
        with self.assertRaises(GatewayError):self.store.watch('viewer-overflow',2)
    def test_jpeg_validation_dimensions(self):
        self.assertEqual(jpeg_size(JPEG),(480,270))
        with self.assertRaises(GatewayError):jpeg_size(b'<svg onload=alert(1)>')
        with self.assertRaises(GatewayError):jpeg_size(JPEG[:24])
        bad=bytearray(JPEG);start=bad.index(b'\xff\xc0');bad[start+7:start+9]=(4096).to_bytes(2,'big')
        with self.assertRaises(GatewayError):jpeg_size(bytes(bad))
    def test_one_last_frame_only_no_raw_in_overview(self):
        self.store.watch('viewer-001',1);self.store.receive('screen-a',report());self.t+=1
        self.store.receive('screen-a',dict(report(),title='Nuovo'))
        self.assertEqual(len(self.store.frames),1)
        result=self.store.overview({'screens':[{'id':'screen-a'}]},1,{})
        self.assertNotIn('jpeg',result['screens'][0]['preview'])
        self.assertEqual(result['screens'][0]['preview']['title'],'Nuovo')
        self.assertEqual(self.store.frame('screen-a')[0],JPEG)
    def test_upload_rate_limit(self):
        self.store.watch('viewer-001',1);self.store.receive('screen-a',report())
        with self.assertRaises(GatewayError) as e:self.store.receive('screen-a',report())
        self.assertEqual(e.exception.status,429)
    def test_invalid_payload_rejected_and_numbers_finite(self):
        self.store.watch('viewer-001',1)
        for bad in [dict(jpeg='%%%'),dict(kind='script'),dict(jpeg='a'*100000),dict(jpeg='')]:
            with self.assertRaises(GatewayError):self.store.receive('screen-a',dict(report(),**bad))
        self.store.receive('screen-a',dict(report(),bufferSeconds=float('inf'),mediaTime='bad'))
        self.assertIsNone(self.store.frames['screen-a']['bufferSeconds'])
    def test_unavailable_clears_old_frame(self):
        self.store.watch('viewer-001',1);self.store.receive('screen-a',report());self.t+=1
        self.store.receive('screen-a',dict(report(),kind='unavailable',jpeg='',error='CORS'))
        with self.assertRaises(GatewayError):self.store.frame('screen-a')
    def test_deleted_screen_is_removed(self):
        self.store.watch('viewer-001',1);self.store.receive('screen-a',report())
        self.store.overview({'screens':[]},1,{});self.assertEqual(self.store.frames,{})

class MonitorApiTests(unittest.TestCase):
    # Reuse setup helpers, excluding inherited tests.
    setUp=helper.PhysicalPlayerTests.setUp
    tearDown=helper.PhysicalPlayerTests.tearDown
    call=helper.PhysicalPlayerTests.call
    jsoncall=helper.PhysicalPlayerTests.jsoncall
    publish=helper.PhysicalPlayerTests.publish
    code=helper.PhysicalPlayerTests.code
    pair=helper.PhysicalPlayerTests.pair
    def watch(self,i=2):return self.jsoncall('/api/monitor?viewer=api-test-viewer&interval='+str(i))
    def test_shell_public_data_private(self):
        self.assertEqual(self.call('/monitor.html',admin=False)[0],200)
        self.assertEqual(self.call('/api/monitor?viewer=api-test-viewer',admin=False)[0],401)
        token=self.pair()
        self.assertEqual(self.call('/api/monitor?viewer=api-test-viewer',player=token,admin=False)[0],401)
    def test_heartbeat_announces_demand_and_stops(self):
        token=self.pair();body=dict(screenId=self.sid)
        self.assertFalse(self.jsoncall('/api/player/heartbeat','POST',body,player=token,admin=False)[1]['monitor']['enabled'])
        self.watch(1)
        self.assertEqual(self.jsoncall('/api/player/heartbeat','POST',body,player=token,admin=False)[1]['monitor']['interval'],1)
        self.call('/api/monitor/stop','POST',{'viewer':'api-test-viewer'})
        self.assertFalse(self.jsoncall('/api/player/heartbeat','POST',body,player=token,admin=False)[1]['monitor']['enabled'])
    def test_upload_read_frame_and_metadata(self):
        token=self.pair();self.watch()
        self.assertEqual(self.call('/api/player/preview','POST',report(self.sid),player=token,admin=False)[0],200)
        status,data=self.watch();self.assertEqual(status,200)
        preview=next(s for s in data['screens'] if s['id']==self.sid)['preview']
        self.assertEqual(preview['kind'],'frame');self.assertNotIn('jpeg',preview)
        self.assertEqual(self.call('/api/monitor/frame/'+self.sid)[1],JPEG)
        self.assertEqual(self.call('/api/monitor/frame/'+self.sid,admin=False)[0],401)
    def test_cross_player_upload_read_forbidden(self):
        token=self.pair();self.watch();other=self.project['screens'][1]['id']
        self.assertEqual(self.call('/api/player/preview','POST',report(other),player=token,admin=False)[0],403)
        self.assertEqual(self.call('/api/player/monitor',player=token,admin=False)[0],403)
    def test_revoke_drops_snapshot_and_rejects_future_upload(self):
        token=self.pair();self.watch();self.call('/api/player/preview','POST',report(self.sid),player=token,admin=False)
        self.call('/api/devices/revoke','POST',{'screenId':self.sid})
        self.assertEqual(self.call('/api/monitor/frame/'+self.sid)[0],404)
        self.assertEqual(self.call('/api/player/preview','POST',report(self.sid),player=token,admin=False)[0],401)
    def test_legacy_admin_player_and_bad_interval(self):
        self.assertEqual(self.watch(4)[0],400)
        self.watch(5)
        reply=self.jsoncall('/api/heartbeat','POST',{'screenId':self.sid})[1]
        self.assertEqual(reply['monitor']['interval'],5)
        self.assertEqual(self.call('/api/preview','POST',report(self.sid))[0],200)
        self.assertEqual(self.call('/api/preview','POST',report('missing-screen'))[0],410)
    def test_deleted_screen_frame_not_leaked(self):
        self.watch();self.call('/api/preview','POST',report(self.sid))
        self.project['screens']=[x for x in self.project['screens'] if x['id']!=self.sid];self.publish(self.project)
        self.assertEqual(self.call('/api/monitor/frame/'+self.sid)[0],410)
    def test_no_device_secret_in_monitor_response(self):
        token=self.pair();status,data=self.watch()
        self.assertEqual(status,200)
        self.assertNotIn(token,str(data));self.assertNotIn(self.admin,str(data))

if __name__=='__main__':unittest.main()
