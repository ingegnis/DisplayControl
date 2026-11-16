import unittest
from unittest.mock import patch
import setup_ndi

class LANLauncherTests(unittest.TestCase):
    def test_lan_is_explicit_and_preserves_dependency_settings(self):
        with patch.object(setup_ndi,'apply_settings') as settings,patch.object(setup_ndi.subprocess,'call',return_value=0) as call:
            self.assertEqual(setup_ndi.main(['launch-lan']),0)
            settings.assert_called_once()
            args=call.call_args.args[0]
            self.assertIn('--host',args);self.assertIn('0.0.0.0',args)
    def test_default_launch_still_loopback_only(self):
        with patch.object(setup_ndi,'apply_settings'),patch.object(setup_ndi.subprocess,'call',return_value=0) as call:
            self.assertEqual(setup_ndi.main(['launch']),0)
            self.assertNotIn('--host',call.call_args.args[0])
