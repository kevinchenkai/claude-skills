"""Offline CLI contract tests. No real model calls or credentials required."""
import base64
from datetime import datetime, timezone
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import sqlite3
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
elif mode == 'schema-ok':
    answer = json.dumps({'items': [{'id': 's1', 'label': '正面'}]}, ensure_ascii=False)
elif mode == 'schema-bad-enum':
    answer = json.dumps({'items': [{'id': 's1', 'label': '積極'}]}, ensure_ascii=False)
else:
    answer = 'review completed'
if mode == 'unknown-cost':
    print('[claude-code:unrecognized_model] {"model":"claude-haiku-5-5"}', file=sys.stderr)
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
elif mode == 'unknown-cost':
    # 2.1.289 不认识 Haiku 5.5 时的形状：costBasis unknown，total_cost_usd 按 Opus 级单价。
    print(json.dumps({'type':'result','subtype':'success','is_error':False,'session_id':'test-session',
                      'result':answer,'total_cost_usd':9.21,
                      'usage':{'input_tokens':2,'cache_creation_input_tokens':8000,'cache_read_input_tokens':1000,
                               'output_tokens':1000,'cache_creation':{'ephemeral_1h_input_tokens':8000,
                                                                      'ephemeral_5m_input_tokens':0}},
                      'modelUsage':{'claude-haiku-5-5':{'costUSD':9.21,'costBasis':'unknown'}}}))
