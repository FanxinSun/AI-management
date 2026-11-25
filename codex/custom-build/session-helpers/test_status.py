from contextlib import closing
import importlib.util
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch


spec = importlib.util.spec_from_file_location('session_status', Path(__file__).with_name('status.py'))
status = importlib.util.module_from_spec(spec)
spec.loader.exec_module(status)
THREAD = '11111111-2222-4333-8444-555555555555'
OWNER = {'pid': 42, 'start_ticks': 1234, 'device': 1, 'inode': 2}


class AvailabilityTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name)
        (self.home / 'sessions').mkdir()
        self.rollout = self.home / 'sessions' / f'rollout-test-{THREAD}.jsonl'
        self.rollout.write_bytes(b'content must never be read\n')
        with closing(sqlite3.connect(self.home / 'state_5.sqlite')) as con, con:
            con.execute("CREATE TABLE threads (id, name, archived, rollout_path, history_mode, source DEFAULT 'cli', has_user_event DEFAULT 0, tokens_used DEFAULT 0, first_user_message DEFAULT '', created_at DEFAULT 100, updated_at DEFAULT 100)")
            con.execute('INSERT INTO threads (id,name,archived,rollout_path,history_mode) VALUES (?,?,?,?,?)',
                        (THREAD, "Executor ' with spaces", 0, str(self.rollout), 'paginated'))
        with closing(sqlite3.connect(self.home / 'thread_history_1.sqlite')) as con, con:
            con.execute('CREATE TABLE thread_turns (thread_id,turn_id,rollout_ordinal,status,started_at,completed_at)')
            con.execute('CREATE TABLE thread_history_projection_state (thread_id,next_rollout_byte_offset)')
            con.execute('CREATE TABLE thread_items (thread_id)')
            con.execute('CREATE TABLE thread_realtime_items (thread_id)')
            con.execute('INSERT INTO thread_history_projection_state VALUES (?,?)',
                        (THREAD, self.rollout.stat().st_size))
        with closing(sqlite3.connect(self.home / 'queue_1.sqlite')) as con, con:
            con.execute('CREATE TABLE queued_items (thread_id)')

    def set_turn(self, turn_state):
        with closing(sqlite3.connect(self.home / 'thread_history_1.sqlite')) as con, con:
            con.execute('DELETE FROM thread_turns')
            con.execute('INSERT INTO thread_turns VALUES (?,?,?,?,?,?)',
                        (THREAD, 'turn-1', 1, turn_state, 100, None if turn_state == 'inProgress' else 200))

    def snapshot(self, owner=OWNER):
        return status.inspect_session(
            self.home, "Executor ' with spaces",
            rpc_query=lambda home, tid: ({'status': {'type': 'notLoaded'}}, None),
            writer_query=lambda path: owner,
        )

    def test_embedded_busy_despite_not_loaded(self):
        self.set_turn('inProgress')
        result = self.snapshot()
        self.assertEqual((result['online'], result['idle'], result['state']), (True, False, 'busy'))
        self.assertEqual(result['last_turn']['status'], 'inProgress')

    def test_embedded_completed_is_idle_not_whole_task_completion(self):
        self.set_turn('completed')
        result = self.snapshot()
        self.assertEqual((result['online'], result['idle']), (True, True))
        self.assertEqual(result['original_task_completion'], 'not_assessed')

    def test_interrupted_and_failed_are_terminal_but_not_task_completion(self):
        for value in ['interrupted', 'failed']:
            self.set_turn(value)
            result = self.snapshot()
            self.assertTrue(result['idle'])
            self.assertEqual(result['last_turn']['status'], value)
            self.assertEqual(result['original_task_completion'], 'not_assessed')

    def test_completed_record_without_live_owner_is_offline(self):
        self.set_turn('completed')
        result = self.snapshot(owner=None)
        self.assertEqual((result['online'], result['idle'], result['state']), (False, None, 'offline'))

    def test_lagging_projection_cannot_claim_idle(self):
        self.set_turn('completed')
        with self.rollout.open('ab') as stream:
            stream.write(b'new turn not yet projected\n')
        result = self.snapshot()
        self.assertTrue(result['online'])
        self.assertIsNone(result['idle'])

    def test_file_change_during_query_cannot_claim_idle(self):
        self.set_turn('completed')
        identity = status.file_identity(self.rollout)
        with patch.object(status, 'file_identity', side_effect=[identity, (*identity[:3], identity[3] + 1)]):
            self.assertIsNone(self.snapshot()['idle'])

    def test_missing_projection_or_unknown_status_is_unknown(self):
        self.set_turn('futureStatus')
        self.assertIsNone(self.snapshot()['idle'])
        self.set_turn('completed')
        with closing(sqlite3.connect(self.home / 'thread_history_1.sqlite')) as con, con:
            con.execute('DELETE FROM thread_history_projection_state')
        self.assertIsNone(self.snapshot()['idle'])

    def test_owner_change_or_pid_reuse_cannot_claim_idle(self):
        turn = {'metadata_current': True, 'last_turn': {'status': 'completed'}}
        for next_owner in [None, {**OWNER, 'start_ticks': 9999}]:
            result = status.classify_local(OWNER, next_owner, turn)
            self.assertIsNone(result['idle'])
            self.assertIsNone(result['online'])

    def test_duplicate_names_return_candidates_without_status_query(self):
        with closing(sqlite3.connect(self.home / 'state_5.sqlite')) as con, con:
            con.execute('INSERT INTO threads (id,name,archived,rollout_path,history_mode) SELECT ?,name,archived,rollout_path,history_mode FROM threads',
                        ('99999999-2222-4333-8444-555555555555',))
        result = self.snapshot()
        self.assertEqual(result['state'], 'ambiguous')
        self.assertEqual(len(result['candidates']), 2)

    def test_shared_active_waiting_is_busy(self):
        result = status.inspect_session(
            self.home, THREAD,
            rpc_query=lambda home, tid: ({'status': {'type': 'active',
                'activeFlags': ['waitingOnUserInput']}, 'canAcceptDirectInput': True}, None),
            writer_query=lambda path: self.fail('Live RPC should be authoritative'),
        )
        self.assertEqual((result['online'], result['idle']), (True, False))
        self.assertEqual(result['active_flags'], ['waitingOnUserInput'])

    def test_no_daemon_still_uses_embedded_status(self):
        self.set_turn('completed')
        result = status.inspect_session(
            self.home, THREAD, rpc_query=lambda home, tid: (None, 'connection refused'),
            writer_query=lambda path: OWNER,
        )
        self.assertTrue(result['idle'])

    def test_never_opens_rollout_content(self):
        self.set_turn('completed')
        with patch.object(Path, 'open', side_effect=AssertionError('Transcript content read')):
            self.assertTrue(self.snapshot()['idle'])

    def test_legacy_metadata_is_explicitly_unsupported(self):
        with closing(sqlite3.connect(self.home / 'state_5.sqlite')) as con, con:
            con.execute("UPDATE threads SET history_mode='legacy'")
        result = self.snapshot()
        self.assertTrue(result['online'])
        self.assertIsNone(result['idle'])
        self.assertIn('Legacy', result['detail'])

    def test_kernel_lock_is_live_only_while_held(self):
        lock = self.home / 'writer.lock'
        script = ('import fcntl,sys\n'
                  'with open(sys.argv[1],"w") as f:\n'
                  ' fcntl.flock(f,fcntl.LOCK_EX)\n'
                  ' print("locked",flush=True)\n'
                  ' sys.stdin.read(1)\n')
        child = subprocess.Popen([sys.executable, '-c', script, str(lock)],
                                 stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
        try:
            self.assertEqual(child.stdout.readline().strip(), 'locked')
            owner = status.writer_snapshot(lock, owner_check=lambda pid: 1)
            self.assertEqual(owner['pid'], child.pid)
        finally:
            child.communicate('x', timeout=3)
        self.assertTrue(lock.exists())
        self.assertIsNone(status.writer_snapshot(lock, owner_check=lambda pid: 1))

    def pristine(self):
        self.rollout.unlink()
        with closing(sqlite3.connect(self.home / 'thread_history_1.sqlite')) as con, con:
            con.execute('DELETE FROM thread_history_projection_state')

    def unregistered(self):
        self.pristine()
        with closing(sqlite3.connect(self.home / 'state_5.sqlite')) as db, db:
            db.execute('DELETE FROM threads')
        with closing(sqlite3.connect(self.home / 'queue_1.sqlite')) as db, db:
            db.execute('CREATE TABLE queued_thread_revisions (thread_id, revision)')

    def unnamed_snapshot(self):
        with patch.object(status, 'visible_initial_owner', return_value='/project'):
            return status.inspect_session(self.home, THREAD, writer_query=lambda path: OWNER,
                rpc_query=lambda *a: self.fail('Unregistered visible TUI does not use another server'))

    def test_unregistered_uuid_is_ready_without_creating_metadata(self):
        self.unregistered()
        result = self.unnamed_snapshot()
        self.assertEqual((result['online'], result['idle'], result['state']), (True, True, 'new_session'))
        self.assertEqual(result['first_input_transport'], 'verified_unregistered_queue_bridge')
        self.assertIsNone(result['name'])
        with closing(sqlite3.connect(self.home / 'state_5.sqlite')) as db:
            self.assertEqual(db.execute('SELECT count(*) FROM threads').fetchone()[0], 0)
        self.assertFalse(self.rollout.exists())

    def test_unregistered_prior_queue_revision_rejects_readiness(self):
        self.unregistered()
        with closing(sqlite3.connect(self.home / 'queue_1.sqlite')) as db, db:
            db.execute('INSERT INTO queued_thread_revisions VALUES (?,1)', (THREAD,))
        self.assertIsNone(self.unnamed_snapshot()['idle'])

    def test_unregistered_compressed_or_prior_history_rejects_readiness(self):
        self.unregistered()
        Path(str(self.rollout) + '.zst').write_bytes(b'existing')
        self.assertIsNone(self.unnamed_snapshot()['idle'])
        Path(str(self.rollout) + '.zst').unlink()
        self.set_turn('completed')
        self.assertIsNone(self.unnamed_snapshot()['idle'])

    def test_unregistered_offline_or_owner_change_not_resolved(self):
        self.unregistered()
        self.assertIsNone(status.resolve_unregistered(self.home, THREAD, lambda path: None))
        with patch.object(status, 'visible_initial_owner', return_value='/project'):
            owners = iter([OWNER, {**OWNER, 'start_ticks': 999}])
            with self.assertRaises(status.StatusError):
                status.resolve_unregistered(self.home, THREAD, lambda path: next(owners))

    def test_unregistered_hidden_and_other_thread_writer_rejected(self):
        proc_root = self.home / 'proc'
        proc = proc_root / str(OWNER['pid'])
        (proc / 'fd').mkdir(parents=True)
        (proc / 'stat').write_text('42 (codex) S 1 42 42 34822 42 0')
        (proc / 'cmdline').write_bytes(b'codex\0')
        (proc / 'cwd').symlink_to('/project')
        for fd in (0, 1, 2):
            (proc / f'fd/{fd}').symlink_to('/dev/pts/6')
        (proc / 'fd/3').symlink_to(self.home / 'state_5.sqlite')
        (proc / 'fd/4').symlink_to(self.home / 'thread-writer-locks' / (THREAD + '.lock'))
        self.assertEqual(status.visible_initial_owner(self.home, THREAD, OWNER, proc_root), '/project')
        (proc / 'cmdline').write_bytes(b'codex\0exec\0')
        with self.assertRaises(status.StatusError):
            status.visible_initial_owner(self.home, THREAD, OWNER, proc_root)
        (proc / 'cmdline').write_bytes(b'codex\0')
        (proc / 'fd/5').symlink_to(self.home / 'thread-writer-locks/another.lock')
        with self.assertRaises(status.StatusError):
            status.visible_initial_owner(self.home, THREAD, OWNER, proc_root)

    def test_verified_new_live_session_is_ready_for_first_input(self):
        self.pristine()
        result = self.snapshot()
        self.assertEqual(result['state'], 'new_session')
        self.assertTrue(result['online'])
        self.assertTrue(result['awaiting_initial_input'])
        self.assertFalse(result['initialization_required'])
        self.assertEqual(result['first_input_transport'], 'codex_queue')
        self.assertTrue(result['idle'])
        self.assertTrue(result['first_input_ready'])
        self.assertEqual(result['readiness_source'], 'live_writer_and_verified_pristine_store')
        self.assertEqual(result['original_task_completion'], 'not_assessed')

    def test_missing_established_history_is_not_new(self):
        self.set_turn('completed')
        self.rollout.unlink()
        self.assertEqual(self.snapshot()['state'], 'unknown')

    def test_missing_history_with_activity_cannot_offer_first_input(self):
        self.set_turn('inProgress')
        self.rollout.unlink()
        result = self.snapshot()
        self.assertEqual(result['state'], 'unknown')
        self.assertNotIn('first_input_transport', result)

    def test_first_input_requires_complete_evidence_not_just_missing_turn(self):
        incomplete = {'metadata_current': True, 'last_turn': None,
                      'awaiting_initial_input': True}
        self.assertIsNone(status.classify_local(OWNER, OWNER, incomplete)['idle'])

    def test_first_input_owner_change_cannot_claim_readiness(self):
        self.pristine()
        new = status.local_turn_snapshot(self.home, status.resolve_thread(self.home, THREAD)[0])
        result = status.classify_local(OWNER, {**OWNER, 'start_ticks': 999}, new)
        self.assertIsNone(result['idle'])
        self.assertNotIn('first_input_ready', result)

    def test_new_candidate_with_pending_input_is_not_ready(self):
        self.pristine()
        with closing(sqlite3.connect(self.home / 'queue_1.sqlite')) as con, con:
            con.execute('INSERT INTO queued_items VALUES (?)', (THREAD,))
        self.assertEqual(self.snapshot()['state'], 'unknown')

    def test_new_candidate_with_prior_activity_or_subagent_source_is_unknown(self):
        self.pristine()
        for field, value, default in [('has_user_event', 1, 0), ('tokens_used', 10, 0),
                                      ('first_user_message', 'prior message', ''),
                                      ('updated_at', 101, 100), ('source', 'subagent', 'cli')]:
            with self.subTest(field=field):
                with closing(sqlite3.connect(self.home / 'state_5.sqlite')) as con, con:
                    con.execute(f'UPDATE threads SET {field}=?', (value,))
                self.assertEqual(self.snapshot()['state'], 'unknown')
                with closing(sqlite3.connect(self.home / 'state_5.sqlite')) as con, con:
                    con.execute(f'UPDATE threads SET {field}=?', (default,))

    def test_compressed_history_is_not_new(self):
        self.pristine()
        Path(str(self.rollout) + '.zst').write_bytes(b'compressed existing history')
        self.assertEqual(self.snapshot()['state'], 'unknown')

    def test_new_session_still_requires_live_owner(self):
        self.pristine()
        self.assertEqual(self.snapshot(owner=None)['state'], 'offline')

    def test_history_items_without_turn_record_are_not_new(self):
        self.pristine()
        with closing(sqlite3.connect(self.home / 'thread_history_1.sqlite')) as con, con:
            con.execute('INSERT INTO thread_items VALUES (?)', (THREAD,))
        self.assertEqual(self.snapshot()['state'], 'unknown')

    def test_history_created_during_new_snapshot_stays_unknown(self):
        self.pristine()
        with patch.object(Path, 'exists', side_effect=[False, False, False, True]):
            self.assertEqual(self.snapshot()['state'], 'unknown')


if __name__ == '__main__':
    unittest.main()
