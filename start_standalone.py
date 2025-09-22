#!/usr/bin/env python3
"""
Startup script for MySQL MCP Standalone Server
Simple launcher for the complete standalone server
"""

import os
import sys

# Add src directory to path
current_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.join(current_dir, 'src')
sys.path.insert(0, src_dir)

from mysql_mcp_server import main_standalone

if __name__ == "__main__":
    main_standalone()