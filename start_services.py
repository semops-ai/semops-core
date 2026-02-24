#!/usr/bin/env python3
"""
start_services.py

This script starts the Supabase stack first, waits for it to initialize, and then starts
the ike-semops services (n8n and Qdrant). All services use the same Docker Compose
project name ("ike") so they appear together in Docker.
"""

import os
import subprocess
import shutil
import time
import argparse
import platform
import sys

def run_command(cmd, cwd=None):
 """Run a shell command and print it."""
 print("Running:", " ".join(cmd))
 # Prevent MSYS/Git Bash from converting Unix paths on Windows
 env = os.environ.copy
 env['MSYS_NO_PATHCONV'] = '1'
 # Use shell=True to ensure env var is properly passed
 cmd_str = " ".join(cmd)
 subprocess.run(cmd_str, cwd=cwd, check=True, env=env, shell=True)

def check_docker_engine:
 """Check that Docker Engine (not Desktop) is available."""
 engine_socket = "/var/run/docker.sock"
 desktop_socket = os.path.expanduser("~/.docker/desktop/docker.sock")

 if os.path.exists(desktop_socket) and not os.path.exists(engine_socket):
 print("Warning: Docker Desktop socket detected but Docker Engine socket not found.")
 print(f" Expected: {engine_socket}")
 print(f" Found: {desktop_socket}")
 print(" This project targets Docker Engine (native). Docker Desktop may cause issues.")
 print(" Install Docker Engine: https://docs.docker.com/engine/install/")

 if not os.path.exists(engine_socket):
 print(f"Warning: Docker socket not found at {engine_socket}")
 print(" Continuing anyway — Docker may be accessible via other means.")


def clone_supabase_repo:
 """Clone the Supabase repository using sparse checkout if not already present."""
 if not os.path.exists("supabase"):
 print("Cloning the Supabase repository...")
 run_command([
 "git", "clone", "--filter=blob:none", "--no-checkout",
 "https://github.com/supabase/supabase.git"
 ])
 os.chdir("supabase")
 run_command(["git", "sparse-checkout", "init", "--cone"])
 run_command(["git", "sparse-checkout", "set", "docker"])
 run_command(["git", "checkout", "master"])
 os.chdir("..")
 else:
 print("Supabase repository already exists, updating...")
 os.chdir("supabase")
 try:
 run_command(["git", "pull"])
 except subprocess.CalledProcessError:
 print("Warning: Could not update Supabase repository. Continuing with existing version...")
 os.chdir("..")

def prepare_supabase_env:
 """Copy .env to .env in supabase/docker."""
 env_path = os.path.join("supabase", "docker", ".env")
 env_example_path = os.path.join(".env")
 print("Copying .env in root to .env in supabase/docker...")
 shutil.copyfile(env_example_path, env_path)

def stop_existing_containers:
 """Stop and remove existing containers for the 'ike' project."""
 print("Stopping and removing existing containers for the 'ike' project...")
 try:
 run_command(["docker", "compose", "-p", "ike", "down"])
 except subprocess.CalledProcessError:
 print("Note: No existing containers to stop (this is normal on first run)")

def start_supabase:
 """Start the Supabase services."""
 print("Starting Supabase services...")
 cmd = ["docker", "compose", "-p", "ike", "-f", "supabase/docker/docker-compose.yml", "up", "-d"]
 run_command(cmd)

def wait_for_postgres:
 """Wait for PostgreSQL to be ready."""
 print("Waiting for PostgreSQL to be ready...")
 max_attempts = 30
 attempt = 0

 while attempt < max_attempts:
 try:
 # Try to connect to PostgreSQL
 result = subprocess.run(
 ["docker", "exec", "semops-hub-pg", "pg_isready", "-U", "postgres"],
 capture_output=True,
 text=True
 )
 if result.returncode == 0:
 print("PostgreSQL is ready!")
 return True
 except subprocess.CalledProcessError:
 pass

 attempt += 1
 print(f"Waiting for PostgreSQL... (attempt {attempt}/{max_attempts})")
 time.sleep(2)

 print("Warning: PostgreSQL may not be ready yet. Proceeding anyway...")
 return False

def start_ike_services:
 """Start the ike-semops services (n8n, Qdrant)."""
 print("Starting ike-semops services (n8n, Qdrant)...")
 cmd = ["docker", "compose", "-p", "ike", "-f", "docker-compose.yml", "up", "-d"]
 run_command(cmd)

def show_service_urls:
 """Display URLs for accessing the services."""
 print("\n" + "="*70)
 print("Services started successfully!")
 print("="*70)
 print("\nAccess your services at:")
 print(" Supabase Studio: http://localhost:8000")
 print(" n8n: http://localhost:5678")
 print(" Qdrant: http://localhost:6333/dashboard")
 print("\nDatabase connection (direct, bypasses pooler):")
 print(" Host: localhost")
 print(" Port: 5434")
 print(" Database: postgres")
 print(" User: postgres")
 print(" Password: (check your .env file)")
 print("\n Note: Port 5432 is Supavisor (pooler). Use 5434 for scripts/agents.")
 print("\nTo view logs:")
 print(" docker compose -p ike logs -f")
 print("\nTo stop services:")
 print(" docker compose -p ike down")
 print("="*70 + "\n")

def main:
 parser = argparse.ArgumentParser(
 description='Start Supabase and ike-semops services.',
 formatter_class=argparse.RawDescriptionHelpFormatter,
 epilog="""
Examples:
 python start_services.py # Start all services
 python start_services.py --skip-clone # Skip Supabase clone if already done
 """
 )
 parser.add_argument('--skip-clone', action='store_true',
 help='Skip cloning Supabase repository')
 args = parser.parse_args

 print("="*70)
 print("Starting ike-semops services")
 print("="*70 + "\n")

 # Ensure we're in the right directory
 if not os.path.exists("docker-compose.yml"):
 print("Error: docker-compose.yml not found. Please run this script from the repository root.")
 sys.exit(1)

 # Step 0: Check Docker Engine
 check_docker_engine

 # Step 1: Clone Supabase if needed
 if not args.skip_clone:
 clone_supabase_repo
 else:
 print("Skipping Supabase clone (--skip-clone flag set)...")

 # Step 2: Prepare environment
 prepare_supabase_env

 # Step 3: Stop existing containers
 stop_existing_containers

 # Step 4: Start Supabase first
 start_supabase

 # Step 5: Wait for PostgreSQL to be ready
 wait_for_postgres

 # Step 6: Start ike services (n8n, Qdrant)
 start_ike_services

 # Step 7: Give services time to initialize
 print("\nWaiting for all services to initialize...")
 time.sleep(5)

 # Step 8: Show service URLs
 show_service_urls

if __name__ == "__main__":
 main