else:
    out = {'type':'result','subtype':'success','is_error':False,
           'session_id':'test-session','result':answer,'usage':{'input_tokens':5}}
    if '--json-schema' in args and mode == 'schema-ok':
        out['structured_output'] = json.loads(answer)
    print(json.dumps(out))
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

    def test_codex_text_runs_are_ephemeral_but_image_runs_are_not(self):
        p = self.invoke('codex')
        self.assertEqual(p.returncode, 0, p.stderr)
        args = json.loads(self.record.read_text())['args']
        self.assertIn('--ephemeral', args)
        self.assertNotIn('--ignore-user-config', args)
        self.output = self.root / 'ignore'
        p = self.invoke('codex', ['--codex-config', 'ignore'])
        self.assertIn('--ignore-user-config', json.loads(self.record.read_text())['args'])
        self.output = self.root / 'image'
        self.invoke('codex', ['--task', 'image'], mode='image')
        self.assertNotIn('--ephemeral', json.loads(self.record.read_text())['args'])
        self.record.unlink()
        self.output = self.root / 'not-codex'
        p = self.invoke('claude', ['--codex-config', 'ignore'])
        self.assertEqual(p.returncode, 2, p.stderr)
        self.assertFalse(self.record.exists())

    def test_label_task_drops_the_honesty_preamble_but_keeps_safety(self):
        p = self.invoke('claude', ['--task', 'label'])
        self.assertEqual(p.returncode, 0, p.stderr)
        prompt = json.loads(self.record.read_text())['prompt']
        self.assertIn('只输出结果本身', prompt)
        self.assertIn('不要提交、推送', prompt)
        self.assertNotIn('不要声称执行过', prompt)
        self.assertNotIn('明确你能从所提供材料确定的事实', prompt)
        self.output = self.root / 'ask'
        self.invoke('claude')
        self.assertIn('不要声称执行过', json.loads(self.record.read_text())['prompt'])

    def test_schema_is_native_for_claude_codex_and_prompted_plus_validated_elsewhere(self):
        schema = self.root / 'schema.json'
        schema.write_text(json.dumps({'type': 'object', 'required': ['items'], 'properties': {'items': {
            'type': 'array', 'items': {'type': 'object', 'required': ['id', 'label'],
                                       'properties': {'id': {'type': 'string'}, 'label': {'enum': ['正面', '负面']}}}}}}))
        for provider in ('claude', 'codex', 'grok'):
            with self.subTest(provider=provider):
                self.output = self.root / ('schema-' + provider)
                p = self.invoke(provider, ['--schema', str(schema)], mode='schema-ok')
                self.assertEqual(p.returncode, 0, p.stderr)
                result = json.loads(p.stdout)
                self.assertEqual(result['json'], {'items': [{'id': 's1', 'label': '正面'}]})
                record = json.loads(self.record.read_text())
                args = record['args']
                if provider == 'claude':
                    self.assertEqual(json.loads(args[args.index('--json-schema') + 1])['type'], 'object')
                elif provider == 'codex':
                    self.assertEqual(Path(args[args.index('--output-schema') + 1]), self.output / 'schema.json')
                self.assertEqual(CALL.SCHEMA_PROMPT in record['prompt'], provider == 'grok')
                for mode, reason in (('success', '不是 JSON 对象'), ('schema-bad-enum', '不在取值范围')):
                    self.output = self.root / ('%s-%s' % (mode, provider))
                    p = self.invoke(provider, ['--schema', str(schema)], mode=mode)
                    result = json.loads(p.stdout)
                    self.assertEqual((p.returncode, result['status'], result['json'], result['error_kind']),
                                     (1, 'error', None, 'invalid_output'))
                    self.assertIn(reason, result['error'])
        array = self.root / 'array.json'
        array.write_text(json.dumps({'type': 'array'}))
        self.record.unlink()
        self.output = self.root / 'bad-array'
        p = self.invoke('claude', ['--schema', str(array)])
        self.assertEqual(p.returncode, 2, p.stderr)
        self.assertIn('顶层必须', p.stderr)
        self.assertFalse(self.record.exists())

    def test_json_object_is_recovered_from_fences_and_chatter(self):
        self.assertEqual(CALL.parse_json_object('```json\n{"a": 1}\n```'), {'a': 1})
        self.assertEqual(CALL.parse_json_object('结果如下：{"a": [1]} 以上。'), {'a': [1]})
        self.assertIsNone(CALL.parse_json_object('[1, 2]'))
        self.assertIsNone(CALL.parse_json_object('没有 JSON'))

    def test_schema_subset_validation(self):
        schema = {'type': 'object', 'required': ['n'], 'additionalProperties': False,
                  'properties': {'n': {'type': 'integer', 'minimum': 1, 'maximum': 10}}}
        self.assertEqual(CALL.schema_errors({'n': 3}, schema), [])
        self.assertTrue(CALL.schema_errors({'n': 11}, schema))
        self.assertTrue(CALL.schema_errors({'n': True}, schema))
        self.assertTrue(CALL.schema_errors({}, schema))
        self.assertTrue(CALL.schema_errors({'n': 1, '質量分': 2}, schema))

    def test_errors_are_classified_for_callers(self):
        aup = ("API Error: Haiku 5.5 can't help with this. Start a new session to continue.\n\n"
               "Learn more: https://www.anthropic.com/legal/aup\n\nDetails: `[bio]`")
        cases = [
            (('error', aup, '', ''), 'refusal'),
            (('error', 'CLI reported an error', '{"stop_reason":"refusal"}', ''), 'refusal'),
            (('error', "agy 报告请求被 Gemini 过滤器拦截（常为误拦）", '', ''), 'refusal'),
            (('error', '402 Grok Build usage balance exhausted', '', ''), 'quota'),
            (('error', 'x', '', 'Error: 429 Too Many Requests'), 'quota'),
            (('error', 'agy 未登录或登录已过期', '', 'Authentication required.'), 'auth'),
            (('error', '401 Invalid bearer token', '', ''), 'auth'),
            (("error", "Couldn't set model 'grok-4.7': unknown model id", '', ''), 'unknown_model'),
            (('error', 'x', '', 'stream disconnected before completion'), 'transient'),
            (('error', '529 overloaded', '', ''), 'transient'),
            (('error', 'agy 使用了任务不允许的工具：run_command。', '', ''), 'policy'),
            (('error', '要求了 --schema，但回答不是 JSON 对象', '', ''), 'invalid_output'),
            (('timeout', '调用超时', '', ''), 'timeout'),
            (('error', 'backend failed', '', ''), 'other'),
        ]
        for args, kind in cases:
            with self.subTest(kind=kind, error=args[1][:30]):
                self.assertEqual(CALL.classify_error(*args), kind)
        p = self.invoke('codex', mode='json-error')
        self.assertEqual(json.loads(p.stdout)['error_kind'], 'quota')

    def test_unrecognized_claude_model_cost_is_flagged_and_reestimated(self):
        p = self.invoke('claude', ['--model', 'claude-haiku-5-5'], mode='unknown-cost')
        self.assertEqual(p.returncode, 0, p.stderr)
        result = json.loads(p.stdout)
        self.assertNotIn('total_cost_usd', result['usage'])
        self.assertEqual(result['usage']['total_cost_usd_unreliable'], 9.21)
        self.assertTrue(any('unrecognized_model' in w for w in result['warnings']))
        self.assertTrue(any('不可信' in w for w in result['warnings']))
        # 2*0.10 + 1000*0.01 + 8000*0.20(1h 写入) + 1000*0.50，单位为每百万 token。
        self.assertAlmostEqual(result['cost_estimate']['usd'], 0.0021102)

    def test_cost_estimate_uses_long_context_tier_and_refuses_unknown_rates(self):
        luna = {'input_tokens': 300000, 'cached_input_tokens': 100000, 'output_tokens': 1000}
        self.assertAlmostEqual(CALL.estimate_cost('gpt-6-luna', luna)['usd'],
                               (200000 * 0.20 + 100000 * 0.02 + 1000 * 0.75) / 1e6)
        short = {'input_tokens': 15000, 'cached_input_tokens': 8000, 'output_tokens': 100}
        self.assertAlmostEqual(CALL.estimate_cost('gpt-6-luna', short)['usd'], (7000 * 0.10 + 8000 * 0.01 + 100 * 0.50) / 1e6)
        long_haiku = {'input_tokens': 150000, 'cache_read_input_tokens': 10, 'output_tokens': 1}
        self.assertIsNone(CALL.estimate_cost('claude-haiku-5-5', long_haiku))  # 长上下文缓存价未公布
        self.assertIsNone(CALL.estimate_cost('claude-sonnet-5-5', short))
        self.assertIsNone(CALL.estimate_cost('claude-haiku-5-5', {'input_tokens': 5, 'cache_creation_input_tokens': 9,
                                                                   'output_tokens': 1}))

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



