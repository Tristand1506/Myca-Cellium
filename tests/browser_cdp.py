"""Small dependency-free Chrome/Edge DevTools test driver (loopback only)."""
import base64
import json
import os
from pathlib import Path
import secrets
import shutil
import socket
import struct
import subprocess
import tempfile
import time
from urllib.parse import urlsplit
from urllib.request import urlopen


def browser_path():
    configured = os.environ.get('MYCA_BROWSER')
    if configured:
        return configured
    for name in ('google-chrome', 'google-chrome-stable', 'chromium', 'chromium-browser', 'msedge'):
        found = shutil.which(name)
        if found:
            return found
    for base in (os.environ.get('PROGRAMFILES', ''), os.environ.get('PROGRAMFILES(X86)', ''),
                 os.environ.get('LOCALAPPDATA', '')):
        for relative in ('Google/Chrome/Application/chrome.exe', 'Microsoft/Edge/Application/msedge.exe'):
            path = Path(base) / relative
            if path.is_file():
                return str(path)
    return None


class Browser:
    def __init__(self):
        self.profile = tempfile.TemporaryDirectory()
        self.process = None
        self.sock = None
        self.sequence = 0
        try:
            self.process = subprocess.Popen([browser_path(), '--headless=new', '--no-sandbox',
                '--disable-gpu', '--remote-debugging-port=0', '--remote-debugging-address=127.0.0.1',
                '--user-data-dir=' + self.profile.name, 'about:blank'],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            port_file = Path(self.profile.name) / 'DevToolsActivePort'
            deadline = time.monotonic() + 15
            while not port_file.exists():
                if time.monotonic() > deadline or self.process.poll() is not None:
                    raise RuntimeError('Browser did not start')
                time.sleep(.05)
            port = int(port_file.read_text().splitlines()[0])
            with urlopen(f'http://127.0.0.1:{port}/json/list', timeout=10) as response:
                pages = json.load(response)
            url = next(p['webSocketDebuggerUrl'] for p in pages if p['type'] == 'page')
            parsed = urlsplit(url); self.sock = socket.create_connection(('127.0.0.1', parsed.port), timeout=20)
            key = base64.b64encode(secrets.token_bytes(16)).decode()
            self.sock.sendall((f'GET {parsed.path} HTTP/1.1\r\nHost: 127.0.0.1:{parsed.port}\r\n'
                               f'Upgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Key: {key}\r\n'
                               'Sec-WebSocket-Version: 13\r\n\r\n').encode())
            header = b''
            while not header.endswith(b'\r\n\r\n'):
                header += self.sock.recv(1)
            if b' 101 ' not in header:
                raise RuntimeError('DevTools connection refused')
        except Exception:
            self.close()
            raise

    def read(self, count):
        data = b''
        while len(data) < count:
            part = self.sock.recv(count-len(data))
            if not part:
                raise RuntimeError('Browser closed the connection')
            data += part
        return data

    def send(self, data, opcode=1):
        mask = secrets.token_bytes(4); length = len(data)
        header = bytes([128 | opcode])
        if length < 126:
            header += bytes([128 | length])
        elif length < 65536:
            header += bytes([128 | 126]) + struct.pack('!H', length)
        else:
            header += bytes([128 | 127]) + struct.pack('!Q', length)
        self.sock.sendall(header + mask + bytes(b ^ mask[i % 4] for i, b in enumerate(data)))

    def call(self, method, **params):
        self.sequence += 1; identity = self.sequence
        self.send(json.dumps({'id': identity, 'method': method, 'params': params}).encode())
        fragments = b''
        while True:
            first, second = self.read(2); opcode = first & 15; length = second & 127
            if length == 126:
                length = struct.unpack('!H', self.read(2))[0]
            elif length == 127:
                length = struct.unpack('!Q', self.read(8))[0]
            mask = self.read(4) if second & 128 else None
            payload = self.read(length)
            if mask:
                payload = bytes(b ^ mask[i % 4] for i, b in enumerate(payload))
            if opcode == 9:
                self.send(payload, opcode=10); continue
            if opcode == 8:
                raise RuntimeError('Browser disconnected')
            if opcode not in (0, 1):
                continue
            fragments += payload
            if not first & 128:
                continue
            message = json.loads(fragments); fragments = b''
            if message.get('id') != identity:
                continue
            if 'error' in message:
                raise RuntimeError(message['error'])
            return message.get('result', {})

    def evaluate(self, expression):
        result = self.call('Runtime.evaluate', expression=expression, awaitPromise=True, returnByValue=True)
        if 'exceptionDetails' in result:
            raise AssertionError(result['exceptionDetails'])
        return result.get('result', {}).get('value')

    def wait(self, expression):
        deadline = time.monotonic() + 15
        while not self.evaluate(expression):
            if time.monotonic() > deadline:
                raise AssertionError('Timed out waiting for ' + expression)
            time.sleep(.05)

    def drag(self, selector, start, end):
        rect = self.evaluate(f'(()=>{{const r=document.querySelector({json.dumps(selector)}).getBoundingClientRect();'
                             'return {x:r.x,y:r.y,width:r.width,height:r.height}})()')
        def point(value):
            return {'x': rect['x'] + value[0]*rect['width'], 'y': rect['y'] + value[1]*rect['height']}
        self.call('Input.dispatchMouseEvent', type='mousePressed', button='left', buttons=1, clickCount=1, **point(start))
        for i in range(1, 6):
            value = [start[j] + (end[j]-start[j])*i/5 for j in (0,1)]
            self.call('Input.dispatchMouseEvent', type='mouseMoved', button='left', buttons=1, **point(value))
        self.call('Input.dispatchMouseEvent', type='mouseReleased', button='left', buttons=0, **point(end))

    def close(self):
        if self.sock:
            try:
                self.send(json.dumps({'id':self.sequence+1,'method':'Browser.close'}).encode())
            except (OSError,RuntimeError):
                pass
            self.sock.close()
        if self.process:
            try:
                self.process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.process.terminate()
                try:
                    self.process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self.process.kill(); self.process.wait()
        # Wait briefly for browser subprocesses to release their profile files.
        for attempt in range(20):
            try:
                self.profile.cleanup()
                break
            except OSError:
                if attempt==19:
                    raise
                time.sleep(.05)
