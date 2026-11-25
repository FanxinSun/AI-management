"""Small standard-library WebSocket client for the existing local Codex daemon."""
import base64
import hashlib
import json
import os
from pathlib import Path
import socket
import struct

class LiveRPC:
    def __init__(self, home=None, socket_path=None):
        home = Path(home or os.environ.get('CODEX_HOME') or Path.home() / '.codex').expanduser()
        socket_path = Path(socket_path or home / 'app-server-control' / 'app-server-control.sock')
        self.socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.socket.settimeout(15)
        self.socket.connect(str(socket_path))
        self.stream = self.socket.makefile('rb')
        self.counter = 0
        key = base64.b64encode(os.urandom(16)).decode()
        request = ('GET / HTTP/1.1\r\nHost: localhost\r\nUpgrade: websocket\r\n'
                   'Connection: Upgrade\r\nSec-WebSocket-Version: 13\r\n'
                   f'Sec-WebSocket-Key: {key}\r\n\r\n')
        self.socket.sendall(request.encode())
        status = self.stream.readline().decode().strip()
        assert ' 101 ' in status, status
        headers = {}
        while True:
            line = self.stream.readline()
            if line == b'\r\n':
                break
            if not line:
                raise ConnectionError('Incomplete WebSocket handshake')
            name, value = line.decode().split(':', 1)
            headers[name.lower()] = value.strip()
        expected = base64.b64encode(hashlib.sha1(
            (key + '258EAFA5-E914-47DA-95CA-C5AB0DC85B11').encode()).digest()).decode()
        assert headers.get('sec-websocket-accept') == expected
        self.call('initialize', {'clientInfo': {'name': os.environ.get('CODEX_RPC_CLIENT_NAME', 'codex-session-helper'), 'version': '1.0'},
                                'capabilities': {'experimentalApi': True}})
        self.send({'method': 'initialized', 'params': {}})

    def frame(self, payload, opcode=1):
        size = len(payload)
        header = bytes([0x80 | opcode])
        if size < 126:
            header += bytes([0x80 | size])
        elif size < 65536:
            header += bytes([0x80 | 126]) + struct.pack('!H', size)
        else:
            header += bytes([0x80 | 127]) + struct.pack('!Q', size)
        mask = os.urandom(4)
        body = bytes(value ^ mask[index % 4] for index, value in enumerate(payload))
        self.socket.sendall(header + mask + body)

    def send(self, value):
        self.frame(json.dumps(value).encode())

    def exact(self, length):
        data = self.stream.read(length)
        if len(data) != length:
            raise ConnectionError('WebSocket connection closed')
        return data

    def receive(self):
        chunks = []
        while True:
            first, second = self.exact(2)
            opcode, size = first & 15, second & 127
            if size == 126:
                size = struct.unpack('!H', self.exact(2))[0]
            elif size == 127:
                size = struct.unpack('!Q', self.exact(8))[0]
            assert size <= 32 * 1024 * 1024
            mask = self.exact(4) if second & 128 else None
            data = self.exact(size)
            if mask:
                data = bytes(value ^ mask[index % 4] for index, value in enumerate(data))
            if opcode == 8:
                raise ConnectionError('Server closed the WebSocket')
            if opcode == 9:
                self.frame(data, 10)
                continue
            if opcode == 10:
                continue
            assert opcode in (0, 1), opcode
            chunks.append(data)
            if first & 128:
                return json.loads(b''.join(chunks))

    def call(self, method, params):
        self.counter += 1
        self.send({'id': self.counter, 'method': method, 'params': params})
        while True:
            result = self.receive()
            if result.get('id') == self.counter:
                if 'error' in result:
                    raise RuntimeError(f'{method}: {result["error"]}')
                return result['result']

    def close(self):
        try:
            self.frame(b'', 8)
        finally:
            self.stream.close()
            self.socket.close()