class PruneTests(unittest.TestCase):
    """prune 只碰本工具在默认结果目录下建的运行，以及这些运行在各家 CLI 里留下的会话。"""
    OLD, NEW = '20200101T000000', datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')
    CODEX_ID = '01a128ed-2ad6-7872-ac2e-a06d168d3c1c'
    AGY_ID = '11111111-1111-4111-8111-111111111111'

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name)
        self.cache = self.home / '.cache/model-bridge'
        self.cache.mkdir(parents=True)
        self.deleted = self.home / 'deleted.txt'
        fake = self.home / 'fake-codex'
        fake.write_text('#!%s\nimport sys\nif "--help" in sys.argv: print("Codex exec"); sys.exit(0)\n'
                        'open(%r, "a").write(" ".join(sys.argv[1:]) + "\\n")\n' % (sys.executable, str(self.deleted)))
        fake.chmod(0o700)
        self.agy = self.home / 'agy'
        (self.agy / 'brain' / self.AGY_ID).mkdir(parents=True)
        (self.agy / 'conversations').mkdir()
        (self.agy / 'conversations' / (self.AGY_ID + '.db')).write_bytes(b'x' * 10)
        (self.agy / 'brain' / 'keep-me').mkdir()
        with sqlite3.connect(str(self.agy / 'conversation_summaries.db')) as db:
            db.execute('create table conversation_summaries (conversation_id text primary key)')
            db.executemany('insert into conversation_summaries values (?)', [(self.AGY_ID,), ('user-own',)])
        self.env = dict(os.environ, HOME=str(self.home), MODEL_BRIDGE_CODEX_BIN=str(fake),
                        MODEL_BRIDGE_AGY_HOME=str(self.agy))
        self.runs = {}
        for provider, stamp, record in (
                ('codex', self.OLD, {'session_id': self.CODEX_ID, 'command': ['codex', 'exec']}),
                ('codex', self.OLD, {'session_id': '01a128ed-0000-7000-8000-000000000000',
                                     'command': ['codex', 'exec', '--ephemeral']}),
                ('agy', self.OLD, {'agy': {'conversation_ids': [self.AGY_ID]}}),
                ('claude', self.OLD, {}), ('claude', self.NEW, {})):
            run = self.cache / ('%s-%s-%s' % (provider, stamp, os.urandom(4).hex()))
            (run / 'artifacts').mkdir(parents=True)
            (run / 'result.json').write_text(json.dumps(record))
            self.runs.setdefault((provider, stamp), []).append(run)
        projects = self.home / '.claude/projects'
        encoded = lambda path: re.sub(r'[^A-Za-z0-9]', '-', str(path))
        self.old_project = projects / encoded(self.runs[('claude', self.OLD)][0] / 'artifacts')
        self.new_project = projects / encoded(self.runs[('claude', self.NEW)][0] / 'artifacts')
        self.orphan_project = projects / encoded(self.cache / 'claude-20200102T000000-deadbeef' / 'artifacts')
        self.user_project = projects / '-Users-someone-Work-repo'
        for path in (self.old_project, self.new_project, self.orphan_project, self.user_project):
            (path / 'memory').mkdir(parents=True)
        self.nonempty_orphan = projects / encoded(self.cache / 'claude-20200103T000000-cafebabe' / 'artifacts')
        self.nonempty_orphan.mkdir()
        (self.nonempty_orphan / 'session.jsonl').write_text('{}')
        self.custom = self.cache / 'my-batch-output'
        self.custom.mkdir()

    def prune(self, *extra):
        p = subprocess.run([sys.executable, str(SCRIPT), 'prune', '--older-than', '7', *extra],
                           capture_output=True, text=True, env=self.env, timeout=20)
        return p, json.loads(p.stdout) if p.stdout.strip() else None

    def test_default_only_reports(self):
        p, report = self.prune()
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual((report['runs'], report['codex_sessions'], report['agy_conversations'],
                          report['claude_empty_project_dirs']), (4, 1, 1, 2))
        self.assertFalse(self.deleted.exists())
        self.assertTrue(all(run.exists() for runs in self.runs.values() for run in runs))
        self.assertTrue(self.old_project.exists() and (self.agy / 'brain' / self.AGY_ID).exists())

    def test_apply_removes_only_old_bridge_runs_and_their_sessions(self):
        p, report = self.prune('--apply')
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(report['errors'], [])
        self.assertEqual(self.deleted.read_text().split(), ['delete', '--force', self.CODEX_ID])
        for (provider, stamp), runs in self.runs.items():
            for run in runs:
                self.assertEqual(run.exists(), stamp == self.NEW, run.name)
        self.assertFalse(self.old_project.exists())
        self.assertFalse(self.orphan_project.exists())
        self.assertTrue(self.new_project.exists())
        self.assertTrue(self.user_project.exists())
        self.assertTrue(self.nonempty_orphan.exists())
        self.assertTrue(self.custom.exists())
        self.assertFalse((self.agy / 'brain' / self.AGY_ID).exists())
        self.assertFalse((self.agy / 'conversations' / (self.AGY_ID + '.db')).exists())
        self.assertTrue((self.agy / 'brain' / 'keep-me').exists())
        with sqlite3.connect(str(self.agy / 'conversation_summaries.db')) as db:
            left = [row[0] for row in db.execute('select conversation_id from conversation_summaries')]
        self.assertEqual(left, ['user-own'])

    def test_batch_out_keeps_results_and_cleans_only_cli_leftovers(self):
        out = self.home / 'batch-out'
        run = out / 'agy_m' / 'b000-a1'
        run.mkdir(parents=True)
        (out / 'manifest.json').write_text('{}')
        (out / 'agy_m.json').write_text('{"x": 1}')
        (run / 'result.json').write_text(json.dumps({'provider': 'agy', 'agy': {'conversation_ids': [self.AGY_ID]}}))
        claude_run = out / 'claude_m' / 'b000-a1'
        claude_run.mkdir(parents=True)
        (claude_run / 'result.json').write_text(json.dumps({'provider': 'claude'}))
        leftover = self.home / '.claude/projects' / re.sub(r'[^A-Za-z0-9]', '-', str(claude_run.resolve() / 'artifacts'))
        (leftover / 'memory').mkdir(parents=True)
        p = subprocess.run([sys.executable, str(SCRIPT), 'prune', '--older-than', '100000', '--batch-out', str(out),
                            '--apply'], capture_output=True, text=True, env=self.env, timeout=20)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(json.loads(p.stdout)['batch_calls'], 2)
        self.assertFalse(leftover.exists())
        self.assertFalse((self.agy / 'brain' / self.AGY_ID).exists())
        self.assertTrue((out / 'agy_m.json').exists() and (run / 'result.json').exists())
        p = subprocess.run([sys.executable, str(SCRIPT), 'prune', '--batch-out', str(self.home)],
                           capture_output=True, text=True, env=self.env, timeout=20)
        self.assertEqual(p.returncode, 2)
        self.assertIn('manifest.json', p.stderr)

    def test_zero_age_is_refused(self):
        p = subprocess.run([sys.executable, str(SCRIPT), 'prune', '--older-than', '0', '--apply'],
                           capture_output=True, text=True, env=self.env, timeout=20)
        self.assertEqual(p.returncode, 2)
        self.assertTrue(all(run.exists() for runs in self.runs.values() for run in runs))


