#!/usr/bin/env python3
"""
Setup Supabase repository

This script clones the Supabase repository which is needed for the devcontainer.
Run this BEFORE opening the devcontainer.

Usage:
 python scripts/setup_supabase.py
"""

import os
import subprocess
import sys
import shutil

def run_command(cmd, cwd=None):
 """Run a shell command."""
 print(f"→ {' '.join(cmd)}")
 result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
 if result.returncode != 0:
 print(f"✗ Command failed: {result.stderr}")
 return False
 return True

def clone_supabase:
 """Clone the Supabase repository using sparse checkout."""
 if os.path.exists("supabase"):
 print("📦 Supabase repository already exists")
 response = input("Do you want to update it? (y/n): ")
 if response.lower == 'y':
 print("Updating Supabase repository...")
 if run_command(["git", "pull"], cwd="supabase"):
 print("✓ Supabase repository updated")
 else:
 print("⚠ Could not update (might be fine)")
 return True

 print("📦 Cloning Supabase repository...")
 print(" (This uses sparse checkout - only the docker folder)")

 if not run_command([
 "git", "clone",
 "--filter=blob:none",
 "--no-checkout",
 "https://github.com/supabase/supabase.git"
 ]):
 return False

 os.chdir("supabase")

 if not run_command(["git", "sparse-checkout", "init", "--cone"]):
 return False

 if not run_command(["git", "sparse-checkout", "set", "docker"]):
 return False

 if not run_command(["git", "checkout", "master"]):
 return False

 os.chdir("..")

 print("✓ Supabase repository cloned successfully")
 return True

def copy_env:
 """Copy .env to supabase/docker/.env"""
 env_source = ".env"
 env_dest = os.path.join("supabase", "docker", ".env")

 if not os.path.exists(env_source):
 print("✗ Error: .env file not found in root!")
 print(" Make sure you have a .env file configured")
 return False

 print(f"📋 Copying {env_source} to {env_dest}...")
 os.makedirs(os.path.dirname(env_dest), exist_ok=True)
 shutil.copyfile(env_source, env_dest)
 print("✓ Environment file copied")
 return True

def main:
 print("="*60)
 print("Ike SemOps - Supabase Setup")
 print("="*60)
 print
 print("This script prepares the Supabase repository for the devcontainer.")
 print("Run this BEFORE opening the project in a devcontainer.")
 print

 if not clone_supabase:
 print("\n✗ Setup failed")
 sys.exit(1)

 if not copy_env:
 print("\n✗ Setup failed")
 sys.exit(1)

 print
 print("="*60)
 print("✓ Setup Complete!")
 print("="*60)
 print
 print("🚀 Next Steps:")
 print(" 1. Open VS Code")
 print(" 2. Press F1 and select 'Dev Containers: Reopen in Container'")
 print(" 3. Wait for the container to build and services to start")
 print(" 4. Run: python scripts/init_schema.py")
 print

if __name__ == "__main__":
 main
