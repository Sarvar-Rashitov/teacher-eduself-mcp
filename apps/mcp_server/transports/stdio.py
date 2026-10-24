"""
MCP Standard I/O (stdio) Transport according to DOC-81 (MCP_SERVER.md).
Used by Claude Desktop, Cursor, and local terminal clients.
"""

import sys
import os
import argparse
import asyncio
import logging

logger = logging.getLogger("mcp_server.stdio")


def parse_arguments():
    parser = argparse.ArgumentParser(
        prog="python -m apps.mcp_server.transports.stdio",
        description="EduSelf Teacher MCP Server - Standard I/O (stdio) Transport for Claude Desktop and CLI tools.",
    )
    parser.add_argument(
        "--api-token",
        dest="api_token",
        help="EduSelf API Token or OAuth 2.1 Access Token for authentication.",
        default=os.getenv("EDUSELF_API_TOKEN"),
    )
    parser.add_argument(
        "--api-url",
        dest="api_url",
        help="Base URL of the EduSelf Teacher API.",
        default=os.getenv("EDUSELF_API_URL", "https://api.eduself.uz"),
    )
    parser.add_argument(
        "--settings",
        dest="settings_module",
        help="Django settings module to initialize.",
        default=os.getenv("DJANGO_SETTINGS_MODULE", "core.settings.local"),
    )
    return parser.parse_args()


def setup_django_environment(settings_module: str):
    """Django muhitini yuklash."""
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", settings_module)
    import django
    django.setup()


def main():
    args = parse_arguments()

    # Django sozlamalarini yuklash
    try:
        setup_django_environment(args.settings_module)
    except Exception as e:
        sys.stderr.write(f"Django setup error: {e}\n")

    from apps.mcp_server.server import mcp_server
    if not mcp_server:
        sys.stderr.write("MCP SDK not initialized or failed to load.\n")
        sys.exit(1)

    # Agar api-token berilgan bo'lsa, uni kontekstga o'rnatish
    if args.api_token:
        from apps.mcp_server.auth import verify_mcp_token, set_current_mcp_context
        try:
            ctx = verify_mcp_token(args.api_token)
            set_current_mcp_context(ctx)
        except Exception as e:
            sys.stderr.write(f"Token verification warning: {e}\n")

    # Stdio transportini ishga tushirish
    try:
        if hasattr(mcp_server, "run_stdio_async"):
            asyncio.run(mcp_server.run_stdio_async())
        else:
            mcp_server.run(transport="stdio")
    except (KeyboardInterrupt, EOFError):
        pass


if __name__ == "__main__":
    main()
