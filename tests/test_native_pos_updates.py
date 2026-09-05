import unittest
from unittest.mock import patch, PropertyMock
from PyQt6.QtWidgets import QApplication
from native_pos.updates import version_status, check_release, UpdateCheckDialog


class UpdateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.app = QApplication.instance() or QApplication([])

    def test_version_order_and_unknown(self):
        self.assertIn('newer', version_status('1.2.0', '1.10.0'))
        self.assertIn('ahead', version_status('2.0.0', '1.9.0'))
        self.assertIn('match', version_status('v1.0.0', '1.0.0'))
        self.assertIn('unavailable', version_status('unknown', '1.0.0'))
        self.assertIn('unavailable', version_status('1.0.0', '1.1.0-beta'))

    def test_shared_metadata_source_without_downloading(self):
        with patch('launcher.current_version', return_value='1.0.0'), patch('launcher.fetch_latest_update', return_value=dict(version='1.1.0', release_notes='Notes', download_url='https://unused.invalid/app.exe')) as fetch:
            result = check_release(); fetch.assert_called_once()
        self.assertEqual(result['local'], '1.0.0'); self.assertEqual(result['notes'], 'Notes')
        self.assertNotIn('download_url', result)
        with patch('launcher.fetch_latest_update', return_value={'version': ''}):
            with self.assertRaises(ValueError): check_release()

    def test_explicit_check_busy_guard_and_plain_notes(self):
        dialog = UpdateCheckDialog(); self.addCleanup(dialog.deleteLater)
        with patch.object(dialog.runner, 'start') as start:
            self.assertFalse(start.called)
            dialog.refresh(); start.assert_called_once()
        dialog.received(dict(local='1.0.0', published='1.1.0', status='Newer', source='fixture', notes='<script>not executed</script>'))
        self.assertIn('<script>', dialog.details.toPlainText())
        with patch.object(type(dialog.runner), 'busy', new_callable=PropertyMock, return_value=True):
            with patch.object(dialog.runner, 'start') as start: dialog.refresh(); start.assert_not_called()
            dialog.update_enabled(); self.assertFalse(dialog.check.isEnabled())
        dialog.reject()
        self.assertLessEqual(dialog.sizeHint().height(), 728)
