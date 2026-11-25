#!/usr/bin/env python3
"""Bounded, read-only WSL Codex availability snapshot; never starts a thread."""

import argparse
from contextlib import contextmanager
import datetime
import json
import os
from pathlib import Path
import re
import signal
import sqlite3
import subprocess
import sys
import time
import uuid


DEFAULT_HOME = Path.home() / '.codex'
UUID_SUFFIX = re.compile(r'([0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12})\.jsonl$')

HELPER_DIR = Path(__file__).resolve().parent
if str(HELPER_DIR) not in sys.path:
    sys.path.insert(0, str(HELPER_DIR))


class StatusError(Exception):
    pass


class DeadlineExpired(Exception):
    pass


@contextmanager
def read_db(path):
    con = sqlite3.connect(path.resolve().as_uri() + '?mode=ro', uri=True, timeout=1)
    con.row_factory = sqlite3.Row
    con.execute('PRAGMA query_only=ON')
    try:
        yield con
    finally:
        con.close()


def resolve_thread(home, target, writer_query=None):
    with read_db(home / 'state_5.sqlite') as con:
        try:
            thread_id = str(uuid.UUID(target))
        except ValueError:
            thread_id = None
        fields = 'id, name, archived, rollout_path, history_mode'
        if thread_id:
            rows = con.execute(f'SELECT {fields} FROM threads WHERE id=?', (thread_id,)).fetchall()
        else:
            rows = con.execute(
                f'SELECT {fields} FROM threads WHERE name=? AND archived=0', (target,)
            ).fetchall()
    if not rows:
        if thread_id:
            live = resolve_unregistered(home, thread_id, writer_query=writer_query)
            if live:
                return live, None
        raise StatusError('No matching session; use its exact current name or thread ID.')
    if len(rows) != 1:
        return None, [{'thread_id': r['id'], 'name': r['name']} for r in rows]
    return dict(rows[0]), None


def codex_owner(pid, proc_root=Path('/proc')):
    proc = proc_root / str(pid)
    if proc.stat().st_uid != os.getuid():
        raise StatusError('Writer belongs to another user.')
    executable = str((proc / 'exe').readlink()).removesuffix(' (deleted)')
    if Path(executable).name != 'codex':
        raise StatusError('Writer lock is not owned by a Codex executable.')
    fields = (proc / 'stat').read_text().rsplit(')', 1)[1].split()
    if fields[0] in {'Z', 'X'}:
        raise StatusError('Writer process has exited.')
    return int(fields[19])  # Linux /proc/PID/stat field 22, process start ticks.


def writer_snapshot(path, proc_root=Path('/proc'), owner_check=codex_owner):
    """Observe the existing kernel lock without attempting to acquire it."""
    try:
        stat = path.stat()
    except FileNotFoundError:
        return None
    wanted = (os.major(stat.st_dev), os.minor(stat.st_dev), stat.st_ino)
    owners = []
    for line in (proc_root / 'locks').read_text().splitlines():
        fields = line.split()
        if len(fields) != 8 or fields[1:4] != ['FLOCK', 'ADVISORY', 'WRITE']:
            continue
        device = fields[5].split(':')
        if len(device) != 3:
            continue
        identity = (int(device[0], 16), int(device[1], 16), int(device[2]))
        if identity == wanted:
            pid = int(fields[4])
            owners.append({'pid': pid, 'start_ticks': owner_check(pid),
                           'device': stat.st_dev, 'inode': stat.st_ino})
    if len(owners) > 1:
        raise StatusError('Conflicting writer ownership.')
    return owners[0] if owners else None


def rpc_snapshot(home, thread_id):
    # This existing transport speaks WebSocket over AF_UNIX. The CLI's proxy
    # forwards bytes; it is not a newline-delimited JSON-RPC adapter.
    from live_rpc import LiveRPC
    rpc = LiveRPC(home)
    try:
        result = rpc.call('thread/read', {'threadId': thread_id, 'includeTurns': False})
        thread = result['thread']
        return {k: thread.get(k) for k in ('id', 'status', 'canAcceptDirectInput')}
    finally:
        rpc.close()


def bounded_rpc(home, thread_id):
    try:
        result = subprocess.run(
            [sys.executable, '-B', str(Path(__file__).resolve()), '--rpc', thread_id],
            env=dict(os.environ, CODEX_HOME=str(home)),
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=2, check=False,
        )
        if result.returncode:
            return None, 'Shared status endpoint unavailable; using local ownership and metadata.'
        data = json.loads(result.stdout)
        if data.get('id') != thread_id:
            return None, 'Shared status endpoint returned a different session.'
        return data, None
    except (OSError, subprocess.TimeoutExpired, json.JSONDecodeError):
        return None, 'Shared status endpoint unavailable or timed out after 2 seconds.'


