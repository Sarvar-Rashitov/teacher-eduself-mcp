# ============================================================
# EduSelf Teacher — apps/mcp_server/cli.py
# CLI Tool: `python -m apps.mcp_server.cli` & `eduself login`
# MCP_AUTH.md DOC-84 asosida
# ============================================================
import os
import sys
import argparse
import secrets
import webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

# Standalone rejimda ishga tushganda Django sozlamalarini yuklaymiz
if not os.environ.get('DJANGO_SETTINGS_MODULE'):
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings.local')

import django
try:
    django.setup()
except RuntimeError:
    pass

from apps.mcp_server.transports.stdio import run_stdio


class OAuthCallbackHandler(BaseHTTPRequestHandler):
    """Mahalliy CLI login paytida callback qabul qiluvchi server."""
    received_code = None

    def do_GET(self):
        query = urlparse(self.path).query
        params = parse_qs(query)
        if "code" in params:
            OAuthCallbackHandler.received_code = params["code"][0]
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            html = """
            <html>
            <body style="font-family:sans-serif; text-align:center; padding:50px; background:#f0f9ff;">
                <h1 style="color:#0284c7;">EduSelf Hisobingiz Muvaffaqiyatli Ulandi!</h1>
                <p>Ushbu oynani yopishingiz va terminalga qaytishingiz mumkin.</p>
            </body>
            </html>
            """
            self.wfile.write(html.encode("utf-8"))
        else:
            self.send_response(400)
            self.end_headers()

    def log_message(self, format, *args):
        # Jim rejim (shovqinsiz)
        pass


def handle_login(port: int = 8085):
    """
    `eduself login` oqimi: Brauzerni ochadi va vaqtinchalik callback qabul qiladi.
    """
    sys.stdout.write(f"EduSelf hisobini ulash boshlanmoqda (Port: {port})...\n")
    state = secrets.token_urlsafe(16)
    auth_url = f"http://localhost:8000/oauth/authorize/?client_id=claude-desktop-client&redirect_uri=http://localhost:{port}/oauth/callback&response_type=code&state={state}"

    sys.stdout.write(f"Brauzer ochilmoqda: {auth_url}\n")
    webbrowser.open(auth_url)

    server = HTTPServer(('localhost', port), OAuthCallbackHandler)
    server.handle_request()  # Bitta so'rovni kutadi

    if OAuthCallbackHandler.received_code:
        sys.stdout.write(f"[Muvaffaqiyatli] Avtorizatsiya kodi olindi: {OAuthCallbackHandler.received_code[:8]}...\n")
        sys.stdout.write("Akkaunt ulandi! Endi Claude Desktop yoki terminal orqali ishlatishingiz mumkin.\n")
    else:
        sys.stderr.write("[Xato] Avtorizatsiya kodi olinmadi.\n")


def main():
    parser = argparse.ArgumentParser(description="EduSelf Teacher MCP CLI")
    subparsers = parser.add_subparsers(dest="command")

    # `login` subbuyrug'i
    login_parser = subparsers.add_parser("login", help="EduSelf hisobiga kirish va bog'lash")
    login_parser.add_argument("--port", type=int, default=8085, help="Callback porti (standart: 8085)")

    # `run` subbuyrug'i (stdio)
    run_parser = subparsers.add_parser("run", help="MCP serverni stdio rejimida ishga tushirish")
    run_parser.add_argument("--token", help="EduSelf API kaliti")

    args = parser.parse_args()

    if args.command == "login":
        handle_login(port=args.port)
    elif args.command == "run":
        run_stdio(api_token=args.token)
    else:
        # Default sifatida stdio ishga tushadi
        run_stdio()


if __name__ == "__main__":
    main()
