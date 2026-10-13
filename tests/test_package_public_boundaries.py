"""Independent privacy/instruction boundaries for generated release archives."""
import pathlib
import sys
import tempfile
import unittest

PROJECT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / 'tools'))
from build_release import _collect
from build_toolkit import _reviewed


class PublicPackageBoundaryTests(unittest.TestCase):
    def test_developer_instructions_are_not_release_payload(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            for name in ('AGENTS.md','CLAUDE.md','safe.py'):
                (root/name).write_text('pass\n',encoding='utf-8')
            (root/'.claude').mkdir()
            (root/'.claude/settings.json').write_text('{}',encoding='utf-8')
            entries = _collect(root,source_files=['AGENTS.md','CLAUDE.md','safe.py','.claude/settings.json'])
            self.assertEqual([entry['path'] for entry in entries],['safe.py'])
            entries = _reviewed(root,vendor=False)
            self.assertEqual([entry['path'] for entry in entries],['safe.py'])

    def test_generic_private_paths_reject_plain_and_escaped_text(self):
        # Independently invented paths, neither author identity nor real source material.
        for value in ('C:/Users/example/work/source.py','D:/workspace-example/source.py',
                      '/home/example/work/source.py',r'C:\\Users\\example\\work\\source.py'):
            with self.subTest(value_kind='invented-private-location'), tempfile.TemporaryDirectory() as directory:
                root = pathlib.Path(directory)
                (root/'README.md').write_text(value,encoding='utf-8')
                with self.assertRaisesRegex(ValueError,'Private absolute development path'):
                    _reviewed(root,vendor=False)

    def test_documented_system_discovery_paths_are_permitted(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            (root/'README.md').write_text('C:/Program Files/app/app.exe\nC:/Windows/System32/cmd.exe\nC:/Tools/cas-offinder.exe\n'
                + r'C:\Python*\Lib\site-packages\primer3\primer3_core.exe' + '\n'
                + r'D:\Anaconda3\envs\*\primer3_core.exe' + '\n'
                + r'C:\Users\...\<Chinese>\program.exe' + '\n'
                + r'Type:\s*(GPU|CPU),\s*ID:\s*(\d+)',encoding='utf-8')
            self.assertEqual([entry['path'] for entry in _reviewed(root,vendor=False)],['README.md'])


if __name__ == '__main__':
    unittest.main()
