#!/usr/bin/env python3
"""
Startup script for Railway deployment.
Reads PORT from environment variable and starts uvicorn.
Runs database migrations on startup.
"""
import os
import sys
import subprocess

def create_directories():
    """Create necessary directories for uploads and storage"""
    # Base path for Railway
    base_path = '/app/data' if os.path.exists('/app') else '../data'

    subdirs = [
        'uploads',
        'documents',
        'screenshots',
        'screenshots/fipe',
        'pdfs',
        'lens_temp',
    ]

    for subdir in subdirs:
        directory = os.path.join(base_path, subdir)
        os.makedirs(directory, exist_ok=True)
        print(f"Directory ensured: {directory}")

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
    # Create necessary directories
    create_directories()

    # Run migrations
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
