import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


class DeployTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / 'scripts').mkdir()
        source = Path(__file__).resolve().parents[1] / 'scripts/deploy.mjs'
        shutil.copyfile(source, self.root / 'scripts/deploy.mjs')
        (self.root / 'bin').mkdir()
        npm = self.root / 'bin/npm'
        npm.write_text('#!/bin/sh\n[ -z "$CLOUDFLARE_API_TOKEN" ] || exit 99\nprintf "%s\\n" "$*" > release-called\nexit "${TEST_RELEASE_STATUS:-0}"\n')
        npm.chmod(0o700)
        wrangler = self.root / 'node_modules/wrangler/bin'
        wrangler.mkdir(parents=True)
        (wrangler / 'wrangler.js').write_text("require('node:fs').writeFileSync('upload-called', JSON.stringify(process.argv.slice(2))); if (!process.env.CLOUDFLARE_API_TOKEN) process.exit(99);\n")
        self.env = {**os.environ, 'PATH': str(self.root / 'bin') + os.pathsep + os.environ['PATH'], 'CLOUDFLARE_API_TOKEN': 'test-only', 'CLOUDFLARE_ACCOUNT_ID': 'a' * 32, 'CLOUDFLARE_PAGES_PROJECT': 'test-project'}

    def invoke(self):
        return subprocess.run([shutil.which('node'), str(self.root / 'scripts/deploy.mjs')], cwd=self.root, env=self.env, capture_output=True, text=True)

    def test_failed_release_never_uploads(self):
        self.env['TEST_RELEASE_STATUS'] = '7'
        self.assertEqual(self.invoke().returncode, 7)
        self.assertEqual((self.root / 'release-called').read_text().strip(), 'run release:check')
        self.assertFalse((self.root / 'upload-called').exists())

    def test_missing_token_never_starts_release_or_upload(self):
        del self.env['CLOUDFLARE_API_TOKEN']
        self.assertEqual(self.invoke().returncode, 1)
        self.assertFalse((self.root / 'release-called').exists())
        self.assertFalse((self.root / 'upload-called').exists())

    def test_success_uploads_only_dist_to_explicit_project_and_main(self):
        result = self.invoke()
        self.assertEqual(result.returncode, 0, result.stderr)
        import json
        self.assertEqual(json.loads((self.root / 'upload-called').read_text()), ['pages', 'deploy', 'dist', '--project-name', 'test-project', '--branch', 'main'])
