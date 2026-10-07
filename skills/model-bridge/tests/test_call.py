"""Offline CLI contract tests. No real model calls or credentials required."""
import base64
import importlib.util
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/call.py"
SPEC = importlib.util.spec_from_file_location("model_bridge_call", SCRIPT)
CALL = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CALL)
FAKE = r'''
import base64, json, os, pathlib, shutil, signal, subprocess, sys, time
provider = os.environ['FAKE_PROVIDER']
if '--help' in sys.argv:
    print({'codex':'Codex exec', 'claude':'Claude Code --print',
           'cursor':'Start the Cursor Agent --trust', 'grok':'Grok Build --single'}[provider])
    sys.exit(0)
if '--version' in sys.argv:
    print('fake 1.0')
    sys.exit(0)
if sys.argv[1:] == ['auth','status']:
    print(json.dumps({'loggedIn':True,'authMethod':os.environ.get('FAKE_AUTH_METHOD','claude.ai'),
                      'apiProvider':'firstParty'}))
    sys.exit(0)
args = sys.argv[1:]
if provider == 'grok':
    prompt = pathlib.Path(args[args.index('--prompt-file')+1]).read_text()
else:
    prompt = sys.stdin.read()
pathlib.Path(os.environ['FAKE_RECORD']).write_text(json.dumps({
    'args':args, 'prompt':prompt, 'cwd':os.getcwd(),
    'depth':os.environ.get('MODEL_BRIDGE_DEPTH'),
    'token_retained':os.environ.get('ANTHROPIC_AUTH_TOKEN') == 'test-bearer-token-123456',
    'nesting_guard':os.environ.get('CLAUDECODE')}))
mode = os.environ.get('FAKE_MODE','success')
if mode == 'timeout':
    child = "import signal,time,pathlib; signal.signal(signal.SIGTERM,lambda *a:(pathlib.Path(%r).write_text('stopped'),exit(0))); print('ready',flush=True); time.sleep(30)" % os.environ['FAKE_STOPPED']
    proc = subprocess.Popen([sys.executable,'-c',child],stdout=subprocess.PIPE,text=True)
    proc.stdout.readline()
    print('partial output',flush=True)
    time.sleep(30)
if mode == 'malformed':
    print('unexpected plain text'); sys.exit(0)
if mode == 'process-error':
    print('backend failed',file=sys.stderr); sys.exit(7)
if mode == 'stderr-reason':
    print('Cannot use this model: grok-4.7[effort=high]', file=sys.stderr)
    print('MODEL-LIST ' + ('m' * 5000), file=sys.stderr)
    sys.exit(1)
if mode == 'stderr-long-line':
    print('reason-prefix ' + ('Z' * 1000), file=sys.stderr)
    sys.exit(1)
if mode == 'json-error':
    print(json.dumps({'type':'error','is_error':True,'message':'402 balance exhausted'})); sys.exit(0)
if mode == 'secret':
    answer = os.environ['ANTHROPIC_AUTH_TOKEN']
else:
    answer = 'review completed'
if mode in ('image', 'code-image', 'reference-image', 'missing-image-cache', 'historical-image', 'mixed-image'):
    # A complete decodable 1x1 PNG, rather than an extension or claimed path.
    png = 'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9Wl2zq8AAAAASUVORK5CYII='
    if mode == 'missing-image-cache':
        pathlib.Path('generated.png').write_bytes(base64.b64decode(png))
    else:
        cache = pathlib.Path(os.environ['CODEX_HOME']) / 'generated_images'
        cache.mkdir(parents=True, exist_ok=True)
        if mode == 'code-image':
            pathlib.Path('generated.png').write_bytes(base64.b64decode(png))
        else:
            source = cache / 'test-session' / 'nested' / 'exec-test.png'
            source.parent.mkdir(parents=True, exist_ok=True)
            if mode == 'reference-image':
                # Even a fresh cache match must not legitimize echoing any reference unchanged.
                references = [args[i + 1] for i, arg in enumerate(args) if arg == '--image']
                shutil.copyfile(references[-1], source)
            else:
                source.write_bytes(base64.b64decode(png))
            if mode == 'historical-image':
                os.utime(source, (time.time() - 3600, time.time() - 3600))
            shutil.copyfile(source, 'generated.png')
            if mode == 'mixed-image':
                pathlib.Path('code.png').write_bytes(base64.b64decode(png) + b'unproven')
    pathlib.Path('outside.png').symlink_to(os.environ['FAKE_OUTSIDE'])
elif mode == 'claimed-image':
    pathlib.Path('pretend.png').write_text('<svg></svg>')
    answer = 'image generated at pretend.png'
if provider == 'codex':
    if mode == 'recovered':
        print(json.dumps({'type':'error','message':'Reconnecting... 1/5'}))
    pathlib.Path(args[args.index('--output-last-message')+1]).write_text(answer)
    for item in [
        {'type':'thread.started','thread_id':'test-session'},
        {'type':'item.completed','item':{'type':'agent_message','text':answer}},
        {'type':'turn.completed','usage':{'input_tokens':5,'output_tokens':2}}]:
        print(json.dumps(item))
else:
    print(json.dumps({'type':'result','subtype':'success','is_error':False,
                      'session_id':'test-session','result':answer,'usage':{'input_tokens':5}}))
'''

