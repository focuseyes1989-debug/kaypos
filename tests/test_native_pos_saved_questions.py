import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from PyQt6.QtWidgets import QApplication, QMessageBox
from native_pos.saved_questions import QuestionStore, SavedQuestionsDialog


class SavedQuestionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_encrypted_roundtrip_and_scopes(self):
        with tempfile.TemporaryDirectory() as folder:
            store = QuestionStore(folder, 'server/user1')
            rows = [dict(name='Today', query='today sales')]
            store.write(rows)
            self.assertEqual(store.read(), rows)
            self.assertNotIn(b'today sales', store.path.read_bytes())
            self.assertEqual(QuestionStore(folder, 'server/user2').read(), [])
            self.assertEqual(QuestionStore(folder, 'other-server/user1').read(), [])
            original = store.path.read_bytes()
            with patch('native_pos.saved_questions.os.replace', side_effect=OSError('disk failure')):
                with self.assertRaises(OSError): store.write([])
            self.assertEqual(store.path.read_bytes(), original)
            stale = QuestionStore(folder, 'server/user1'); stale.read()
            store.write([])
            with self.assertRaisesRegex(ValueError, 'another window'): stale.write(rows)

    def test_validation_and_corrupt_file_preserved(self):
        with tempfile.TemporaryDirectory() as folder:
            store = QuestionStore(folder, 'user')
            for rows in ([dict(name='', query='sales')], [dict(name='a', query='x'*1001)], [dict(name='a', query='sales'), dict(name='A', query='stock')]):
                with self.assertRaises(ValueError): store.write(rows)
            store.path.write_bytes(b'broken')
            with self.assertRaises(ValueError): store.read()
            self.assertEqual(store.path.read_bytes(), b'broken')

    def test_save_edit_load_delete(self):
        with tempfile.TemporaryDirectory() as folder:
            store = QuestionStore(folder, 'user')
            dialog = SavedQuestionsDialog(store, 'today sales'); self.addCleanup(dialog.deleteLater)
            dialog.name.setText('Daily'); dialog.save()
            dialog.query.setPlainText('yesterday sales'); dialog.save()
            self.assertEqual(len(store.read()), 1)
            dialog.load(); self.assertEqual(dialog.chosen, 'yesterday sales')
            with patch('native_pos.saved_questions.QMessageBox.question', return_value=QMessageBox.StandardButton.Yes): dialog.delete()
            self.assertEqual(store.read(), [])
            self.assertLessEqual(dialog.sizeHint().height(), 728)
