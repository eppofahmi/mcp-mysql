from . import server
import asyncio
import sys

def main():
   """Main entry point for the package."""
   # Check if --http flag is passed for HTTP server mode
   if "--http" in sys.argv:
       from .http_server import main as http_main
       asyncio.run(http_main())
   else:
       # Default stdio mode
       asyncio.run(server.main())

def main_http():
   """HTTP server entry point"""
   from .http_server import main as http_main
   asyncio.run(http_main())

def main_standalone():
   """Standalone server entry point"""
   import os
   import sys

   # Add project root to path
   project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
   sys.path.insert(0, project_root)

   from standalone_server import main as standalone_main
   standalone_main()

# Expose important items at package level
__all__ = ['main', 'main_http', 'main_standalone', 'server']