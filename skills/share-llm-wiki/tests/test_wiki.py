"""Read-only CLI regression tests. Run: python3 -m unittest discover -s skills/share-llm-wiki/tests -v

Uses a local ssh shim and temporary wiki; never connects to the shared drive.
GNU utilities are needed for the production `check` command (tested remotely separately).
"""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts/wiki.sh'


class WikiTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='wiki-test-')
        self.addCleanup(self.tmp.cleanup)
        base = Path(self.tmp.name)
        self.root = base / "wiki with 'quotes'"
        self.root.mkdir()
        bindir = base / 'bin'
        bindir.mkdir()
        ssh = bindir / 'ssh'
        ssh.write_text('#!/bin/bash\nfor arg; do command="$arg"; done\nexec bash -c "$command"\n')
        ssh.chmod(0o755)
        self.env = dict(os.environ, PATH=str(bindir) + ':' + os.environ['PATH'],
                        WIKI_ROOT=str(self.root), LC_ALL='C')
        for directory in ['sources', 'evaluations', 'experiments', 'findings', 'topics', 'datasets']:
            (self.root / directory).mkdir()
        for name in ['index.md', 'log.md', 'AGENTS.md']:
            self.write(name, '# Navigation\n')

    def write(self, name, text):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)

    def run_cli(self, *args):
        return subprocess.run([str(SCRIPT), *args], env=self.env, capture_output=True,
                              text=True, encoding='utf-8', timeout=10)

    def test_errors_are_not_no_matches(self):
        for args in [('grepall', '['), ('nav', '['), ('assets', 'missing'),
                     ('grep', 'x', 'missing'), ('trace', '[')]:
            with self.subTest(args=args):
                result = self.run_cli(*args)
                self.assertNotEqual(result.returncode, 0)
                self.assertTrue(result.stderr)
        self.assertEqual(self.run_cli('grepall', 'absent').returncode, 0)

    def test_asset_truncation_and_full_output(self):
        for i in range(100):
            self.write(f'sources/{i:03}.yaml', 'value: 1\n')
        result = self.run_cli('assets', 'sources', '--limit', '3')
        self.assertEqual(result.returncode, 0)
        self.assertEqual(len(result.stdout.splitlines()), 3)
        self.assertIn('100', result.stderr)
        result = self.run_cli('assets', '--all', 'sources')
        self.assertEqual(len(result.stdout.splitlines()), 100)
        self.assertNotIn('截断', result.stderr)

    def test_search_does_not_sigpipe_or_split_paths(self):
        self.write('sources/space dir/a.md', 'needle\n' * 1000)
        result = self.run_cli('grep', 'needle', 'sources/space dir', '--limit', '2')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len(result.stdout.splitlines()), 2)
        self.assertIn('1000', result.stderr)
        self.assertEqual(len(self.run_cli('grepall', 'needle', '--all').stdout.splitlines()), 1000)

    def test_quoted_frontmatter_and_body_false_positive(self):
        for i, value in enumerate(['superseded', '"superseded"', "'superseded'"]):
            self.write(f'findings/old{i}.md', f'---\nstatus: {value} # old\n---\n# Old\n')
            self.assertIn('>>>', self.run_cli('cat', f'findings/old{i}.md').stdout)
        self.write('findings/current.md', '# Current\nstatus: superseded\n')
        self.assertNotIn('>>>', self.run_cli('cat', 'findings/current.md').stdout)
        result = self.run_cli('stale')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len(result.stdout.splitlines()), 3)
        self.assertIn('superseded', self.run_cli('ls', 'findings').stdout)

    def test_assets_and_segments(self):
        self.write('sources/empty.yaml', '')
        self.assertIn('空文件', self.run_cli('cat', 'sources/empty.yaml').stdout)
        self.write('sources/report.pdf', '%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\n%%EOF\n')
        result = self.run_cli('cat', 'sources/report.pdf')
        self.assertIn('二进制', result.stdout)
        self.assertNotIn('%PDF', result.stdout)
        self.write('sources/config.yaml', 'one: 1\ntwo: 2\nthree: 3\n')
        result = self.run_cli('cat', 'sources/config.yaml', '--lines', '2:3')
        self.assertEqual(result.stdout, 'two: 2\nthree: 3\n')
        self.assertIn('共 3 行', result.stderr)
        self.assertNotEqual(self.run_cli('cat', 'sources/config.yaml', '--lines', '9:10').returncode, 0)

    def test_svg_is_text_and_hidden_assets_are_excluded(self):
        self.write('sources/chart.svg', '<svg xmlns="http://www.w3.org/2000/svg"></svg>\n')
        self.assertIn('<svg', self.run_cli('cat', 'sources/chart.svg').stdout)
        self.write('.git/config', 'hidden\n')
        self.write('.obsidian/config.json', '{}\n')
        self.assertNotIn('config', self.run_cli('assets', '--all').stdout)

    def test_shell_characters_remain_literal(self):
        directory = "sources/space 'quote' $(false)"
        self.write(directory + '/a.md', '--literal $(false)\n')
        result = self.run_cli('grep', '--', '--literal', directory)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('--literal $(false)', result.stdout)

    def test_link_forms(self):
        self.write('experiments/v0021.md', '# Run\n')
        for name in ['v0021', 'experiments/v0021', '[[experiments/v0021.md#Section|Alias]]']:
            self.assertEqual(self.run_cli('link', name).stdout.strip(), 'experiments/v0021.md')

    def test_option_errors(self):
        for args in [('assets', '--limit', '-1'), ('cat', 'index.md', '--lines', '3:1'),
                     ('grepall', '--unknown'), ('trace', 'x', '--lines', '1:2')]:
            self.assertNotEqual(self.run_cli(*args).returncode, 0)


if __name__ == '__main__':
    unittest.main()
