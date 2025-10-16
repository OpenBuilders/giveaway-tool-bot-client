import threading
from http.server import BaseHTTPRequestHandler, HTTPServer


class _HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path in ('/', '/healthz', '/livez', '/readyz'):
            self.send_response(200)
            self.send_header('Content-Type', 'text/plain')
            self.end_headers()
            self.wfile.write(b'OK')
        else:
            self.send_response(404)
            self.end_headers()

    # Silence default request logging to stderr
    def log_message(self, format, *args):  # type: ignore[override]
        return


def start_health_server(port: int) -> threading.Thread:
    """Start a simple HTTP health server in background thread."""
    server = HTTPServer(('0.0.0.0', port), _HealthHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return thread


