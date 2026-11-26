#!/usr/bin/env python3
"""LIVE WHITEBOARD SERVER — serves canvas page + SSE command bus + POST API.
I can push shapes via curl; user can type commands in the page. All animate live."""
import json, time, threading, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:
    import sentry
except Exception:
    sentry = None
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler

HERE = os.path.dirname(os.path.abspath(__file__))
_KEYFILE = os.path.join(os.path.dirname(HERE), 'marshal.key')
MARSHAL_KEY = open(_KEYFILE).read().strip() if os.path.exists(_KEYFILE) else ''
PORT = 8901
clients = []          # SSE queues
lock = threading.Lock()
history = []          # last commands for replay

def broadcast(cmd):
    with lock:
        history.append(cmd)
        del history[:-12]
        dead = []
        for q in clients:
            try: q.put_nowait(cmd)
            except Exception: dead.append(q)
        for q in dead: clients.remove(q)

class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass

    def _send(self, code, body, ctype='text/html'):
        b = body.encode() if isinstance(body, str) else body
        self.send_response(code)
        self.send_header('Content-Type', ctype)
        self.send_header('Content-Length', str(len(b)))
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(b)

    def do_GET(self):
        if self.path == '/':
            self._send(200, open(os.path.join(HERE,'index.html')).read().replace('__KEY__', MARSHAL_KEY))
        elif self.path == '/events':
            self.send_response(200)
            self.send_header('Content-Type','text/event-stream')
            self.send_header('Cache-Control','no-cache')
            self.send_header('Access-Control-Allow-Origin','*')
            self.end_headers()
            import queue
            q = queue.Queue()
            with lock:
                clients.append(q)
                for c in history: q.put(c)
            try:
                while True:
                    try:
                        cmd = q.get(timeout=15)
                        self.wfile.write(f"data: {json.dumps(cmd)}\n\n".encode())
                        self.wfile.flush()
                    except Exception:
                        self.wfile.write(b": ping\n\n"); self.wfile.flush()
            except Exception:
                with lock:
                    if q in clients: clients.remove(q)
        elif self.path == '/health':
            self._send(200, '{"ok":true,"clients":%d}' % len(clients), 'application/json')
        else:
            self._send(404, 'not found', 'text/plain')

    def do_POST(self):
        if self.path == '/api/draw':
            n = int(self.headers.get('Content-Length', 0))
            try:
                cmd = json.loads(self.rfile.read(n) or b'{}')
                if sentry: sentry.record(sentry.check('POST', '/api/draw ' + json.dumps(cmd)[:200], authed=True), 'POST', '/api/draw', 'whiteboard')
                if MARSHAL_KEY and cmd.get('key') != MARSHAL_KEY:
                    if sentry: sentry.record([('AUTH-04','unauth-draw','MED')], 'POST', '/api/draw', 'whiteboard')
                    self._send(403, '{"ok":false,"err":"marshal key required"}', 'application/json'); return
                shape = str(cmd.get('shape','')).strip().lower()
                if shape:
                    broadcast({'shape': shape, 'args': cmd.get('args', [])})
                    self._send(200, '{"ok":true}', 'application/json')
                    return
            except Exception:
                pass
            self._send(400, '{"ok":false}', 'application/json')
        else:
            self._send(404, 'not found', 'text/plain')

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header('Access-Control-Allow-Origin','*')
        self.send_header('Access-Control-Allow-Headers','*')
        self.send_header('Access-Control-Allow-Methods','GET,POST,OPTIONS')
        self.end_headers()

if __name__ == '__main__':
    print(f'LIVE WHITEBOARD → http://localhost:{PORT}')
    ThreadingHTTPServer(('0.0.0.0', PORT), H).serve_forever()
