"""
Standard Input/Output (Stdio) Transport Runner.
Conforms to DOC-81 (MCP_SERVER.md) for local clients (Claude Desktop, Cursor, CLI).
"""

import argparse
import asyncio
import os
import sys

# Django muhitini yuklash
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings.local")
try:
    import django
    django.setup()
except Exception:
    pass

from ..server import mcp_server
from ..auth import authenticate_bearer_token, set_current_mcp_context


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m apps.mcp_server.transports.stdio",
        description="EduSelf Teacher Model Context Protocol (MCP) Stdio Server for Claude Desktop and local agents.",
    )
    parser.add_argument(
        "--token",
        type=str,
        default=os.environ.get("EDUSELF_API_TOKEN", ""),
        help="EduSelf API Token / Bearer Token (or set EDUSELF_API_TOKEN env var).",
    )
    parser.add_argument(
        "--client-name",
        type=str,
        default="Claude Desktop",
        help="Client name identifier for audit logs (default: 'Claude Desktop').",
    )
    return parser


async def main_async(args):
    token = args.token or os.environ.get("EDUSELF_API_TOKEN", "")
    if token:
        try:
            context = authenticate_bearer_token(token, client_name=args.client_name)
            set_current_mcp_context(context)
            sys.stderr.write(f"EduSelf MCP: Authenticated as {context.user.email} ({context.user.id})\n")
        except Exception as ex:
            sys.stderr.write(f"EduSelf MCP Warning: Token authentication failed ({ex})\n")

    sys.stderr.write("EduSelf MCP: Starting Stdio transport listener...\n")
    await mcp_server.run_stdio_async()


def main():
    parser = build_arg_parser()
    args = parser.parse_args()
    try:
        asyncio.run(main_async(args))
    except (KeyboardInterrupt, SystemExit):
        sys.stderr.write("EduSelf MCP: Stdio transport stopped.\n")


if __name__ == "__main__":
    main()
