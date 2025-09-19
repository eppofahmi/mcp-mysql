"""
Main entry point for mysql_mcp_server module
Allows running via: python -m mysql_mcp_server
"""

from .server import main
import asyncio

if __name__ == "__main__":
    asyncio.run(main())