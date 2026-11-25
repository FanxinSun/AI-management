import contextlib
import fcntl
import io
import json
from pathlib import Path
import sqlite3
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import send

OLD = '01a07b45-8349-7583-8526-8b68be1fdab4'
NEW = '01a07cd6-a0ef-73e2-b36b-2d7e381a59b8'
MID = '01a08056-193d-77a3-951f-5613c9ec11e8'
NAME = 'Example Supervisor (Manager)'


class DeliveryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name)
        with contextlib.closing(sqlite3.connect(self.home / 'state_5.sqlite')) as db, db:
            db.execute('CREATE TABLE threads(id TEXT,name TEXT,archived INTEGER,rollout_path TEXT,history_mode TEXT,cwd TEXT,source TEXT)')
            for tid in (OLD, NEW):
                db.execute('INSERT INTO threads VALUES(?,?,0,?,\'paginated\',\'/tmp\',\'cli\')',
                           (tid, NAME, '/tmp/' + tid + '.jsonl'))
        self.thread = send.recipients(self.home, NEW)[0][0]
        self.availability = {'online': True, 'idle': True}

    def writer(self, live):
        return lambda path: {'pid': 42, 'start_ticks': 100} if path.stem in live else None

    def test_name_selects_only_live_writer_instead_of_saved_parent(self):
        row, why = send.resolve(self.home, NAME, writer_query=self.writer({NEW}))
        self.assertEqual(row['id'], NEW)
        self.assertEqual(why, 'unique_live_exact_name')

    def test_two_live_namesakes_stay_ambiguous(self):
        with self.assertRaises(send.SendError) as caught:
            send.resolve(self.home, NAME, writer_query=self.writer({OLD, NEW}))
        self.assertEqual(caught.exception.details['state'], 'ambiguous')

    def test_all_offline_namesakes_do_not_choose_by_recency(self):
        with self.assertRaises(send.SendError):
            send.resolve(self.home, NAME, writer_query=self.writer(set()))

    def test_stale_id_is_rejected_without_silent_redirect(self):
        with self.assertRaises(send.SendError) as caught:
            send.resolve(self.home, OLD, NAME, self.writer({NEW}))
        self.assertEqual(caught.exception.details['state'], 'stale_target')

    def test_verified_offline_id_can_receive_pending_report(self):
        row, why = send.resolve(self.home, NEW, NAME, self.writer(set()))
        self.assertEqual(row['id'], NEW)
        self.assertEqual(why, 'explicit_id')

    def test_name_mismatch_rejected(self):
        with self.assertRaises(send.SendError):
            send.resolve(self.home, NEW, 'Other Manager', self.writer(set()))

    def test_archived_id_rejected(self):
        with contextlib.closing(sqlite3.connect(self.home / 'state_5.sqlite')) as db, db:
            db.execute('UPDATE threads SET archived=1 WHERE id=?', (NEW,))
        with self.assertRaises(send.SendError):
            send.resolve(self.home, NEW, NAME, self.writer(set()))

    def ack(self, tid=NEW):
        return subprocess.CompletedProcess([], 0, f'Queued message {MID} for thread {tid}.\n', '')

    def test_literal_message_is_one_argv_without_shell_and_verified(self):
        message = "line one\n`touch SHOULD_NOT_EXIST` $(false) $HOME \\\"quoted\\\"\n报告"
        def run(args, **kw):
            self.assertEqual(args, [send.CODEX, 'queue', '--thread', NEW, '--message', message])
            self.assertNotIn('shell', kw)
            return self.ack()
        payload = {'UserInput': {'content': [{'type': 'text', 'text': message}]}}
        result = send.send(self.home, self.thread, message, self.availability,
                           runner=run, verify=lambda *args: payload)
        self.assertEqual(result['verification'], 'queue_acknowledgment_and_exact_durable_payload')
        self.assertEqual(result['delivery'], 'pending_or_unconfirmed')

    def test_consumed_entry_does_not_claim_review(self):
        result = send.send(self.home, self.thread, 'report', self.availability,
                           runner=lambda *a, **k: self.ack(), verify=lambda *a: None)
        self.assertEqual(result['state'], 'queued')
        self.assertEqual(result['assessment'], 'not_established')

    def test_wrong_recipient_ack_rejected(self):
        with self.assertRaises(send.SendError):
            send.send(self.home, self.thread, 'report', self.availability,
                      runner=lambda *a, **k: self.ack(OLD))

    def test_durable_text_mismatch_rejected(self):
        with self.assertRaises(send.SendError):
            send.send(self.home, self.thread, 'report', self.availability,
                      runner=lambda *a, **k: self.ack(),
                      verify=lambda *a: {'UserInput': {'content': [{'type': 'text', 'text': 'changed'}]}})

    def test_timeout_remains_uncertain(self):
        def run(*args, **kwargs):
            raise subprocess.TimeoutExpired('codex queue', 12)
        with self.assertRaises(send.SendError) as caught:
            send.send(self.home, self.thread, 'report', self.availability, runner=run)
        self.assertTrue(caught.exception.details['may_have_queued'])
        self.assertEqual(caught.exception.details['state'], 'unconfirmed')

    def cli(self, *, availability=None, sending=None, require_idle=False, new_session_ready=None):
        message = self.home / 'report.txt'
        message.write_text('Final result\nall findings at /tmp/report.md')
        args = ['send.py', '--to', NEW, '--expect-name', NAME, '--message-file', str(message)]
        if require_idle:
            args.append('--require-idle')
        if new_session_ready:
            args.extend(['--new-session-ready', new_session_ready])
        output = io.StringIO()
        with patch('sys.argv', args), patch.dict('os.environ', {'CODEX_HOME': str(self.home)}), \
             patch.object(send, 'resolve', return_value=(self.thread, 'explicit_id')), \
             patch.object(send, 'snapshot', return_value=availability or self.availability), \
             patch.object(send, 'send', side_effect=sending) as sender, contextlib.redirect_stdout(output):
            code = send.main()
        return code, json.loads(output.getvalue()), sender.call_count

    def test_busy_handover_held_without_queue(self):
        code, result, calls = self.cli(availability={'online': True, 'idle': False}, require_idle=True)
        self.assertEqual(code, 2)
        self.assertEqual(result['state'], 'held')
        self.assertEqual(calls, 0)

    def test_success_receipt_prevents_duplicate_send(self):
        result = {'state': 'queued', 'thread_id': NEW, 'queue_message_id': MID}
        first = self.cli(sending=lambda *a: result)
        second = self.cli(sending=lambda *a: self.fail('duplicate dispatch'))
        self.assertEqual(first[2], 1)
        self.assertEqual(second[2], 0)
        self.assertTrue(second[1]['reused_receipt'])

    def test_uncertain_receipt_prevents_blind_retry(self):
        def uncertain(*a):
            raise send.SendError('timeout', state='unconfirmed', may_have_queued=True)
        first = self.cli(sending=uncertain)
        second = self.cli(sending=lambda *a: self.fail('duplicate dispatch'))
        self.assertEqual(first[0], 2)
        self.assertEqual(second[0], 2)
        self.assertTrue(second[1]['reused_receipt'])
        self.assertEqual(second[2], 0)

    def test_proven_bridge_rollback_allows_fresh_retry(self):
        def rejected(*a):
            raise send.SendError('Readiness changed; transaction rolled back', state='held', may_have_queued=False)
        first = self.cli(sending=rejected)
        self.assertEqual(first[0], 2)
        second = self.cli(sending=lambda *a: {'state': 'queued', 'thread_id': NEW, 'queue_message_id': MID})
        self.assertEqual((second[0], second[2]), (0, 1))

    def test_unregistered_busy_is_held_even_without_require_idle(self):
        self.thread['unregistered'] = True
        code, result, calls = self.cli(availability={'online': True, 'idle': False})
        self.assertEqual((code, result['state'], calls), (2, 'held', 0))

    def test_verified_first_input_accepts_existing_user_ready_statement(self):
        available = {'online': True, 'idle': None, 'state': 'new_session',
                     'awaiting_initial_input': True, 'metadata_current': True}
        code, result, calls = self.cli(availability=available, require_idle=True,
            new_session_ready='The user says this new session is online and idle.',
            sending=lambda *a: {'state': 'queued', 'thread_id': NEW, 'queue_message_id': MID})
        self.assertEqual((code, calls), (0, 1))
        self.assertEqual(result['readiness_evidence']['source'], 'current_user_readiness_for_first_input')
        self.assertIsNone(result['availability']['idle'])

    def test_automatic_first_handover_needs_no_user_readiness_argument(self):
        available = {'online': True, 'idle': True, 'state': 'new_session',
                     'awaiting_initial_input': True, 'metadata_current': True,
                     'first_input_ready': True}
        code, result, calls = self.cli(availability=available, require_idle=True,
            sending=lambda *a: {'state': 'queued', 'thread_id': NEW, 'queue_message_id': MID})
        self.assertEqual((code, calls, result['state']), (0, 1, 'queued'))
        self.assertEqual(result['readiness_evidence']['source'], 'live_writer_and_verified_pristine_store')
        self.assertNotIn('user_statement', result['readiness_evidence'])

    def test_incomplete_new_session_cannot_claim_automatic_readiness(self):
        available = {'online': True, 'idle': True, 'state': 'new_session',
                     'awaiting_initial_input': True, 'metadata_current': False,
                     'first_input_ready': True}
        code, result, calls = self.cli(availability=available, require_idle=True)
        self.assertEqual((code, calls, result['state']), (2, 0, 'held'))

    def test_another_sender_to_same_recipient_holds_even_different_request(self):
        directory = self.home / 'session-send-receipts' / 'recipient-locks'
        directory.mkdir(parents=True)
        with (directory / (NEW + '.lock')).open('a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            code, result, calls = self.cli(require_idle=True)
            self.assertEqual((code, calls, result['state']), (2, 0, 'held'))
        code, result, calls = self.cli(require_idle=True,
            sending=lambda *a: {'state': 'queued', 'thread_id': NEW, 'queue_message_id': MID})
        self.assertEqual((code, calls), (0, 1))

    def test_new_session_without_ready_signal_is_held(self):
        available = {'online': True, 'idle': None, 'state': 'new_session',
                     'awaiting_initial_input': True, 'metadata_current': True}
        code, result, calls = self.cli(availability=available, require_idle=True)
        self.assertEqual((code, calls, result['state']), (2, 0, 'held'))
        self.assertFalse(result['initialization_required'])
        self.assertEqual(result['first_input_transport'], 'codex_queue')
        self.assertEqual(result['required_action'], 'confirm_current_first_input_readiness')

    def test_readiness_confirmation_can_release_held_first_input_without_dummy_message(self):
        available = {'online': True, 'idle': None, 'state': 'new_session',
                     'awaiting_initial_input': True, 'metadata_current': True}
        code, result, calls = self.cli(availability=available, require_idle=True)
        self.assertEqual((code, calls), (2, 0))
        code, result, calls = self.cli(availability=available, require_idle=True,
            new_session_ready='Yes, Tester is open and idle.',
            sending=lambda *a: {'state': 'queued', 'thread_id': NEW, 'queue_message_id': MID})
        self.assertEqual((code, calls, result['state']), (0, 1, 'queued'))

    def test_unknown_state_does_not_claim_first_input_supported(self):
        code, result, calls = self.cli(availability={'online': True, 'idle': None,
                                                   'state': 'unknown'}, require_idle=True)
        self.assertEqual((code, calls), (2, 0))
        self.assertNotIn('first_input_transport', result)

    def test_readiness_statement_never_overrides_busy_offline_or_unknown(self):
        for available in [
            {'online': True, 'idle': False, 'state': 'busy'},
            {'online': False, 'idle': None, 'state': 'offline'},
            {'online': True, 'idle': None, 'state': 'unknown'},
            {'online': True, 'idle': None, 'state': 'new_session', 'awaiting_initial_input': True, 'metadata_current': False},
            {'online': True, 'idle': False, 'state': 'new_session', 'awaiting_initial_input': True, 'metadata_current': True},
        ]:
            with self.subTest(state=available['state']):
                code, result, calls = self.cli(availability=available, require_idle=True,
                    new_session_ready='The user says this new session is idle.')
                self.assertEqual((code, calls), (2, 0))


class UnregisteredDeliveryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name)
        self.owner = {'pid': 42, 'start_ticks': 100, 'inode': 20, 'device': 1}
        with contextlib.closing(sqlite3.connect(self.home / 'state_5.sqlite')) as db, db:
            db.execute('CREATE TABLE threads(id,name,archived,rollout_path,history_mode,cwd,source)')
        with contextlib.closing(sqlite3.connect(self.home / 'thread_history_1.sqlite')) as db, db:
            for table in ['thread_turns', 'thread_items', 'thread_history_projection_state', 'thread_realtime_items']:
                db.execute(f'CREATE TABLE {table}(thread_id)')
        with contextlib.closing(sqlite3.connect(self.home / 'queue_1.sqlite')) as db, db:
            db.executescript(Path(__file__).with_name('queue-schema-0.154.0.sql').read_text())
            db.execute('CREATE TABLE _sqlx_migrations(version,description,success)')
            db.executemany('INSERT INTO _sqlx_migrations VALUES (?,?,1)', [(1,'queued items'),(2,'queued thread revisions')])
        self.thread = send.status.resolve_unregistered(self.home, NEW, lambda path: self.owner,
                                                       lambda *a: '/project')
        self.available = {'thread_id': NEW, 'online': True, 'idle': True, 'state': 'new_session',
                          'writer_identity': self.owner, **send.status.unregistered_input_snapshot(self.home, self.thread)}

    def bridge(self, **kw):
        return send.bridge_first_input(self.home, self.thread, 'Approved brief\n$(literal) 报告', self.available,
            writer_query=kw.get('writer_query', lambda path: self.owner), owner_query=lambda *a: '/project',
            version_query=kw.get('version_query', lambda: 'codex-cli 0.154.0'))

    def test_exact_uuid_without_name_resolves(self):
        with patch.object(send.status, 'visible_initial_owner', return_value='/project'):
            result, why = send.resolve(self.home, NEW, writer_query=lambda path: self.owner)
            self.assertEqual((result['id'], result['name'], why), (NEW, None, 'explicit_id'))
            with self.assertRaises(send.SendError):
                send.resolve(self.home, NEW, 'Invented name', writer_query=lambda path: self.owner)

    def test_bridge_matches_native_payload_revision_and_creates_no_thread(self):
        result = self.bridge()
        self.assertEqual(result['state'], 'queued')
        payload = send.queued_payload(self.home, result['queue_message_id'], NEW)
        self.assertEqual(send.payload_text(payload), 'Approved brief\n$(literal) 报告')
        self.assertEqual(send.uuid.UUID(payload['UserInput']['client_id']).version, 7)
        with send.status.read_db(self.home / 'queue_1.sqlite') as db:
            self.assertEqual(db.execute('SELECT count(*) FROM queued_items').fetchone()[0], 1)
            self.assertEqual(db.execute('SELECT revision FROM queued_thread_revisions').fetchone()[0], result['queue_revision'])
        with send.status.read_db(self.home / 'state_5.sqlite') as db:
            self.assertEqual(db.execute('SELECT count(*) FROM threads').fetchone()[0], 0)
        with self.assertRaises(send.status.StatusError):
            self.bridge()  # Even a consumed prior input retains a revision.

    def test_unknown_version_and_schema_fail_without_queue(self):
        with self.assertRaises(send.SendError):
            self.bridge(version_query=lambda: 'codex-cli 0.999.0')
        with contextlib.closing(sqlite3.connect(self.home / 'queue_1.sqlite')) as db, db:
            db.execute('DROP TRIGGER queued_items_revision_after_insert')
        with self.assertRaises(send.SendError):
            self.bridge()
        with send.status.read_db(self.home / 'queue_1.sqlite') as db:
            self.assertEqual(db.execute('SELECT count(*) FROM queued_items').fetchone()[0], 0)

    def test_writer_exit_before_commit_rolls_back_queue_and_revision(self):
        calls = 0
        def writer(path):
            nonlocal calls
            calls += 1
            return self.owner if calls <= 4 else None
        with self.assertRaises(send.SendError):
            self.bridge(writer_query=writer)
        with send.status.read_db(self.home / 'queue_1.sqlite') as db:
            self.assertEqual(db.execute('SELECT count(*) FROM queued_items').fetchone()[0], 0)
            self.assertEqual(db.execute('SELECT count(*) FROM queued_thread_revisions').fetchone()[0], 0)

    def test_registration_or_incomplete_evidence_blocks_first_input(self):
        self.available['idle'] = False
        with self.assertRaises(send.SendError):
            self.bridge()
        self.available['idle'] = True
        with contextlib.closing(sqlite3.connect(self.home / 'state_5.sqlite')) as db, db:
            db.execute('INSERT INTO threads(id) VALUES (?)', (NEW,))
        with self.assertRaises(send.status.StatusError):
            self.bridge()


if __name__ == '__main__':
    unittest.main()