def file_identity(path):
    s = path.stat()
    return (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns)


def visible_initial_owner(home, thread_id, owner, proc_root=Path('/proc')):
    """Identify a foreground TUI, without inspecting prompts or process memory."""
    proc = proc_root / str(owner['pid'])
    fields = (proc / 'stat').read_text().rsplit(')', 1)[1].split()
    if int(fields[4]) == 0 or fields[2] != fields[5]:
        raise StatusError('Unregistered writer is not the foreground terminal process group.')
    terminal = str((proc / 'fd/0').readlink())
    if not terminal.startswith('/dev/pts/') or any(
            str((proc / f'fd/{fd}').readlink()) != terminal for fd in (1, 2)):
        raise StatusError('Unregistered writer is not a visible foreground TUI.')
    args = (proc / 'cmdline').read_bytes().split(b'\0')
    if any(arg in {b'exec', b'e', b'app-server', b'resume', b'fork', b'--ephemeral',
                   b'--remote'} or arg.startswith(b'--remote=') for arg in args[1:]):
        raise StatusError('Unregistered writer is not a fresh local interactive session.')
    files = set()
    for fd in (proc / 'fd').iterdir():
        try:
            files.add(str(fd.readlink()))
        except FileNotFoundError:
            continue
    expected_lock = home / 'thread-writer-locks' / (thread_id + '.lock')
    writer_files = {p for p in files if p.startswith(str(home / 'thread-writer-locks') + '/')
                    and not p.endswith('/.coordination.lock')}
    # SQLite's idle connection pool may close all DB descriptors. The exclusive
    # open writer-lock path still binds the actual Codex home and exact thread;
    # requiring an open state DB would incorrectly reject an idle new TUI.
    if writer_files != {str(expected_lock)}:
        raise StatusError('Cannot bind the visible TUI exclusively to this thread and Codex home.')
    return str((proc / 'cwd').readlink())


def resolve_unregistered(home, thread_id, writer_query=None, owner_query=None):
    writer_query = writer_query or writer_snapshot
    owner_query = owner_query or visible_initial_owner
    lock = home / 'thread-writer-locks' / (thread_id + '.lock')
    before = writer_query(lock)
    if before is None:
        return None
    cwd = owner_query(home, thread_id, before)
    if writer_query(lock) != before:
        raise StatusError('Unregistered writer ownership changed during identification.')
    return {'id': thread_id, 'name': None, 'archived': 0, 'rollout_path': None,
            'history_mode': 'unregistered', 'source': 'cli', 'cwd': cwd,
            'unregistered': True, 'writer_identity': before}


def unregistered_input_snapshot(home, thread):
    """No invented thread row: validate a live TUI's unused in-memory identity."""
    tid = thread['id']
    def history_exists():
        return any(next((home / folder).rglob('*' + tid + '*.jsonl*'), None) is not None
                   for folder in ('sessions', 'archived_sessions'))
    if history_exists():
        raise StatusError('Unregistered thread has existing rollout history.')
    with read_db(home / 'state_5.sqlite') as con:
        for alias, filename in [('hist', 'thread_history_1.sqlite'), ('queue', 'queue_1.sqlite')]:
            con.execute(f'ATTACH DATABASE ? AS {alias}',
                        ((home / filename).resolve().as_uri() + '?mode=ro',))
        con.execute('BEGIN')
        tables = ['threads', 'hist.thread_turns', 'hist.thread_items',
                  'hist.thread_history_projection_state', 'hist.thread_realtime_items',
                  'queue.queued_items', 'queue.queued_thread_revisions']
        for table in tables:
            key = 'id' if table == 'threads' else 'thread_id'
            if con.execute(f'SELECT 1 FROM {table} WHERE {key}=? LIMIT 1', (tid,)).fetchone():
                raise StatusError('Unregistered first-input state changed or has prior activity/pending input.')
    if history_exists():
        raise StatusError('Rollout appeared during first-input check.')
    return {'last_turn': None, 'metadata_current': True, 'awaiting_initial_input': True,
            'initialization_required': False, 'first_input_ready': True,
            'first_input_transport': 'verified_unregistered_queue_bridge',
            'first_input_checks': ['visible_foreground_tui', 'exclusive_live_thread_writer',
                                   'matching_codex_home', 'no_saved_thread_or_rollout',
                                   'no_history_or_queue_activity']}


