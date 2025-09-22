"""
ASGI application module for uvicorn
This module exports the FastAPI app for uvicorn to run with --reload
"""

import os
import sys

# Add src directory to path
current_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.join(current_dir, 'src')
sys.path.insert(0, src_dir)

from standalone_server import StandaloneMySQLMCPServer

# Create the server instance
server = StandaloneMySQLMCPServer()

# Export the FastAPI app for uvicorn
app = server.app