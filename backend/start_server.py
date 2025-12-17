#!/usr/bin/env python3
"""
Startup script for Railway deployment.
Runs both uvicorn API server and Celery worker in the same container
to share the filesystem for uploads.
"""
import os
import sys
import subprocess
import signal
import time

processes = []

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

def start_celery_worker():
    """Start Celery worker in background"""
    print("Starting Celery worker...")

    # Check if Redis is configured
    redis_url = os.environ.get('REDIS_URL', '')
    if not redis_url:
        print("WARNING: REDIS_URL not configured. Celery worker will not start.")
        return None

    process = subprocess.Popen(
        [
            'celery', '-A', 'app.tasks.celery_app', 'worker',
            '--loglevel=info',
            '--concurrency=2'
        ],
        cwd=os.path.dirname(os.path.abspath(__file__))
    )
    print(f"Celery worker started with PID {process.pid}")
    return process

def start_uvicorn():
    """Start uvicorn server"""
    port = os.environ.get('PORT', '8000')
    print(f"Starting uvicorn on port {port}")

    process = subprocess.Popen(
        [
            'uvicorn', 'app.main:app',
            '--host', '0.0.0.0',
            '--port', port
        ],
        cwd=os.path.dirname(os.path.abspath(__file__))
    )
    print(f"Uvicorn started with PID {process.pid}")
    return process

def signal_handler(signum, frame):
    """Handle shutdown signals"""
    global processes
    print(f"Received signal {signum}, shutting down...")
    for p in processes:
        if p and p.poll() is None:
            print(f"Stopping process {p.pid}...")
            p.terminate()

    # Wait for processes to finish
    for p in processes:
        if p:
            try:
                p.wait(timeout=10)
            except subprocess.TimeoutExpired:
                p.kill()

    sys.exit(0)

def main():
    global processes

    # Create necessary directories
    create_directories()

    # Run migrations
    run_migrations()

    # Setup signal handlers for graceful shutdown
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)

    # Start Celery worker in background
    celery = start_celery_worker()
    if celery:
        processes.append(celery)

    # Give Celery a moment to start
    time.sleep(2)

    # Start uvicorn
    uvicorn = start_uvicorn()
    processes.append(uvicorn)

    # Wait for uvicorn to exit (main process)
    # If uvicorn exits, we should shutdown everything
    try:
        uvicorn.wait()
    except KeyboardInterrupt:
        pass
    finally:
        signal_handler(signal.SIGTERM, None)

if __name__ == '__main__':
    main()
