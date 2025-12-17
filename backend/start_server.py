#!/usr/bin/env python3
"""
Startup script for Railway deployment.
Reads PORT from environment variable and starts uvicorn.
"""
import os
import sys

def main():
    port = os.environ.get('PORT', '8000')
    print(f"Starting uvicorn on port {port}")

    # Use os.execvp to replace current process with uvicorn
    os.execvp('uvicorn', [
        'uvicorn',
        'app.main:app',
        '--host', '0.0.0.0',
        '--port', port
    ])

if __name__ == '__main__':
    main()
