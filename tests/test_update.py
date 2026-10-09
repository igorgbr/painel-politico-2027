import argparse
import fcntl
import importlib.util
import os
from pathlib import Path
import sqlite3
import subprocess
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('update_script', Path(__file__).resolve().parents[1] / 'scripts/update.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class UpdateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / 'var').mkdir()
        self.db = self.root / 'var/painel.sqlite3'
        with sqlite3.connect(self.db) as connection:
            connection.execute('CREATE TABLE evidence(value TEXT)')
            connection.execute("INSERT INTO evidence VALUES ('preserved')")
        self.args = argparse.Namespace(history_end='2026-10-05', expenses_end='2026-09-30')

    def test_backup_precedes_collectors_and_first_failure_stops(self):
        def fail(command, **kwargs):
            backups = list((self.root / 'var/backups').glob('*.sqlite3'))
            self.assertEqual(len(backups), 1)
            with sqlite3.connect(backups[0]) as connection:
                self.assertEqual(connection.execute('SELECT value FROM evidence').fetchone()[0], 'preserved')
            self.assertEqual(backups[0].stat().st_mode & 0o777, 0o600)
            self.assertNotIn('CLOUDFLARE_API_TOKEN', kwargs['env'])
            raise subprocess.CalledProcessError(7, command)
        with patch.dict(os.environ, {'CLOUDFLARE_API_TOKEN': 'test-only'}), patch.object(module.subprocess, 'run', side_effect=fail) as run:
            with self.assertRaises(subprocess.CalledProcessError):
                module.update(self.args, self.root)
            self.assertEqual(run.call_count, 1)

    def test_missing_or_locked_database_never_starts_collection(self):
        with patch.object(module.subprocess, 'run') as run:
            with Path(str(self.db) + '.lock').open('a') as lock:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                with self.assertRaises(BlockingIOError):
                    module.update(self.args, self.root)
            self.db.unlink()
            with self.assertRaises(ValueError):
                module.update(self.args, self.root)
            run.assert_not_called()

    def test_complete_sequence_has_no_deploy(self):
        with patch.object(module.subprocess, 'run') as run:
            module.update(self.args, self.root)
            self.assertEqual(run.call_count, 8)
            self.assertTrue(all(call.kwargs['check'] for call in run.call_args_list))
            self.assertFalse(any('deploy' in call.args[0] for call in run.call_args_list))
            self.assertEqual(run.call_args_list[-1].args[0], ['npm', 'run', 'release:check'])
