#!/usr/bin/env python3
"""
Main entry point - automatically detects if running in Codespaces
"""
import os

if os.getenv('CODESPACE_NAME'):
    # Running in GitHub Codespaces
    from codespaces_app import main
else:
    # Running locally
    from local_app import main

if __name__ == '__main__':
    main()