def initial_input_snapshot(home, thread, rollout, rollout_id):
    """Verify first-input readiness from live ownership plus pristine store state.

    Missing rollout alone is insufficient. Normal turn-start events are appended
    and flushed before delivery by Core; any file, projected event, prior user
    activity or pending queue entry therefore disqualifies this first-input path.
    The caller brackets this snapshot with kernel writer/PID identity checks.
    """
    paths = [rollout, Path(str(rollout) + '.zst'), Path(str(rollout) + '.gz')]
    if rollout_id != thread['id'] or any(p.exists() for p in paths):
        raise StatusError('Missing history is not a pristine new-session state.')
    with read_db(home / 'state_5.sqlite') as con:
        for alias, filename in [('hist', 'thread_history_1.sqlite'), ('queue', 'queue_1.sqlite')]:
            uri = (home / filename).resolve().as_uri() + '?mode=ro'
            con.execute(f'ATTACH DATABASE ? AS {alias}', (uri,))
        con.execute('BEGIN')
        row = con.execute(
            'SELECT id,rollout_path,history_mode,source,archived,has_user_event,'
            'tokens_used,first_user_message,created_at,updated_at FROM threads WHERE id=?',
            (thread['id'],),
        ).fetchone()
        pristine = row is not None and (
            row['history_mode'] == 'paginated' and row['source'] in {'cli', 'vscode'}
            and row['archived'] == 0 and row['has_user_event'] == 0
            and row['tokens_used'] == 0 and not row['first_user_message']
            and row['created_at'] == row['updated_at']
            and Path(row['rollout_path']).resolve() == rollout
        )
        for table in ['hist.thread_turns', 'hist.thread_items',
                      'hist.thread_history_projection_state', 'hist.thread_realtime_items',
                      'queue.queued_items']:
            if con.execute(f'SELECT 1 FROM {table} WHERE thread_id=? LIMIT 1',
                           (thread['id'],)).fetchone():
                pristine = False
    if not pristine or any(p.exists() for p in paths):
        raise StatusError('Missing history has prior activity, pending input, or changed metadata; readiness is unknown.')
    return {'last_turn': None, 'metadata_current': True, 'awaiting_initial_input': True,
            'initialization_required': False, 'first_input_transport': 'codex_queue',
            'first_input_ready': True,
            'first_input_checks': ['no_rollout_or_compressed_history', 'matching_initial_rollout_id',
                                   'local_visible_source', 'no_prior_user_activity',
                                   'unchanged_creation_activity_metadata',
                                   'no_turns_items_projection_or_realtime_history',
                                   'no_queued_input']}


def local_turn_snapshot(home, thread):
    if thread.get('unregistered'):
        return unregistered_input_snapshot(home, thread)
    if thread['history_mode'] != 'paginated':
        raise StatusError('Legacy history has no supported metadata-only local status view.')
    rollout = Path(thread['rollout_path']).resolve()
    if not any(rollout.is_relative_to(home / folder) for folder in ('sessions', 'archived_sessions')):
        raise StatusError('Session history path is outside this Codex home.')
    match = UUID_SUFFIX.search(rollout.name)
    if not match:
        raise StatusError('Cannot identify the current rollout metadata.')
    rollout_id = match.group(1)
    try:
        before = file_identity(rollout)
    except FileNotFoundError:
        return initial_input_snapshot(home, thread, rollout, rollout_id)
    with read_db(home / 'thread_history_1.sqlite') as con:
        con.execute('BEGIN')
        turn = con.execute(
            'SELECT turn_id, status, started_at, completed_at FROM thread_turns '
            'WHERE thread_id=? ORDER BY rollout_ordinal DESC LIMIT 1', (rollout_id,)
        ).fetchone()
        projection = con.execute(
            'SELECT next_rollout_byte_offset FROM thread_history_projection_state '
            'WHERE thread_id=?', (rollout_id,)
        ).fetchone()
    after = file_identity(rollout)
    return {
        'last_turn': dict(turn) if turn else None,
        'metadata_current': before == after and projection is not None
                            and projection[0] == after[2],
    }


def classify_local(owner_before, owner_after, turn_snapshot):
    if owner_before != owner_after:
        return {'online': None, 'idle': None, 'state': 'unknown',
                'reason': 'Session ownership changed during this snapshot.'}
    if owner_before is None:
        return {'online': False, 'idle': None, 'state': 'offline',
                'reason': 'No active local Codex writer owns this session.'}
    result = {'online': True, 'idle': None, 'state': 'unknown',
              'writer_pid': owner_before['pid'], **turn_snapshot}
    turn = turn_snapshot.get('last_turn')
    if not turn_snapshot.get('metadata_current'):
        result['reason'] = 'Turn metadata is behind durable state or changed during the snapshot.'
    elif turn_snapshot.get('awaiting_initial_input'):
        if turn_snapshot.get('first_input_ready') is True:
            result.update(idle=True, state='new_session',
                          readiness_source='live_writer_and_verified_pristine_store',
                          reason='Stable live writer and fully verified unused session with no '
                          'history, prior activity or queued input. Ready for its approved first '
                          'handover through codex-session-send; no user confirmation or initialization '
                          'message is needed. This does not assess completion of an existing task.')
        else:
            result.update(state='new_session', reason='Incomplete first-input evidence; readiness is unknown.')
    elif turn and turn['status'] == 'inProgress':
        result.update(idle=False, state='busy', reason='The current turn is still in progress.')
    elif turn and turn['status'] in {'completed', 'interrupted', 'failed'}:
        result.update(idle=True, state='idle', reason='Live writer; latest turn is terminal.')
    elif turn is None:
        result.update(idle=True, state='idle', reason='Live writer; no turn has started.')
    else:
        result['reason'] = 'Unrecognized turn status; readiness is unconfirmed.'
    return result


