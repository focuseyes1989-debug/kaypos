"""Phase 8 release identity, build-manifest and smoke checks."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from native_pos.release import metadata, distribution_manifest
from build_native_pos import build_arguments, source_state


class NativeReleaseTests(unittest.TestCase):
    def test_metadata_identity_and_invalid_files(self):
        self.assertEqual(metadata()['version'],'0.8.0')
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'version.json'
            for value in ({}, {'product':'KAY POS Native','version':'bad','release_channel':'phase8-preview','minimum_display':'1366x768','server_api':'native-v1'}):
                path.write_text(json.dumps(value),encoding='utf-8')
                with self.assertRaises(ValueError):metadata(path)

    def test_build_arguments_keep_separate_output_identity(self):
        root=Path(__file__).resolve().parents[1];args=build_arguments(root)
        self.assertIn('KAY_POS_Native',args);self.assertIn('--windowed',args);self.assertIn('--onedir',args);self.assertIn('--clean',args)
        self.assertIn(str(root/'native_version.txt'),args);self.assertNotIn('ZAY_POS.exe',args)
        self.assertIn('--add-binary',args)
        self.assertTrue(any('Qt6' in value and value.endswith('*.dll;.') for value in args))

    def test_distribution_manifest_hash_and_missing_assets(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);internal=root/'_internal';(internal/'assets/kay').mkdir(parents=True)
            (root/'KAY_POS_Native.exe').write_bytes(b'exe fixture');(internal/'assets/kay/kay_multi.ico').write_bytes(b'ico')
            (internal/'native_version.json').write_text(Path('native_version.json').read_text(encoding='utf-8'),encoding='utf-8')
            result=distribution_manifest(root,'abc123',False)
            self.assertEqual(result['executable_size'],11);self.assertEqual(len(result['executable_sha256']),64)
            self.assertEqual(result['source_revision'],'abc123');self.assertFalse(result['source_dirty'])
            (internal/'native_version.json').unlink()
            with self.assertRaisesRegex(ValueError,'incomplete'):distribution_manifest(root)

    def test_source_state_failure_is_explicit(self):
        with patch('build_native_pos.subprocess.run',side_effect=OSError('git missing')):
            self.assertEqual(source_state(Path('.')),('unknown',True))


if __name__=='__main__':unittest.main()
