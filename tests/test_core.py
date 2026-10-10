from pathlib import Path
import copy
import json
import os
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
from jarvis.core import Core, SYSTEM
from jarvis.config import Config, atomic_write, secure_read
from jarvis.memory import bounded_context
from jarvis.providers import OpenAIProvider, ProviderError, Cancellation, validate_url
from jarvis.system import intent
from tests.fake_node import Node


class CoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.core = Core(self.root / 'config', self.root / 'data')
        self.node = Node()
        self.core.config.update_profile('tablet', {'enabled': True, 'url': self.node.url}, self.node.key)

    def tearDown(self):
        self.node.close()
        self.temp.cleanup()

    def chat(self, prompt='Explain RAM.', **extra):
        return list(self.core.request({'method': 'chat', 'prompt': prompt, **extra}))

    def test_deterministic_bypasses_inference(self):
        events = self.chat('what time is it?')
        self.assertEqual(events[1]['kind'], 'system')
        self.assertEqual(events[-1]['type'], 'done')
        self.assertFalse(self.node.requests)

    def test_real_sse_and_history(self):
        events = self.chat()
        self.assertEqual(''.join(e['text'] for e in events if e['type'] == 'token'), 'Hello Aman — local stream.')
        self.assertEqual(sum(e['type'] == 'token' for e in events), 4)
        self.assertTrue(events[-1]['saved'])
        self.assertTrue(self.node.requests[0]['stream'])
        conversation = next(e['id'] for e in events if e['type'] == 'conversation')
        self.assertEqual(len(self.core.memory.history(conversation)), 2)
        self.chat('More about RAM.', conversation=conversation)
        self.assertEqual(len(self.node.requests[-1]['messages']), 4)

    def test_probe_authentication(self):
        event = list(self.core.request({'method': 'probe', 'id': 'tablet'}))[-1]
        self.assertEqual(event['value']['models'], ['smollm2-360m'])
        self.core.config.update_profile('tablet', {}, 'wrong-key')
        with self.assertRaises(ProviderError):
            list(self.core.request({'method': 'probe', 'id': 'tablet'}))

    def test_cancel_stalled_stream_without_blocking(self):
        self.node.behavior = 'stall'
        events = []
        thread = threading.Thread(target=lambda: events.extend(self.chat()), daemon=True)
        thread.start()
        self.assertTrue(self.node.started.wait(2))
        generation = next(iter(self.core.active))
        began = time.monotonic()
        list(self.core.request({'method': 'cancel', 'generation': generation}))
        self.assertLess(time.monotonic() - began, 0.5)
        thread.join(2)
        self.assertFalse(thread.is_alive())
        self.assertTrue(events[-1]['cancelled'])
        self.assertFalse(self.core.active)

    def test_partial_failure_not_saved_or_concatenated(self):
        self.node.behavior = 'disconnect'
        events = self.chat()
        self.assertEqual(events[-1]['type'], 'error')
        ident = next(e['id'] for e in events if e['type'] == 'conversation')
        self.assertFalse(self.core.memory.history(ident))

    def test_quota_fallback_to_second_local_node(self):
        self.node.behavior = 'quota'
        other = Node()
        try:
            self.core.config.update_profile('advanced', {'enabled': True, 'url': other.url}, other.key)
            events = self.chat()
            self.assertEqual(events[-1]['route'], 'advanced_local')
            self.assertEqual(len(other.requests), 1)
        finally:
            other.close()

    def test_failure_does_not_disable_system(self):
        self.node.behavior = 'malformed'
        with self.assertRaisesRegex(ValueError, 'All allowed providers failed'):
            self.chat()
        self.assertEqual(self.chat('show RAM usage')[-1]['route'], 'system')
        self.assertFalse(self.core.active)
        self.assertEqual(len(self.node.requests), 1)

    def test_memory_search_confirm_delete_replay(self):
        event = list(self.core.request({'method': 'remember', 'content': 'Project ReLife recycles plastic.'}))[-1]
        ident = event['value']
        self.assertTrue(self.core.memory.relevant('ReLife progress'))
        self.assertFalse(self.core.memory.relevant('Weather outside'))
        event = list(self.core.request({'method': 'delete_fact', 'id': ident}))[-1]
        self.assertEqual(event['type'], 'confirmation')
        list(self.core.request({'method': 'confirm', 'nonce': event['nonce']}))
        self.assertFalse(self.core.memory.facts())
        with self.assertRaisesRegex(ValueError, 'expired or already used'):
            list(self.core.request({'method': 'confirm', 'nonce': event['nonce']}))

    def test_confirmation_expiry_and_folder_traversal(self):
        event = self.chat('create a folder called Projects')[-1]
        self.assertEqual(event['type'], 'confirmation')
        action, _ = self.core.pending[event['nonce']]
        self.core.pending[event['nonce']] = (action, time.monotonic() - 1)
        with self.assertRaises(ValueError):
            list(self.core.request({'method': 'confirm', 'nonce': event['nonce']}))
        with self.assertRaises(ValueError):
            intent('create a folder called ../../bad')
        self.assertIsNone(intent('open firefox; rm -rf /'))

    def test_private_keys_and_config_persistence(self):
        key_path = self.root / 'config/secrets/tablet.key'
        self.assertEqual(key_path.stat().st_mode & 0o777, 0o600)
        self.core.config.preferences({'mode': 'local_only'})
        config = Config(self.root / 'config')
        self.assertEqual(config.data['nodes'][0]['url'], self.node.url)
        self.assertEqual(config.data['mode'], 'local_only')
        key_path.chmod(0o644)
        with self.assertRaises(ValueError):
            config.key(config.data['nodes'][0])

    def test_router_modes_and_sensitive_data(self):
        config = self.core.config
        config.data['cloud_enabled'] = True
        config.data['cloud'][0]['enabled'] = True
        router = self.core.router
        profiles, consent = router.candidates('Explain RAM')
        self.assertFalse(consent)
        self.assertEqual(profiles[0]['kind'], 'local')
        profiles, _ = router.candidates('Analyse a complex architecture')
        self.assertEqual(profiles[0]['kind'], 'cloud')
        profiles, _ = router.candidates('Complex architecture password=secret')
        self.assertTrue(all(p['kind'] != 'cloud' for p in profiles))
        config.data['mode'] = 'ask_before_cloud'
        profiles, consent = router.candidates('Complex architecture')
        self.assertTrue(consent)
        profiles, consent = router.candidates('Complex architecture', consent=False)
        self.assertFalse(consent)
        self.assertTrue(all(p['kind'] != 'cloud' for p in profiles))
        config.data['mode'] = 'local_only'
        with self.assertRaises(ValueError):
            router.candidates('Hi', requested='cloud')

    def test_cloud_receives_only_current_question(self):
        config = self.core.config
        config.data['cloud_enabled'] = True
        cloud = config.data['cloud'][0]
        cloud.update(enabled=True, model='fixture-cloud')
        ident = self.core.memory.new()
        self.core.memory.save(ident, 'Private past', 'Private reply', 'local')
        self.core.memory.remember('Architecture private fact')
        captured = []
        class Stub:
            def __init__(self, *_):
                pass
            def stream(self, messages, cancel):
                captured.extend(messages)
                yield 'Answer'
        with patch('jarvis.core.OpenAIProvider', Stub):
            self.chat('Explain a complex architecture', conversation=ident)
        self.assertEqual(len(captured), 2)
        self.assertNotIn('Private past', json.dumps(captured))
        self.assertNotIn('private fact', json.dumps(captured))

    def test_context_is_bounded_and_rejects_oversize(self):
        profile = self.core.config.data['nodes'][0]
        history = [{'role': role, 'content': 'x' * 200} for _ in range(40) for role in ['user', 'assistant']]
        messages = bounded_context(SYSTEM, history, 'RAM?', profile)
        budget = profile['context_tokens'] - profile['max_tokens'] - 256
        self.assertLessEqual(sum(len(m['content'].encode()) + 16 for m in messages), budget)
        with self.assertRaises(ValueError):
            bounded_context(SYSTEM, [], 'x' * 6000, profile)

    def test_large_unicode_history_is_framed(self):
        from jarvis.ipc import MAX_FRAME
        ident = self.core.memory.new()
        content = '🧠' * 48000
        self.core.memory.save(ident, 'Long reply', content, 'local')
        frames = list(self.core.request({'method': 'history_stream', 'conversation': ident}))
        self.assertEqual(''.join(e['text'] for e in frames if e['type'] == 'history_chunk'), 'Long reply' + content)
        self.assertTrue(all(len(json.dumps(e, ensure_ascii=False).encode()) < MAX_FRAME for e in frames))
        self.assertFalse(self.core.memory.history(ident))

    def test_disabling_history_does_not_store_conversations(self):
        self.core.config.preferences({'history_enabled': False, 'memory_enabled': False})
        events = self.chat()
        self.assertFalse(events[-1]['saved'])
        self.assertFalse(self.core.memory.conversations())
        with self.assertRaises(ValueError):
            list(self.core.request({'method': 'remember', 'content': 'Secret'}))

    def test_regenerate_trims_previous_pair(self):
        events = self.chat()
        ident = next(e['id'] for e in events if e['type'] == 'conversation')
        self.chat(conversation=ident, regenerate=True)
        self.assertEqual(len(self.node.requests[-1]['messages']), 2)

    def test_no_redirect_or_public_local_endpoint(self):
        for url in ['http://8.8.8.8/v1', 'http://user:pass@127.0.0.1/v1', 'http://192.168.0.2:8080/v1']:
            with self.assertRaises(ValueError):
                validate_url(url, 'local')
        self.assertEqual(validate_url('http://192.168.0.2:8080/v1', 'local', True), 'http://192.168.0.2:8080/v1')
        with self.assertRaises(ValueError):
            validate_url('https://evil.example/v1', 'cloud')

    def test_close_at_first_event_releases_generation(self):
        stream = self.core.request({'method': 'chat', 'prompt': 'RAM?'})
        self.assertEqual(next(stream)['type'], 'generation')
        stream.close()
        self.assertFalse(self.core.active)
        self.assertEqual(self.chat('what time is it?')[-1]['route'], 'system')

    def test_failed_reload_preserves_working_configuration(self):
        original = copy.deepcopy(self.core.config.data)
        atomic_write(self.root / 'config/preferences.json', '{"mode": "broken"}')
        with self.assertRaises(ValueError):
            list(self.core.request({'method': 'reload'}))
        self.assertEqual(self.core.config.data, original)
        self.assertEqual(self.chat()[-1]['route'], 'local')

    def test_provider_boolean_types_and_key_paths(self):
        for changes in ({'enabled': 'false'}, {'allow_insecure_lan': 'false'}):
            with self.assertRaises(ValueError):
                self.core.config.update_profile('tablet', changes)
        self.assertIs(self.core.config.data['nodes'][0]['enabled'], True)

    def test_privacy_changes_blocked_during_generation(self):
        stream = self.core.request({'method': 'chat', 'prompt': 'RAM?'})
        next(stream)
        try:
            with self.assertRaisesRegex(ValueError, 'Stop generation'):
                list(self.core.request({'method': 'preferences', 'changes': {'history_enabled': False}}))
        finally:
            stream.close()

    def test_large_unicode_facts_fit_ipc_and_remain_saved(self):
        from jarvis.ipc import MAX_FRAME
        for _ in range(100):
            self.core.memory.remember('🧠' * 2000)
        event = list(self.core.request({'method': 'facts'}))[-1]
        self.assertLess(len(json.dumps(event, ensure_ascii=False).encode()), MAX_FRAME)
        with self.core.memory.connect() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM facts').fetchone()[0], 100)

    def test_malformed_sse_shapes_fail_cleanly(self):
        for behavior in ('null-choices', 'bad-delta', 'array-event'):
            with self.subTest(behavior=behavior):
                self.node.behavior = behavior
                self.core.router.cooldown.clear()
                with self.assertRaisesRegex(ValueError, 'All allowed providers failed'):
                    self.chat()
                self.assertFalse(self.core.active)
                self.assertEqual(self.chat('show RAM usage')[-1]['route'], 'system')

    def test_malformed_models_report_provider_error(self):
        self.node.behavior = 'bad-models'
        with self.assertRaises(ProviderError):
            list(self.core.request({'method': 'probe', 'id': 'tablet'}))

    def test_disabled_cloud_does_not_request_consent(self):
        self.core.config.preferences({'mode': 'ask_before_cloud', 'cloud_enabled': True})
        profiles, consent = self.core.router.candidates('Explain a complex architecture')
        self.assertFalse(consent)
        self.assertEqual(profiles[0]['kind'], 'local')

    def test_cloud_http_quota_and_outage_fall_back_to_local(self):
        cloud_node = Node()
        config = self.core.config
        config.preferences({'cloud_enabled': True})
        config.update_profile('groq', {'enabled': True, 'model': 'fixture-cloud'}, cloud_node.key)
        original_request = OpenAIProvider.request
        # Test-only transport seam: approved production URL validation is intact.
        # Send the cloud-shaped request to an authenticated loopback HTTP fixture.
        def fixture_request(provider, suffix, payload=None):
            if provider.profile['kind'] == 'cloud':
                provider.base = cloud_node.url
            return original_request(provider, suffix, payload)
        try:
            for behavior in ('quota', 'malformed', 'ok'):
                with self.subTest(behavior=behavior):
                    cloud_node.behavior = behavior
                    self.core.router.cooldown.clear()
                    with patch.object(OpenAIProvider, 'request', fixture_request):
                        events = self.chat('Explain a complex architecture')
                    expected = 'cloud' if behavior == 'ok' else 'local'
                    self.assertEqual(events[-1]['route'], expected)
            for request in cloud_node.requests:
                self.assertEqual([x['role'] for x in request['messages']], ['system', 'user'])
            self.node.behavior = 'malformed'
            cloud_node.behavior = 'quota'
            self.core.router.cooldown.clear()
            with patch.object(OpenAIProvider, 'request', fixture_request):
                with self.assertRaises(ValueError):
                    self.chat('Explain a complex architecture')
            self.assertEqual(self.chat('show RAM usage')[-1]['route'], 'system')
        finally:
            cloud_node.close()

    def test_llm_text_never_becomes_a_system_action(self):
        class Hostile:
            def __init__(self, *_):
                pass
            def stream(self, messages, cancel):
                yield 'shutdown; rm -rf /; open terminal'
        with patch('jarvis.core.OpenAIProvider', Hostile), patch('jarvis.core.perform') as action:
            self.chat('Explain RAM.')
        action.assert_not_called()

    def test_folder_creation_requires_confirmation(self):
        with patch('jarvis.system.Path.home', return_value=self.root):
            event = self.chat('create a folder called SafeFolder')[-1]
            self.assertFalse((self.root / 'SafeFolder').exists())
            list(self.core.request({'method': 'confirm', 'nonce': event['nonce']}))
            self.assertTrue((self.root / 'SafeFolder').is_dir())


if __name__ == '__main__':
    unittest.main()
