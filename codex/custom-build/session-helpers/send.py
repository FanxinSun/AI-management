#!/usr/bin/env python3
"""Resolve a named WSL Codex recipient and queue an authorized message once."""

import argparse
import datetime
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import subprocess
import sys
import uuid
import time

HELPER_DIR = Path(__file__).resolve().parent
if str(HELPER_DIR) not in sys.path:
    sys.path.insert(0, str(HELPER_DIR))
import status

CODEX = os.environ.get('CODEX_BIN', 'codex')
QUEUE_SCHEMA_0154 = '77329e40acd0509261267d802c4819853e81f4392baab20ac444084a8bd6a55e'
ACK = re.compile(r'^Queued message ([0-9a-f-]{36}) for thread ([0-9a-f-]{36})\.$', re.M)


class SendError(Exception):
    def __init__(self, reason, **details):
        super().__init__(reason)
        self.details = details


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def recipients(home, target):
    try:
        identifier = str(uuid.UUID(target))
    except ValueError:
        identifier = None
    with status.read_db(home / 'state_5.sqlite') as db:
        fields = 'id, name, archived, rollout_path, history_mode, cwd, source'
        if identifier:
            rows = db.execute(f'SELECT {fields} FROM threads WHERE id=?', (identifier,))
        else:
            rows = db.execute(f'SELECT {fields} FROM threads WHERE name=? AND archived=0', (target,))
        return [dict(row) for row in rows], identifier is not None


def observe_candidates(home, rows, writer_query):
    observed = []
    for row in rows:
        owner = writer_query(home / 'thread-writer-locks' / (row['id'] + '.lock'))
        observed.append({'thread_id': row['id'], 'name': row['name'],
                         'online': owner is not None, 'writer': owner})
    return observed


def resolve(home, target, expected_name=None, writer_query=status.writer_snapshot):
    rows, explicit_id = recipients(home, target)
    if not rows and explicit_id:
        live = status.resolve_unregistered(home, str(uuid.UUID(target)), writer_query=writer_query)
        if live:
            rows = [live]
    if not rows:
        raise SendError('No session matches the exact name or ID.', state='not_found')
    if explicit_id:
        row = rows[0]
        if expected_name and row['name'] != expected_name:
            raise SendError('The ID does not have the expected current session name.',
                            state='name_mismatch', actual_name=row['name'])
        if row['archived']:
            raise SendError('The intended session is archived.', state='archived')
        # A UUID pins identity. Never silently redirect it to a namesake or fork.
        if row['name']:
            siblings, _ = recipients(home, row['name'])
            observed = observe_candidates(home, siblings, writer_query)
            own_live = any(c['thread_id'] == row['id'] and c['online'] for c in observed)
            other_live = [c for c in observed if c['thread_id'] != row['id'] and c['online']]
            if not own_live and other_live:
                raise SendError('This pinned ID is offline while another same-name session is live. '
                                'Resolve recipient continuity before using the current ID.',
                                state='stale_target', candidates=observed)
        return row, 'explicit_id'
    if expected_name and target != expected_name:
        raise SendError('Target name differs from expected name.', state='name_mismatch')
    if len(rows) == 1:
        return rows[0], 'unique_exact_name'
    observed = observe_candidates(home, rows, writer_query)
    live = [c for c in observed if c['online']]
    if len(live) != 1:
        raise SendError('Duplicate names do not identify one live recipient. Use an explicitly '
                        'verified thread ID; recency alone is insufficient.',
                        state='ambiguous', candidates=observed)
    selected = next(row for row in rows if row['id'] == live[0]['thread_id'])
    return selected, 'unique_live_exact_name'


def snapshot(home, thread_id, runner=subprocess.run):
    env = dict(os.environ, CODEX_HOME=str(home))
    status_bin = os.environ.get('CODEX_SESSION_STATUS_BIN', str(HELPER_DIR / 'status.py'))
    command = ([sys.executable, '-B', status_bin] if status_bin.endswith('.py')
               else [status_bin])
    result = runner(command + [thread_id, '--json'],
                    capture_output=True, text=True, timeout=9, env=env)
    data = json.loads(result.stdout)
    if data.get('thread_id') not in (None, thread_id):
        raise SendError('Status returned a different recipient.', state='unknown')
    return data