BATCH_FAKE = r"""
import json, os, pathlib, re, sys
args = sys.argv[1:]
if '--help' in args:
    print('Claude Code --print'); sys.exit(0)
prompt = sys.stdin.read()
ids = re.findall(r'^\[(\S+)\] ', prompt, re.M)
log = pathlib.Path(os.environ['FAKE_LOG'])
with log.open('a') as f:
    f.write(','.join(ids) + '\n')
calls = len(log.read_text().splitlines())
mode = os.environ.get('FAKE_BATCH_MODE', 'ok')
if 'POISON' in prompt:
    print(json.dumps({'type': 'result', 'subtype': 'success', 'is_error': True, 'stop_reason': 'refusal',
                      'result': "API Error: Haiku 5.5 can't help with this. Details: `[bio]`"}))
    sys.exit(1)
if mode == 'quota':
    print('Error: 429 rate limit reached', file=sys.stderr); sys.exit(1)
answer = [{'id': i, 'label': '正面'} for i in ids]
if mode == 'drop-first' and calls == 1:
    answer = answer[:-1]
text = json.dumps({'items': answer} if '--json-schema' in args else answer, ensure_ascii=False)
out = {'type': 'result', 'subtype': 'success', 'is_error': False, 'session_id': 's', 'result': text,
       'usage': {'input_tokens': 1, 'output_tokens': 1}}
print(json.dumps(out))
"""