AGY_FAKE = r"""
import base64, json, os, pathlib, shutil, sys, time
MAIN = '11111111-1111-4111-8111-111111111111'
SUB = '22222222-2222-4222-8222-222222222222'
PNG = base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9Wl2zq8AAAAASUVORK5CYII=')
args = sys.argv[1:]
if '--help' in args:
    print('Usage of agy:\n  --output-format  Output format'); sys.exit(0)
if '--version' in args:
    print('agy fake 1.3.1'); sys.exit(0)
prompt = sys.stdin.read()
pathlib.Path(os.environ['FAKE_RECORD']).write_text(json.dumps({
    'args': args, 'prompt': prompt, 'cwd': os.getcwd(), 'depth': os.environ.get('MODEL_BRIDGE_DEPTH'),
    'gemini_key': os.environ.get('GEMINI_API_KEY'), 'google_key': os.environ.get('GOOGLE_API_KEY')}))
mode = os.environ.get('FAKE_AGY_MODE', 'success')
home = pathlib.Path(os.environ['MODEL_BRIDGE_AGY_HOME'])
response = 'review completed'
events = [{'event': 'init', 'conversation_id': MAIN, 'init': {'tools': []}}]
denied = []

def step(name, **info):
    events.append({'event': 'step_update', 'step_update': {'conversation_id': MAIN, 'step_index': len(events),
                   'state': 'DONE', 'step_type': 'tool', 'tool_name': name, 'tool_info': {'parameters': info}}})

def transcript(*records):
    logs = home / 'brain' / SUB / '.system_generated/logs'
    logs.mkdir(parents=True, exist_ok=True)
    (logs / 'transcript.jsonl').write_text('\n'.join(json.dumps(r) for r in records))

if mode == 'auth':
    print('Authentication required. Please visit the URL to log in:', file=sys.stderr)
    print('  https://accounts.google.com/o/oauth2/auth?x=1', file=sys.stderr); sys.exit(1)
if mode == 'blocked':
    response = "This request was blocked by Gemini's filters. They can occasionally trigger by mistake."
if mode == 'truncated-marker':
    response = '<truncated 8602 bytes>\n'
if mode == 'partial':
    response = ''
    print('[agy] print timeout after 3s with turn in progress; returning partial output', file=sys.stderr)
if mode == 'denied':
    denied = [{'action': 'command', 'display_name': 'RunCommand'}]
if mode == 'tool-violation':
    step('run_command', CommandLine='touch INJECTED.txt')
if mode == 'view-file':
    step('view_file')
if mode == 'transcript-tool' or mode.startswith('image'):
    events.append({'event': 'step_update', 'step_update': {'conversation_id': MAIN, 'step_index': 9, 'state': 'DONE',
                   'step_type': 'subagent', 'tool_name': 'invoke_subagent',
                   'subagent_info': {'subagents': [{'type_name': 'image-generator', 'conversation_id': SUB}]}}})
if mode == 'transcript-tool':
    transcript({'step_index': 1, 'type': 'PLANNER_RESPONSE', 'tool_calls': [{'name': 'write_to_file', 'args': {}}]})
if mode.startswith('image'):
    target = home / 'brain' / MAIN / 'generated.png'
    target.parent.mkdir(parents=True, exist_ok=True)
    if mode == 'image-reference':
        reference = [l[2:] for l in prompt.splitlines() if l.startswith('- /')][-1]
        shutil.copyfile(reference, target)
    elif mode == 'image-forged':
        pathlib.Path('forged.png').write_bytes(PNG)
    else:
        target.write_bytes(PNG)
    if mode == 'image-old':
        os.utime(target, (time.time() - 3600, time.time() - 3600))
    if mode == 'image-run-command':
        step('run_command', CommandLine='cp generated.png .')
    if mode != 'image-forged':
        transcript({'step_index': 1, 'type': 'PLANNER_RESPONSE', 'tool_calls': [{'name': 'generate_image', 'args': {}}]},
                   {'step_index': 2, 'type': 'GENERIC', 'content': 'Generated image is saved at %s.' % target})
for e in events:
    print(json.dumps(e))
print(json.dumps({'event': 'result', 'result': {'conversation_id': MAIN, 'status': 'SUCCESS', 'response': response,
                  'usage': {'input_tokens': 5, 'output_tokens': 2}, 'denied_actions': denied}}))
"""


class CallTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.cli = self.root / "fake-cli"
        self.cli.write_text("#!%s\n%s" % (sys.executable, FAKE))
        self.cli.chmod(0o700)
        self.record = self.root / "record.json"
        self.output = self.root / "output"
        self.env = os.environ.copy()
        # Test shims only: remove inherited depth, keep real credentials out of assertions.
        self.env.pop("MODEL_BRIDGE_DEPTH", None)
        self.env.update(FAKE_RECORD=str(self.record), FAKE_STOPPED=str(self.root / "stopped"),
                        FAKE_OUTSIDE=str(self.root / "external.png"),
                        CODEX_HOME=str(self.root / "codex-home"),
                        ANTHROPIC_AUTH_TOKEN="test-bearer-token-123456", CLAUDECODE="1")

    def invoke(self, provider="codex", extra=(), mode="success", prompt="审查材料"):
        env = dict(self.env, FAKE_PROVIDER=provider, FAKE_MODE=mode)
        command = [sys.executable, str(SCRIPT), "run", provider, "--cli", str(self.cli),
                   "--output-dir", str(self.output), "--timeout", "5"]
        if prompt is not None:
            command += ["--prompt", prompt]
        return subprocess.run(command + list(extra), capture_output=True, text=True, env=env,
                              input="来自 stdin 的请求" if prompt is None else None, timeout=12)

    def test_four_providers_normalize_result_and_preserve_auth(self):
        expected_models = {"codex":"gpt-6.1-sol", "claude":"claude-sonnet-5-5", "grok":"grok-4.7", "cursor":"auto"}
        for provider in expected_models:
            with self.subTest(provider=provider):
                self.output = self.root / provider
                p = self.invoke(provider)
                self.assertEqual(p.returncode, 0, p.stderr)
                result = json.loads(p.stdout)
                self.assertEqual((result['status'], result['text']), ('ok','review completed'))
                self.assertEqual(result['requested_model'], expected_models[provider])
                self.assertEqual(result['session_id'], 'test-session')
                self.assertEqual(result['usage']['input_tokens'], 5)
                record = json.loads(self.record.read_text())
                self.assertTrue(record['token_retained'])
                self.assertEqual(record['depth'], '1')
                self.assertEqual(record['nesting_guard'], None if provider == 'claude' else '1')
                self.assertEqual(stat.S_IMODE(self.output.stat().st_mode), 0o700)
                self.assertEqual(stat.S_IMODE((self.output/'request.txt').stat().st_mode), 0o600)
                args = record['args']
                self.assertNotIn('--force', args)
                self.assertNotIn('--yolo', args)
                if provider == 'cursor':
                    self.assertIn('--trust', args)
                    self.assertEqual(args[args.index('--mode')+1], 'ask')
                    self.assertIn('审查材料', record['prompt'])
                    self.assertTrue(all('审查材料' not in arg for arg in args))
                if provider == 'codex':
                    self.assertEqual(args[args.index('--sandbox')+1], 'read-only')
                if provider == 'claude':
                    self.assertEqual(args[args.index('--tools')+1], '')

    def test_materials_and_shell_characters_remain_literal(self):
        context = self.root / "材料 with spaces.md"
        context.write_text('验收标准：返回 None。')
        marker = self.root / 'must-not-exist'
        prompt = '请求 "quote" $(touch %s) `touch %s`\n第二行' % (marker, marker)
        p = self.invoke('cursor', ['--context', str(context)], prompt=prompt)
        self.assertEqual(p.returncode, 0, p.stderr)
        captured = json.loads(self.record.read_text())
        self.assertIn(prompt, captured['prompt'])
        self.assertIn(context.read_text(), captured['prompt'])
        self.assertFalse(marker.exists())
        args = captured['args']
        self.assertIn('--trust', args)
        self.assertNotIn('--force', args)
        self.assertNotIn('--yolo', args)
        self.assertEqual(args[args.index('--mode')+1], 'ask')
        self.assertTrue(all('$(touch' not in arg and '`touch' not in arg and prompt not in arg for arg in args))

    def test_stdin_and_model_effort_override(self):
        p = self.invoke('claude', ['--model','sonnet','--effort','high'], prompt=None)
        self.assertEqual(p.returncode, 0, p.stderr)
        record = json.loads(self.record.read_text())
        self.assertIn('来自 stdin 的请求', record['prompt'])
        self.assertEqual(record['args'][record['args'].index('--effort')+1], 'high')

    def test_interactive_stdin_without_prompt_is_rejected_without_reading(self):
        stdin = mock.Mock()
        stdin.isatty.return_value = True
        args = SimpleNamespace(prompt=None, prompt_file=None)
        with mock.patch.object(CALL.sys, 'stdin', stdin):
            with self.assertRaisesRegex(CALL.CallError, '--prompt、--prompt-file 或管道输入'):
                CALL.make_prompt(args, self.root / 'artifacts')
        stdin.read.assert_not_called()

    def test_explicit_claude_login_excludes_only_child_environment_credentials(self):
        p = self.invoke('claude', ['--claude-auth','login'])
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertFalse(json.loads(self.record.read_text())['token_retained'])
        self.assertEqual(json.loads(p.stdout)['claude_auth'], 'login')
        self.assertEqual(self.env['ANTHROPIC_AUTH_TOKEN'], 'test-bearer-token-123456')

    def test_claude_login_refuses_other_auth_without_model_call(self):
        self.env['FAKE_AUTH_METHOD'] = 'api_key'
        p = self.invoke('claude', ['--claude-auth','login'])
        self.assertEqual(p.returncode, 2, p.stderr)
        self.assertFalse(self.record.exists())
        self.assertFalse(self.output.exists())

    def test_claude_rejects_effort_the_cli_would_silently_ignore(self):
        for bad in ('none', 'ultra'):
            with self.subTest(effort=bad):
                self.record.unlink() if self.record.exists() else None
                p = self.invoke('claude', ['--effort', bad])
                self.assertEqual(p.returncode, 2, p.stderr)
                self.assertFalse(self.record.exists())
                self.assertFalse(self.output.exists())
        p = self.invoke('claude', ['--effort', 'xhigh'])
        self.assertEqual(p.returncode, 0, p.stderr)

    def test_claude_settings_project_is_opt_in_and_claude_only(self):
        p = self.invoke('claude')
        self.assertNotIn('--setting-sources', json.loads(self.record.read_text())['args'])
        self.assertEqual(json.loads(p.stdout)['claude_settings'], 'inherit')
        self.output = self.root / 'isolated'
        p = self.invoke('claude', ['--claude-settings', 'project'])
        self.assertEqual(p.returncode, 0, p.stderr)
        args = json.loads(self.record.read_text())['args']
        self.assertEqual(args[args.index('--setting-sources')+1], 'project')
        self.assertTrue(json.loads(self.record.read_text())['token_retained'])  # 不碰进程环境里的认证
        self.record.unlink()
        self.output = self.root / 'other'
        p = self.invoke('codex', ['--claude-settings', 'project'])
        self.assertEqual(p.returncode, 2, p.stderr)
        self.assertFalse(self.record.exists())

    def test_dry_run_does_not_request_model_or_create_output(self):
        p = self.invoke(extra=['--dry-run'])
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertTrue(json.loads(p.stdout)['dry_run'])
        self.assertFalse(self.record.exists())
        self.assertFalse(self.output.exists())

    def test_wrong_cli_identity_and_recursion_are_rejected_before_call(self):
        self.env['FAKE_PROVIDER'] = 'grok'
        for args in ([sys.executable,str(SCRIPT),'run','cursor','--cli',str(self.cli),'--prompt','hi'],):
            p = subprocess.run(args, capture_output=True, text=True, env=self.env)
            self.assertEqual(p.returncode, 2)
            self.assertIn('身份不符', p.stderr)
        self.env['MODEL_BRIDGE_DEPTH'] = '1'
        p = self.invoke()
        self.assertEqual(p.returncode, 2)
        self.assertIn('禁止再次委派', p.stderr)
        self.assertFalse(self.record.exists())

    def test_failures_never_become_success_or_retry(self):
        for mode in ('json-error','process-error','malformed'):
            with self.subTest(mode=mode):
                self.output = self.root / mode
                p = self.invoke('grok', mode=mode)
                self.assertEqual(p.returncode, 1, p.stderr)
                result = json.loads(p.stdout)
                self.assertEqual(result['status'], 'error')
                self.assertTrue(result['error'])
                if mode == 'json-error':
                    self.assertIn('402 balance exhausted', result['error'])
                if mode == 'malformed':
                    self.assertIn('未收到预期的 JSON/JSONL 结果', result['error'])
                if mode == 'process-error':
                    self.assertEqual(result['process_exit_code'], 7)
                    self.assertIn('backend failed', result['error'])
                    self.assertIn('stderr.txt', result['error'])
                    self.assertNotIn('未收到预期的 JSON', result['error'])

    def test_cursor_effort_is_refused_unless_the_model_string_is_passed_through(self):
        refused = (
            ['--model', 'grok-4.7', '--effort', 'high'],
            ['--model', 'grok-4.7-high', '--effort', 'high'],
            ['--effort', 'high'],
        )
        for index, extra in enumerate(refused):
            with self.subTest(extra=extra):
                self.output = self.root / ('refuse-%d' % index)
                p = self.invoke('cursor', extra)
                self.assertEqual(p.returncode, 2, p.stderr)
                self.assertIn('grok-4.7-high', p.stderr)
                self.assertIn('list-models', p.stderr)
                self.assertIn('auto', p.stderr)
                self.assertNotIn('[effort=', p.stderr)
                self.assertFalse(self.record.exists())
                self.assertFalse(self.output.exists())

        self.output = self.root / 'cursor-id'
        p = self.invoke('cursor', ['--model', 'grok-4.7-high'])
        self.assertEqual(p.returncode, 0, p.stderr)
        result = json.loads(p.stdout)
        self.assertEqual(result['requested_model'], 'grok-4.7-high')
        self.assertIsNone(result['effort'])
        self.assertTrue(result['command'])
        self.assertNotIn('[effort=', '\n'.join(result['command']))
        self.assertTrue(all('审查材料' not in arg for arg in result['command']))
        args = json.loads(self.record.read_text())['args']
        self.assertEqual(args[args.index('--model')+1], 'grok-4.7-high')
        self.assertNotIn('--effort', args)

        bracket = 'claude-opus-4-8[effort=high]'
        for extra, folder in ((['--model', bracket], 'cursor-bracket'),
                              (['--model', bracket, '--effort', 'high'], 'cursor-bracket-effort')):
            with self.subTest(extra=extra):
                self.output = self.root / folder
                p = self.invoke('cursor', extra)
                self.assertEqual(p.returncode, 0, p.stderr)
                args = json.loads(self.record.read_text())['args']
                self.assertEqual(args[args.index('--model')+1], bracket)
                self.assertNotIn('--effort', args)

        self.output = self.root / 'cursor-dry'
        p = self.invoke('cursor', ['--model', 'grok-4.7-high', '--dry-run'])
        self.assertEqual(p.returncode, 0, p.stderr)
        plan = json.loads(p.stdout)
        self.assertTrue(plan['stdin'])
        self.assertEqual(plan['requested_model'], 'grok-4.7-high')
        self.assertIsNone(plan['effort'])
        self.assertNotIn('[effort=', '\n'.join(plan['command']))
        self.assertTrue(all('审查材料' not in arg for arg in plan['command']))
        self.assertFalse(self.output.exists())

    def test_nonzero_exit_without_json_reports_first_stderr_line(self):
        p = self.invoke('grok', mode='stderr-reason')
        self.assertEqual(p.returncode, 1, p.stderr)
        result = json.loads(p.stdout)
        self.assertEqual((result['status'], result['process_exit_code']), ('error', 1))
        self.assertIn('Cannot use this model: grok-4.7[effort=high]', result['error'])
        self.assertIn('stderr.txt', result['error'])
        self.assertNotIn('MODEL-LIST', result['error'])
        self.assertNotIn('m' * 80, result['error'])
        self.assertNotIn('未收到预期的 JSON', result['error'])
        self.assertLess(len(result['error']), 400)
        self.assertIn('MODEL-LIST', (self.output / 'stderr.txt').read_text())

        self.output = self.root / 'long-line'
        p = self.invoke('grok', mode='stderr-long-line')
        self.assertEqual(p.returncode, 1, p.stderr)
        result = json.loads(p.stdout)
        self.assertEqual(result['status'], 'error')
        self.assertTrue(result['error'].startswith('reason-prefix'))
        self.assertNotIn('Z' * 400, result['error'])
        self.assertLessEqual(len(result['error']), CALL.STDERR_REASON_LIMIT + len('…；详见 stderr.txt。'))
        self.assertIn('Z' * 1000, (self.output / 'stderr.txt').read_text())

    def test_codex_completed_turn_supersedes_reconnect_event(self):
        p = self.invoke(mode='recovered')
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(json.loads(p.stdout)['status'], 'ok')
        self.assertIn('Reconnecting', (self.output/'stdout.txt').read_text())

    def test_timeout_terminates_child_group_and_keeps_partial_output(self):
        p = self.invoke(extra=['--timeout','0.4'], mode='timeout')
        self.assertEqual(p.returncode, 124, p.stderr)
        self.assertEqual(json.loads(p.stdout)['status'], 'timeout')
        self.assertIn('partial output', (self.output/'stdout.txt').read_text())
        self.assertEqual((self.root/'stopped').read_text(), 'stopped')

    def test_actual_image_required_and_outside_symlink_excluded(self):
        outside = Path(self.env['FAKE_OUTSIDE'])
        outside.write_bytes(base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9Wl2zq8AAAAASUVORK5CYII='))
        p = self.invoke(extra=['--task','image'], mode='image')
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertTrue((self.output / 'artifacts/outside.png').is_symlink())
        self.assertTrue((self.output / 'artifacts/outside.png').is_file())
        images = json.loads(p.stdout)['artifacts']
        self.assertEqual(len(images), 1)
        self.assertEqual(images[0]['format'], 'png')
        self.assertEqual(len(images[0]['sha256']), 64)
        source = Path(self.env['CODEX_HOME']) / 'generated_images/test-session/nested/exec-test.png'
        self.assertEqual(images[0]['sha256'], CALL.file_sha256(source))
        args = json.loads(self.record.read_text())['args']
        self.assertEqual(args[args.index('--sandbox')+1], 'workspace-write')
        self.output = self.root / 'claim'
        p = self.invoke(extra=['--task','image'], mode='claimed-image')
        self.assertEqual(p.returncode, 1)
        self.assertEqual(json.loads(p.stdout)['artifacts'], [])

    def test_image_without_builtin_source_is_rejected(self):
        p = self.invoke(extra=['--task', 'image'], mode='code-image')
        self.assertEqual(p.returncode, 1, p.stderr)
        result = json.loads(p.stdout)
        self.assertEqual(result['status'], 'error')
        self.assertEqual(len(result['artifacts']), 1)  # Valid PNG alone is not proof.
        self.assertIn('无法证明产物来自内置 image_gen', result['error'])
        self.assertIn('SHA-256 未匹配', result['error'])

    def test_unchanged_reference_is_rejected_even_with_fresh_builtin_source(self):
        first, second = self.root / 'first.png', self.root / 'second.png'
        first.write_bytes(base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9Wl2zq8AAAAASUVORK5CYII=') + b'first')
        second.write_bytes(first.read_bytes()[:-5])
        p = self.invoke(extra=['--task', 'image', '--image', str(first), '--image', str(second)],
                        mode='reference-image')
        self.assertEqual(p.returncode, 1, p.stderr)
        result = json.loads(p.stdout)
        self.assertEqual(result['status'], 'error')
        self.assertEqual(result['artifacts'][0]['sha256'], CALL.file_sha256(second))
        source = Path(self.env['CODEX_HOME']) / 'generated_images/test-session/nested/exec-test.png'
        self.assertEqual(CALL.file_sha256(source), CALL.file_sha256(second))
        self.assertIn('原样回传不能认定编辑成功', result['error'])

    def test_changed_image_with_fresh_builtin_source_succeeds(self):
        reference = self.root / 'reference.png'
        reference.write_bytes(base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9Wl2zq8AAAAASUVORK5CYII=') + b'reference')
        p = self.invoke(extra=['--task', 'image', '--image', str(reference)], mode='image')
        self.assertEqual(p.returncode, 0, p.stderr)
        result = json.loads(p.stdout)
        self.assertEqual(result['status'], 'ok')
        self.assertNotEqual(result['artifacts'][0]['sha256'], CALL.file_sha256(reference))

    def test_missing_generated_images_fails_closed_with_actionable_hint(self):
        p = self.invoke(extra=['--task', 'image'], mode='missing-image-cache')
        self.assertEqual(p.returncode, 1, p.stderr)
        result = json.loads(p.stdout)
        self.assertEqual(result['status'], 'error')
        self.assertIn('无法证明产物来自内置 image_gen', result['error'])
        self.assertIn('generated_images 目录不存在或不可读', result['error'])
        self.assertIn('CODEX_HOME', result['error'])
        self.assertIn('需更新本脚本的来源校验', result['error'])

    def test_unreadable_generated_images_fails_closed(self):
        cache = self.root / 'generated_images'
        cache.mkdir()
        with mock.patch.object(CALL.os, 'walk', side_effect=PermissionError('permission denied')):
            with self.assertRaisesRegex(CALL.CallError, '目录不存在或不可读.*读取权限'):
                CALL.validate_image_sources([{'path': 'image.png', 'sha256': 'test'}], cache, 0, 1, set())

    def test_historical_generated_image_cannot_prove_current_output(self):
        p = self.invoke(extra=['--task', 'image'], mode='historical-image')
        self.assertEqual(p.returncode, 1, p.stderr)
        result = json.loads(p.stdout)
        self.assertEqual(result['status'], 'error')
        self.assertEqual(len(result['artifacts']), 1)
        self.assertIn('本次运行期间写入的来源文件', result['error'])

    def test_every_image_artifact_requires_builtin_provenance(self):
        p = self.invoke(extra=['--task', 'image'], mode='mixed-image')
        self.assertEqual(p.returncode, 1, p.stderr)
        result = json.loads(p.stdout)
        self.assertEqual(result['status'], 'error')
        self.assertEqual(len(result['artifacts']), 2)
        self.assertIn('code.png', result['error'])

    def test_existing_output_is_preserved_and_invalid_inputs_do_not_call(self):
        self.output.mkdir()
        sentinel = self.output/'keep.txt'
        sentinel.write_text('keep')
        p = self.invoke()
        self.assertEqual(p.returncode, 2)
        self.assertEqual(sentinel.read_text(), 'keep')
        self.output = self.root/'new'
        for provider, extra in [('cursor',['--effort','high']), ('grok',['--task','image']),
                                ('codex',['--context',str(self.root/'missing')])]:
            p = self.invoke(provider, extra)
            self.assertEqual(p.returncode, 2, p.stderr)
        self.assertFalse(self.record.exists())

    def test_logs_and_terminal_redact_inherited_credentials(self):
        p = self.invoke(mode='secret')
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertNotIn(self.env['ANTHROPIC_AUTH_TOKEN'], p.stdout+p.stderr)
        for file in self.output.glob('*.txt'):
            self.assertNotIn(self.env['ANTHROPIC_AUTH_TOKEN'], file.read_text())
        self.assertEqual(json.loads(p.stdout)['text'], '[REDACTED]')


class AgyTests(unittest.TestCase):
    PNG = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9Wl2zq8AAAAASUVORK5CYII=")

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.cli = self.root / "fake-agy"
        self.cli.write_text("#!%s\n%s" % (sys.executable, AGY_FAKE))
        self.cli.chmod(0o700)
        self.record = self.root / "record.json"
        self.output = self.root / "output"
        self.home = self.root / "agy-home"
        self.env = os.environ.copy()
        self.env.pop("MODEL_BRIDGE_DEPTH", None)
        self.env.update(FAKE_RECORD=str(self.record), MODEL_BRIDGE_AGY_HOME=str(self.home),
                        GEMINI_API_KEY="test-gemini-key-123456", GOOGLE_API_KEY="test-google-key-123456")

    def invoke(self, mode="success", extra=(), task="ask", prompt="审查材料"):
        # 每次调用用全新结果目录与记录，避免上一次调用的残留影响断言。
        for leftover in (self.output, self.home):
            if leftover.exists():
                shutil.rmtree(leftover)
        if self.record.exists():
            self.record.unlink()
        env = dict(self.env, FAKE_AGY_MODE=mode)
        command = [sys.executable, str(SCRIPT), "run", "agy", "--cli", str(self.cli), "--task", task,
                   "--output-dir", str(self.output), "--timeout", "5", "--prompt", prompt]
        return subprocess.run(command + list(extra), capture_output=True, text=True, env=env, timeout=15)

    def test_text_task_uses_stdin_isolated_work_dir_and_strips_api_keys(self):
        process = self.invoke()
        self.assertEqual(process.returncode, 0, process.stderr)
        result = json.loads(process.stdout)
        self.assertEqual((result["status"], result["text"]), ("ok", "review completed"))
        self.assertEqual(result["requested_model"], "gemini-3.8-flash-medium")
        record = json.loads(self.record.read_text())
        self.assertEqual(record["args"][record["args"].index("--output-format") + 1], "stream-json")
        self.assertNotIn("-p", record["args"])
        self.assertIn("审查材料", record["prompt"])
        self.assertIn("严禁调用任何工具", record["prompt"])
        self.assertEqual(Path(record["cwd"]).resolve(), (self.output / "work").resolve())
        self.assertEqual(record["depth"], "1")
        self.assertIsNone(record["gemini_key"])
        self.assertIsNone(record["google_key"])
        self.assertEqual(result["usage"]["input_tokens"], 5)

    def test_bare_model_accepts_effort(self):
        process = self.invoke(extra=["--model", "gemini-3.8-flash", "--effort", "high"])
        self.assertEqual(process.returncode, 0, process.stderr)
        args = json.loads(self.record.read_text())["args"]
        self.assertEqual(args[args.index("--effort") + 1], "high")
        self.assertEqual(args[args.index("--model") + 1], "gemini-3.8-flash")

    def test_invalid_requests_are_rejected_before_calling(self):
        big = self.root / "big.txt"
        big.write_text("x" * (160 * 1024))
        cases = [
            (["--model", "gemini-3.8-flash-low", "--effort", "high"], "已含档位"),
            (["--model", "gemini-3.8-flash", "--effort", "xhigh"], "未经验证"),
            (["--workspace", str(self.root)], "不是只读"),
            (["--image", str(self.root / "missing.png")], "--image"),
            (["--context", str(big)], "150 KiB"),
        ]
        for extra, reason in cases:
            with self.subTest(extra=extra):
                process = self.invoke(extra=extra)
                self.assertEqual(process.returncode, 2)
                self.assertIn(reason, process.stderr)
                self.assertFalse(self.record.exists())

    def test_image_is_copied_only_with_generate_image_provenance(self):
        process = self.invoke("image", task="image", prompt="画一张图")
        self.assertEqual(process.returncode, 0, process.stderr)
        result = json.loads(process.stdout)
        self.assertEqual(result["status"], "ok")
        self.assertEqual([a["format"] for a in result["artifacts"]], ["png"])
        self.assertTrue(result["artifacts"][0]["path"].startswith(str((self.output / "artifacts").resolve())))
        self.assertIn("generate_image", result["agy"]["tools"])
        self.assertEqual(result["agy"]["conversation_ids"][0], "11111111-1111-4111-8111-111111111111")

    def test_image_without_provenance_or_from_history_is_rejected(self):
        for mode in ("image-forged", "image-old"):
            with self.subTest(mode=mode):
                process = self.invoke(mode, task="image", prompt="画一张图")
                result = json.loads(process.stdout)
                self.assertEqual(process.returncode, 1)
                self.assertEqual((result["status"], result["artifacts"]), ("error", []))
                self.assertIn("generate_image", result["error"])

    def test_unchanged_reference_is_rejected(self):
        reference = self.root / "reference.png"
        reference.write_bytes(self.PNG)
        process = self.invoke("image-reference", task="image", extra=["--image", str(reference)])
        result = json.loads(process.stdout)
        self.assertEqual((process.returncode, result["status"]), (1, "error"))
        self.assertIn("SHA-256", result["error"])
        self.assertIn(str(reference.resolve()), json.loads(self.record.read_text())["prompt"])

    def test_missing_agy_state_dir_fails_closed_for_images(self):
        self.env["MODEL_BRIDGE_AGY_HOME"] = str(self.root / "elsewhere")
        process = self.invoke("success", task="image")
        result = json.loads(process.stdout)
        self.assertEqual((process.returncode, result["status"], result["artifacts"]), (1, "error", []))

    def test_run_command_in_image_task_is_only_a_warning(self):
        process = self.invoke("image-run-command", task="image")
        result = json.loads(process.stdout)
        self.assertEqual((process.returncode, result["status"]), (0, "ok"))
        self.assertIn("cp generated.png .", " ".join(result["warnings"]))

    def test_tools_beyond_the_task_allowance_fail_closed(self):
        for mode in ("tool-violation", "view-file", "transcript-tool"):
            with self.subTest(mode=mode):
                process = self.invoke(mode)
                result = json.loads(process.stdout)
                self.assertEqual((process.returncode, result["status"]), (1, "error"))
                self.assertIn("不允许的工具", result["error"])

    def test_success_status_is_not_trusted_for_known_failure_shapes(self):
        expected = {"blocked": "过滤器", "truncated-marker": "截断标记", "partial": "部分输出",
                    "denied": "被拒绝的动作"}
        for mode, text in expected.items():
            with self.subTest(mode=mode):
                process = self.invoke(mode)
                result = json.loads(process.stdout)
                self.assertEqual((process.returncode, result["status"]), (1, "error"))
                self.assertIn(text, result["error"])

    def test_not_logged_in_gives_actionable_error(self):
        process = self.invoke("auth")
        result = json.loads(process.stdout)
        self.assertEqual((process.returncode, result["status"]), (1, "error"))
        self.assertIn("登录", result["error"])
        self.assertNotIn("accounts.google.com", result["error"])


if __name__ == '__main__':
    unittest.main()