def queued_payload(home, message_id, thread_id):
    """Verify only this queue acknowledgment; never inspect conversation text."""
    with status.read_db(home / 'queue_1.sqlite') as db:
        row = db.execute('SELECT thread_id,payload_json FROM queued_items WHERE id=?',
                         (message_id,)).fetchone()
    if row is None:
        return None  # It may already have been consumed; this is not proof of reading.
    if row['thread_id'] != thread_id:
        raise SendError('Durable queue entry belongs to a different recipient.', state='unconfirmed')
    return json.loads(row['payload_json'])


def payload_text(payload):
    content = payload.get('UserInput', {}).get('content', [])
    if len(content) != 1 or content[0].get('type') != 'text':
        raise SendError('Durable message content is not the expected text input.', state='unconfirmed')
    return content[0]['text']


def send(home, thread, message, availability, *, runner=subprocess.run,
         verify=queued_payload):
    if thread.get('unregistered'):
        try:
            return bridge_first_input(home, thread, message, availability)
        except SendError as exc:
            exc.details.setdefault('may_have_queued', False)
            raise
        except (status.StatusError, OSError, sqlite3.Error, subprocess.SubprocessError) as exc:
            raise SendError(str(exc), state='held', may_have_queued=False) from exc
    try:
        result = runner([CODEX, 'queue', '--thread', thread['id'], '--message', message],
                        capture_output=True, text=True, timeout=12,
                        env=dict(os.environ, CODEX_HOME=str(home)))
    except subprocess.TimeoutExpired as exc:
        raise SendError('Queue command timed out. Outcome is unknown; do not blindly retry.',
                        state='unconfirmed', may_have_queued=True) from exc
    match = ACK.search(result.stdout)
    if not match or result.returncode != 0:
        raise SendError('Queue command did not return a successful acknowledgment.',
                        state='unconfirmed', may_have_queued=True,
                        transport_error=(result.stderr or result.stdout)[-2000:])
    message_id, actual_id = match.groups()
    if actual_id != thread['id']:
        raise SendError('Queue acknowledgment names a different recipient.', state='unconfirmed',
                        may_have_queued=True, acknowledged_thread=actual_id)
    verification = 'queue_acknowledgment'
    try:
        payload = verify(home, message_id, actual_id)
        if payload is not None:
            if payload_text(payload) != message:
                raise SendError('Durable message differs from the supplied file.', state='unconfirmed',
                                may_have_queued=True, queue_message_id=message_id)
            verification = 'queue_acknowledgment_and_exact_durable_payload'
    except (OSError, sqlite3.Error, ValueError):
        pass  # A successful supported acknowledgment still establishes queueing.
    return {'state': 'queued', 'queue_message_id': message_id, 'thread_id': actual_id,
            'name': thread['name'], 'verification': verification,
            'availability': availability, 'delivery': 'pending_or_unconfirmed',
            'assessment': 'not_established', 'queued_at': now()}