class BatchTests(unittest.TestCase):
    """call.py batch：每批 id 必须完整；被拒二分定位到单条；额度/认证停下；续跑跳过已完成。"""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        cli = self.root / 'fake-claude'
        cli.write_text('#!%s\n%s' % (sys.executable, BATCH_FAKE))
        cli.chmod(0o700)
        self.log = self.root / 'calls.log'
        self.items = self.root / 'items.jsonl'
        texts = ['好吃', '难吃', 'POISON 一条会被拒的', '一般', '还行', '不错', '很差']
        self.items.write_text('\n'.join(json.dumps({'id': 'x%d' % i, 'text': t}, ensure_ascii=False)
                                        for i, t in enumerate(texts)))
        self.template = self.root / 'template.txt'
        self.template.write_text('标情感，只输出 JSON 数组。本批：{ids}\n\n{items}')
        self.out = self.root / 'out'
        self.env = dict(os.environ, MODEL_BRIDGE_CLAUDE_BIN=str(cli), FAKE_LOG=str(self.log))
        self.env.pop('MODEL_BRIDGE_DEPTH', None)

    def batch(self, *extra, mode='ok'):
        p = subprocess.run([sys.executable, str(SCRIPT), 'batch', '--items', str(self.items), '--template',
                            str(self.template), '--model-spec', 'claude:claude-haiku-5-5:low:2:4', '--out', str(self.out),
                            '--timeout', '10', *extra], capture_output=True, text=True,
                           env=dict(self.env, FAKE_BATCH_MODE=mode), timeout=60)
        return p, json.loads(p.stdout)[0] if p.stdout.strip().startswith('[') else None

    def calls(self):
        return [line.split(',') for line in self.log.read_text().splitlines()]

    def test_refusal_is_bisected_to_the_single_item_and_others_are_kept(self):
        p, report = self.batch()
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(report['refused_ids'], ['x2'])
        self.assertEqual((report['answered'], report['failed_batches']), (6, {}))
        answers = json.loads((self.out / (report['tag'] + '.json')).read_text())
        self.assertEqual(sorted(answers), ['x0', 'x1', 'x3', 'x4', 'x5', 'x6'])
        # 批 0 = x0..x3 被拒（不重试）→ [x0,x1] 成功、[x2,x3] 被拒 → [x2] 被拒、[x3] 成功；批 1 = x4..x6 成功。
        self.assertEqual(sorted(map(tuple, self.calls())), sorted([
            ('x0', 'x1', 'x2', 'x3'), ('x0', 'x1'), ('x2', 'x3'), ('x2',), ('x3',), ('x4', 'x5', 'x6')]))
        before = len(self.calls())
        p, report = self.batch()
        self.assertEqual((p.returncode, len(self.calls()), report['refused_ids']), (0, before, ['x2']))

    def test_incomplete_batch_is_retried_and_schema_wraps_items(self):
        self.items.write_text('\n'.join(json.dumps({'id': 'x%d' % i, 'text': 't'}) for i in range(3)))
        schema = self.root / 'item.json'
        schema.write_text(json.dumps({'type': 'object', 'required': ['id', 'label'],
                                      'properties': {'id': {'type': 'string'}, 'label': {'type': 'string'}}}))
        p, report = self.batch('--item-schema', str(schema), mode='drop-first')
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual((report['answered'], report['calls_this_run']), (3, 2))
        self.assertEqual(sorted(path.name for path in (self.out / report['tag']).iterdir() if path.is_dir()),
                        ['b000-a1', 'b000-a2'])
        self.assertEqual(json.loads((self.out / 'schema.json').read_text())['properties']['items']['items']['required'],
                         ['id', 'label'])

    def test_quota_stops_the_target_without_hammering(self):
        p, report = self.batch('--retries', '3', mode='quota')
        self.assertEqual(p.returncode, 1)
        self.assertTrue(report['stopped'].startswith('quota'))
        self.assertLessEqual(len(self.calls()), 2)  # 并发 2：最多两批各打一次，不重试
        self.assertEqual(report['answered'], 0)

    def test_resume_with_different_inputs_is_refused(self):
        self.batch()
        self.template.write_text('换了模板 {items}')
        p, _ = self.batch()
        self.assertEqual(p.returncode, 2)
        self.assertIn('manifest', p.stderr)


if __name__ == '__main__':
    unittest.main()