def inspect_session(home, target, rpc_query=bounded_rpc,
                    writer_query=writer_snapshot, turn_query=local_turn_snapshot):
    thread, candidates = resolve_thread(home, target, writer_query=writer_query)
    base = {'original_task_completion': 'not_assessed'}
    if candidates:
        return {**base, 'state': 'ambiguous', 'online': None, 'idle': None,
                'candidates': candidates, 'reason': 'Duplicate names; select the intended thread ID.'}
    base.update(thread_id=thread['id'], name=thread['name'])
    if thread.get('unregistered'):
        base.update(unregistered=True, writer_identity=thread['writer_identity'], cwd=thread['cwd'])
    if thread['archived']:
        return {**base, 'state': 'archived', 'online': None, 'idle': None,
                'reason': 'This session is archived.'}
    rpc, rpc_error = (None, None) if thread.get('unregistered') else rpc_query(home, thread['id'])
    status = (rpc or {}).get('status') or {}
    kind = status.get('type')
    if kind in {'idle', 'active', 'systemError'}:
        return {**base, 'source': 'app_server_live', 'online': True,
                'idle': kind == 'idle', 'state': 'busy' if kind == 'active' else kind,
                'active_flags': status.get('activeFlags', []),
                'can_accept_direct_input': rpc.get('canAcceptDirectInput')}
    base.update(source='kernel_writer_lock_and_turn_metadata', shared_server_status=kind)
    if rpc_error:
        base['shared_server_note'] = rpc_error
    lock_path = home / 'thread-writer-locks' / (thread['id'] + '.lock')
    before = writer_query(lock_path)
    try:
        turns = turn_query(home, thread) if before else {}
    except (OSError, sqlite3.Error, StatusError) as exc:
        turns = {'metadata_current': False, 'detail': str(exc)}
    after = writer_query(lock_path)
    if thread.get('unregistered') and before != thread['writer_identity']:
        return {**base, 'online': None, 'idle': None, 'state': 'unknown',
                'reason': 'Unregistered thread owner changed before readiness check.'}
    return {**base, **classify_local(before, after, turns)}


def deadline_expired(signum, frame):
    raise DeadlineExpired('Status check exceeded its 8-second deadline; no session was changed.')


def main():
    if len(sys.argv) == 3 and sys.argv[1] == '--rpc':
        try:
            home = Path(os.environ.get('CODEX_HOME') or DEFAULT_HOME).expanduser().resolve()
            print(json.dumps(rpc_snapshot(home, sys.argv[2])))
            return 0
        except Exception:
            return 2
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('session', help='Exact user-given session name or thread UUID')
    parser.add_argument('--json', action='store_true', help='Emit a machine-readable snapshot')
    args = parser.parse_args()
    started = time.monotonic()
    signal.signal(signal.SIGALRM, deadline_expired)
    signal.setitimer(signal.ITIMER_REAL, 8)
    try:
        home = Path(os.environ.get('CODEX_HOME') or DEFAULT_HOME).expanduser().resolve()
        result = inspect_session(home, args.session)
    except (OSError, sqlite3.Error, StatusError, DeadlineExpired) as exc:
        result = {'state': 'unknown', 'online': None, 'idle': None, 'reason': str(exc),
                  'original_task_completion': 'not_assessed'}
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
    result['checked_at'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    result['elapsed_ms'] = round((time.monotonic() - started) * 1000)
    if args.json:
        print(json.dumps(result, ensure_ascii=False))
    else:
        label = result.get('name') or args.session
        print(f"{label}: {result['state'].upper()}")
        print(f"Online: {result['online']} | Idle: {result['idle']} | Checked: {result['checked_at']}")
        if result.get('last_turn'):
            print(f"Latest turn: {result['last_turn']['status']}")
        if result.get('reason'):
            print(result['reason'])
        print('Whole-task completion remains a separate check against the final report.')
        if result.get('candidates'):
            for candidate in result['candidates']:
                print(f"  {candidate['thread_id']}  {candidate['name']}")
    return 2 if result['state'] in {'unknown', 'ambiguous', 'archived'} or (
        result['state'] == 'new_session' and not result.get('first_input_ready')) else 0


if __name__ == '__main__':
    sys.exit(main())
