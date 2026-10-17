# ============================================================
# EduSelf Teacher — apps/mcp_server/transports/stdio.py
# Stdio Transport Runner (Claude Desktop / CLI)
# MCP_SERVER.md DOC-81 asosida
# ============================================================
import os
import sys
import asyncio
import argparse

# Standalone rejimda ishga tushganda Django sozlamalarini yuklaymiz
if not os.environ.get('DJANGO_SETTINGS_MODULE'):
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings.local')

import django
try:
    django.setup()
except RuntimeError:
    # Allaqachon yuklangan bo'lsa
    pass

from apps.mcp_server.server import mcp_server
from apps.mcp_server.auth import authenticate_token, set_current_mcp_context


def run_stdio(api_token: str = None):
    """
    Stdio transportini ishga tushirish funksiyasi.
    Claude Desktop yoki mahalliy agentlar bilan stdin/stdout orqali muloqot qiladi.
    """
    token = api_token or os.environ.get("EDUSELF_API_TOKEN")
    if token:
        try:
            ctx = authenticate_token(token)
            set_current_mcp_context(ctx)
            sys.stderr.write(f"[EduSelf MCP] Foydalanuvchi muvaffaqiyatli autentifikatsiya qilindi: {ctx.user.username}\n")
        except Exception as e:
            sys.stderr.write(f"[EduSelf MCP] Ogohlantirish: Token noto'g'ri: {str(e)}\n")
    else:
        sys.stderr.write("[EduSelf MCP] Ogohlantirish: EDUSELF_API_TOKEN ko'rsatilmadi. So'rovlar kontekstsiz ishlaydi.\n")

    sys.stderr.flush()
    asyncio.run(mcp_server.run_stdio_async())


def main():
    parser = argparse.ArgumentParser(description="EduSelf Teacher MCP Server (Stdio Transport)")
    parser.add_argument("--token", dest="token", help="EduSelf API kaliti (usr_token_...)")
    parser.add_argument("--version", action="version", version="EduSelf MCP 1.0.0")
    args = parser.parse_args()

    run_stdio(api_token=args.token)


if __name__ == "__main__":
    main()