def uuid7():
    value = ((time.time_ns() // 1_000_000) << 80) | (7 << 76)
    value |= (int.from_bytes(os.urandom(2), 'big') & 0xfff) << 64
    value |= (2 << 62) | (int.from_bytes(os.urandom(8), 'big') & ((1 << 62) - 1))
    return str(uuid.UUID(int=value))


def queue_schema_digest(db):
    rows = db.execute("SELECT type,name,sql FROM sqlite_master WHERE name NOT LIKE 'sqlite_%' "
                      "AND name != '_sqlx_migrations' ORDER BY type,name").fetchall()
    normalized = [[kind, name, ' '.join(sql.split()) if sql else None] for kind, name, sql in rows]
    return hashlib.sha256(json.dumps(normalized, separators=(',', ':')).encode()).hexdigest()


def bridge_first_input(home, thread, message, availability, *, writer_query=None,
                       owner_query=None, version_query=None):
    """0.154.0 compatibility bridge for a visible, unused, unregistered TUI.

    The public queue API cannot resolve this thread before its first input.
    Append only the real approved brief to the native queue; its existing
    watcher consumes it. Never invent a thread row, rollout or conversation.
    Schema/version checks deliberately fail closed after incompatible updates.
    """
    writer_query = writer_query or status.writer_snapshot
    owner_query = owner_query or status.visible_initial_owner
    if (availability.get('thread_id') != thread['id']
            or availability.get('writer_identity') != thread.get('writer_identity')
            or availability.get('first_input_transport') != 'verified_unregistered_queue_bridge'
            or readiness(availability, None) is None
            or availability.get('state') != 'new_session'):
        raise SendError('Unregistered first-input evidence is incomplete.', state='held')
    if not message.strip() or '\x00' in message or len(message) > (1 << 20):
        raise SendError('Invalid or oversized first-input text.', state='invalid_message')
    pid = thread['writer_identity']['pid']
    if version_query is None:
        version_query = lambda: subprocess.run([f'/proc/{pid}/exe', '--version'],
            text=True, capture_output=True, timeout=3, check=True).stdout.strip()
    if version_query() != 'codex-cli 0.154.0':
        raise SendError('Unregistered queue bridge needs validation for this Codex version.', state='held')
    def recheck():
        live = status.resolve_unregistered(home, thread['id'], writer_query, owner_query)
        if live is None or live['writer_identity'] != thread['writer_identity'] or live['cwd'] != thread['cwd']:
            raise SendError('Visible recipient ownership changed; no first input queued.', state='held')
        status.unregistered_input_snapshot(home, live)
    recheck()
    message_id, client_id = uuid7(), uuid7()
    payload = json.dumps({'UserInput': {'content': [
        {'type': 'text', 'text': message, 'text_elements': []}], 'client_id': client_id}}, ensure_ascii=False)
    db = sqlite3.connect((home / 'queue_1.sqlite').as_uri() + '?mode=rw', uri=True, timeout=1)
    try:
        db.execute('BEGIN IMMEDIATE')
        if queue_schema_digest(db) != QUEUE_SCHEMA_0154:
            raise SendError('Unregistered queue bridge refuses an unknown queue schema.', state='held')
        migrations = db.execute('SELECT version,description,success FROM _sqlx_migrations ORDER BY version').fetchall()
        if migrations != [(1, 'queued items', 1), (2, 'queued thread revisions', 1)]:
            raise SendError('Unregistered queue bridge refuses unknown queue migrations.', state='held')
        # Holding the queue write transaction excludes concurrent queue sends.
        recheck()
        stamp = time.time_ns() // 1_000_000
        db.execute('INSERT INTO queued_items VALUES (?,?,?,?,?,?)',
                   (message_id, thread['id'], payload, 0, stamp, stamp))
        if db.execute('SELECT payload_json FROM queued_items WHERE id=?', (message_id,)).fetchone() != (payload,):
            raise SendError('First-input queue verification failed.', state='held')
        revision = db.execute('SELECT revision FROM queued_thread_revisions WHERE thread_id=?',
                              (thread['id'],)).fetchone()
        if not revision:
            raise SendError('Queue watcher revision was not created.', state='held')
        # Recheck identity immediately before commit without reading our own
        # uncommitted input through a second connection.
        if writer_query(home / 'thread-writer-locks' / (thread['id'] + '.lock')) != thread['writer_identity']:
            raise SendError('Recipient exited before queue commit.', state='held')
        try:
            db.commit()
        except sqlite3.Error as exc:
            raise SendError('Queue commit failed; preserve the receipt and verify before retrying.',
                            state='unconfirmed', may_have_queued=True,
                            queue_message_id=message_id) from exc
    finally:
        db.close()  # Roll back every failed pre-commit check.
    return {'state': 'queued', 'queue_message_id': message_id, 'thread_id': thread['id'],
            'name': None, 'transport': 'verified_unregistered_queue_bridge',
            'verification': 'exact_native_queue_payload_and_revision', 'queue_revision': revision[0],
            'availability': availability, 'delivery': 'pending_or_unconfirmed',
            'assessment': 'not_established', 'queued_at': now()}


def save_receipt(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + '.' + str(uuid.uuid4()) + '.tmp')
    try:
        with temp.open('x', encoding='utf-8') as out:
            os.chmod(temp, 0o600)
            json.dump(data, out, indent=2, ensure_ascii=False)
            out.write('\n')
            out.flush()
            os.fsync(out.fileno())
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)


def verified_first_input(availability):
    return (availability.get('online') is True
            and availability.get('idle') is None
            and availability.get('state') == 'new_session'
            and availability.get('awaiting_initial_input') is True
            and availability.get('metadata_current') is True)


def readiness(availability, user_ready_statement):
    if availability.get('online') is True and availability.get('idle') is True:
        if availability.get('state') == 'new_session':
            if (availability.get('first_input_ready') is not True
                    or availability.get('metadata_current') is not True
                    or availability.get('awaiting_initial_input') is not True):
                return None
            return {'source': 'live_writer_and_verified_pristine_store',
                    'scope': 'first input to this verified new visible session only',
                    'checks': availability.get('first_input_checks', [])}
        return {'source': 'current_status_snapshot'}
    if (user_ready_statement and user_ready_statement.strip()
            and verified_first_input(availability)):
        return {'source': 'current_user_readiness_for_first_input',
                'user_statement': user_ready_statement,
                'scope': 'first input to this verified new visible session only'}
    return None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--to', required=True, help='Exact current user-given session name or verified UUID')
    parser.add_argument('--expect-name', help='Check the current name when specifying a UUID')
    parser.add_argument('--check', action='store_true', help='Resolve and check availability without sending')
    parser.add_argument('--message-file', type=Path, help='UTF-8 message; preserved exactly, without shell expansion')
    parser.add_argument('--require-idle', action='store_true', help='Hold unless currently online and idle; task completion is separate')
    parser.add_argument('--new-session-ready', help='Quote the current user statement that this newly opened session is online and idle; only accepted for verified first-input state')
    parser.add_argument('--receipt', type=Path, help='Receipt path; reusing the same request does not enqueue it again')
    args = parser.parse_args()
    if not args.check and not args.message_file:
        parser.error('--message-file is required unless --check is used')
    home = Path(os.environ.get('CODEX_HOME') or status.DEFAULT_HOME).expanduser().resolve()
    receipt_path = None
    fingerprint = None
    result = None
    receipt_lock = None
    recipient_lock = None
    dispatch_intent = False
    try:
        thread, resolution = resolve(home, args.to, args.expect_name)
        message = None if args.check else args.message_file.read_text(encoding='utf-8')
        if message is not None:
            if not message.strip() or '\x00' in message:
                raise SendError('Message file must contain nonempty text without NUL bytes.', state='invalid_message')
            fingerprint = hashlib.sha256(json.dumps([str(home), thread['id'], message],
                                                    ensure_ascii=False).encode()).hexdigest()
            receipt_path = (args.receipt or home / 'session-send-receipts' / (fingerprint + '.json')).expanduser().resolve()
            receipt_path.parent.mkdir(parents=True, exist_ok=True)
            receipt_lock = receipt_path.with_name(receipt_path.name + '.lock').open('a')
            os.chmod(receipt_lock.name, 0o600)
            try:
                fcntl.flock(receipt_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                raise SendError('This request already has an active sender; no duplicate was queued.',
                                state='held') from exc
            if receipt_path.exists():
                previous = json.loads(receipt_path.read_text())
                if previous.get('request_sha256') != fingerprint:
                    raise SendError('Receipt belongs to a different request. Use a separate receipt path.',
                                    state='receipt_conflict')
                print(json.dumps({**previous, 'reused_receipt': True}, ensure_ascii=False))
                return 0 if previous.get('state') == 'queued' else 2
            # Serialize different handovers to the same recipient: the next
            # sender must see the first queue entry or started turn, not reuse
            # an earlier empty-session snapshot. No recipient process is locked.
            recipient_lock_dir = home / 'session-send-receipts' / 'recipient-locks'
            recipient_lock_dir.mkdir(parents=True, exist_ok=True)
            recipient_lock = (recipient_lock_dir / (thread['id'] + '.lock')).open('a')
            os.chmod(recipient_lock.name, 0o600)
            try:
                fcntl.flock(recipient_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                raise SendError('Another sender is dispatching to this recipient; no message queued.',
                                state='held', required_action='retry_after_current_sender_finishes') from exc
        availability = snapshot(home, thread['id'])
        base = {'thread_id': thread['id'], 'name': thread['name'], 'resolution': resolution,
                'availability': availability, 'original_task_completion': 'not_assessed'}
        if args.check:
            result = {'state': 'checked', **base}
        else:
            ready = readiness(availability, args.new_session_ready)
            if (args.require_idle or thread.get('unregistered')) and ready is None:
                if verified_first_input(availability):
                    raise SendError(
                        'The approved brief can be this session\'s first input; no initialization '
                        'message is needed. Current readiness is the missing signal. Use an '
                        'existing current user statement with --new-session-ready; if none exists, '
                        'ask only whether the session is open and idle, then send the brief directly.',
                        state='held', initialization_required=False,
                        first_input_transport='codex_queue',
                        required_action='confirm_current_first_input_readiness', **base)
                raise SendError('Recipient is not confirmed online and idle; message was held locally.',
                                state='held', **base)
            if args.new_session_ready and ready is None:
                raise SendError('The first-input readiness statement cannot override this status.',
                                state='held', **base)
            if ready:
                base['readiness_evidence'] = ready
            # Revalidate identity at dispatch, without a second transcript/status probe.
            current, _ = resolve(home, args.to, args.expect_name)
            if current['id'] != thread['id']:
                raise SendError('Recipient ownership changed before dispatch; no message sent.', state='held')
            if resolution == 'unique_live_exact_name' and availability.get('online') is not True:
                raise SendError('Selected live namesake became unavailable; resolve again later.', state='held')
            # A durable intent prevents blind duplicate sends after interruption/timeout.
            save_receipt(receipt_path, {**base, 'state': 'unconfirmed', 'may_have_queued': True,
                                       'request_sha256': fingerprint, 'attempt_started_at': now()})
            dispatch_intent = True
            result = {**base, **send(home, thread, message, availability), 'request_sha256': fingerprint}
            save_receipt(receipt_path, result)
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except (SendError, status.StatusError, OSError, sqlite3.Error, ValueError,
            subprocess.TimeoutExpired) as exc:
        details = exc.details if isinstance(exc, SendError) else {}
        result = {'state': 'blocked', 'reason': str(exc), **details, 'checked_at': now()}
        # Preserve an uncertain dispatch; do not overwrite a conflicting or prior receipt.
        if receipt_path and fingerprint and result.get('may_have_queued'):
            save_receipt(receipt_path, {**result, 'request_sha256': fingerprint})
        elif dispatch_intent and result.get('may_have_queued') is False:
            # Explicit bridge rejection/rollback is known not to have queued.
            # Keep the diagnostic, but let a later fresh ready check retry.
            save_receipt(receipt_path.with_suffix('.held.json'), {**result, 'request_sha256': fingerprint})
            receipt_path.unlink(missing_ok=True)
        print(json.dumps(result, ensure_ascii=False))
        return 2
    finally:
        if recipient_lock is not None:
            recipient_lock.close()
        if receipt_lock is not None:
            receipt_lock.close()


if __name__ == '__main__':
    sys.exit(main())
