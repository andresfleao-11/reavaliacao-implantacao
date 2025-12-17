#!/usr/bin/env python3
"""
Startup script for Railway deployment.
Reads PORT from environment variable and starts uvicorn.
Runs database migrations on startup.
"""
import os
import sys
import subprocess

def run_migrations():
    """Run alembic migrations"""
    print("Running database migrations...")
    try:
        result = subprocess.run(
            ['alembic', 'upgrade', 'head'],
            capture_output=True,
            text=True,
            cwd=os.path.dirname(os.path.abspath(__file__))
        )
        if result.returncode == 0:
            print("Migrations completed successfully")
            if result.stdout:
                print(result.stdout)
        else:
            print(f"Migration warning (may already be up to date): {result.stderr}")
    except Exception as e:
        print(f"Migration error (continuing anyway): {e}")

def main():
    # Run migrations first
    run_migrations()

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
