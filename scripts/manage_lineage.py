#!/usr/bin/env python3
"""
Lineage Tracking Management Script

Manage lineage tracking settings - enable/disable, change modes, check status.
"""

import sys
import os
from pathlib import Path


def load_env_file() -> dict:
    """Load .env file and return as dictionary."""
    env_file = Path(__file__).parent.parent / ".env"
    if not env_file.exists():
        print("Error: .env file not found")
        sys.exit(1)

    env_vars = {}
    with open(env_file, "r") as f:
        for line in f:
            line = line.strip()
            # Skip comments and empty lines
            if not line or line.startswith("#"):
                continue
            # Parse key=value
            if "=" in line:
                key, value = line.split("=", 1)
                env_vars[key.strip()] = value.strip()

    return env_vars


def save_env_file(env_vars: dict):
    """Save environment variables back to .env file."""
    env_file = Path(__file__).parent.parent / ".env"

    # Read original file to preserve comments and structure
    with open(env_file, "r") as f:
        lines = f.readlines()

    # Update values
    updated_lines = []
    for line in lines:
        stripped = line.strip()
        # Keep comments and empty lines as-is
        if not stripped or stripped.startswith("#"):
            updated_lines.append(line)
            continue

        # Update variable values
        if "=" in stripped:
            key = stripped.split("=", 1)[0].strip()
            if key in env_vars:
                updated_lines.append(f"{key}={env_vars[key]}\n")
            else:
                updated_lines.append(line)
        else:
            updated_lines.append(line)

    # Write back
    with open(env_file, "w") as f:
        f.writelines(updated_lines)


def get_status():
    """Get current lineage tracking status."""
    env_vars = load_env_file()

    enabled = env_vars.get("ENABLE_LINEAGE_TRACKING", "false")
    mode = env_vars.get("LINEAGE_TRACKING_MODE", "minimal")

    print("=" * 60)
    print("Lineage Tracking Status")
    print("=" * 60)
    print(f"  Enabled: {enabled}")
    print(f"  Mode: {mode}")
    print()

    if enabled.lower() in ("true", "1", "yes", "on"):
        print("✅ Lineage tracking is ENABLED")
        if mode == "full":
            print("   → Logging ALL events")
        elif mode == "minimal":
            print("   → Logging MAJOR events only (publishes, ingestions, merges)")
        elif mode == "off":
            print("   → Mode set to 'off' - no events will be logged")
    else:
        print("❌ Lineage tracking is DISABLED")
        print("   → No events will be logged to /lineage/events.ndjson")

    print()
    print("To change settings, use:")
    print("  python scripts/manage_lineage.py enable")
    print("  python scripts/manage_lineage.py disable")
    print("  python scripts/manage_lineage.py mode [full|minimal|off]")
    print()


def enable_tracking():
    """Enable lineage tracking."""
    env_vars = load_env_file()
    env_vars["ENABLE_LINEAGE_TRACKING"] = "true"
    save_env_file(env_vars)
    print("✅ Lineage tracking ENABLED")
    print(f"   Mode: {env_vars.get('LINEAGE_TRACKING_MODE', 'minimal')}")


def disable_tracking():
    """Disable lineage tracking."""
    env_vars = load_env_file()
    env_vars["ENABLE_LINEAGE_TRACKING"] = "false"
    save_env_file(env_vars)
    print("❌ Lineage tracking DISABLED")


def set_mode(mode: str):
    """Set lineage tracking mode."""
    valid_modes = ["full", "minimal", "off"]
    if mode not in valid_modes:
        print(f"Error: Invalid mode '{mode}'")
        print(f"Valid modes: {', '.join(valid_modes)}")
        sys.exit(1)

    env_vars = load_env_file()
    env_vars["LINEAGE_TRACKING_MODE"] = mode
    save_env_file(env_vars)

    print(f"✅ Lineage tracking mode set to: {mode}")
    if mode == "full":
        print("   → Will log ALL events")
    elif mode == "minimal":
        print("   → Will log MAJOR events only")
    elif mode == "off":
        print("   → Will NOT log any events")


def show_help():
    """Show help message."""
    print("""
Lineage Tracking Management

Usage:
  python scripts/manage_lineage.py <command> [arguments]

Commands:
  status              Show current lineage tracking status
  enable              Enable lineage tracking
  disable             Disable lineage tracking
  mode <mode>         Set tracking mode (full|minimal|off)

Modes:
  full                Log all events (entity changes, deliveries, edges, etc.)
  minimal             Log only major events (publishes, ingestions, major derivations)
  off                 Disable all lineage logging

Examples:
  # Check current status
  python scripts/manage_lineage.py status

  # Enable tracking with minimal mode (recommended for development)
  python scripts/manage_lineage.py enable
  python scripts/manage_lineage.py mode minimal

  # Enable full tracking (recommended for production)
  python scripts/manage_lineage.py enable
  python scripts/manage_lineage.py mode full

  # Disable tracking completely
  python scripts/manage_lineage.py disable

Configuration:
  Settings are stored in .env file:
    ENABLE_LINEAGE_TRACKING=true|false
    LINEAGE_TRACKING_MODE=full|minimal|off
""")


def main():
    if len(sys.argv) < 2:
        show_help()
        sys.exit(0)

    command = sys.argv[1].lower()

    if command == "status":
        get_status()
    elif command == "enable":
        enable_tracking()
    elif command == "disable":
        disable_tracking()
    elif command == "mode":
        if len(sys.argv) < 3:
            print("Error: mode command requires an argument (full|minimal|off)")
            sys.exit(1)
        set_mode(sys.argv[2].lower())
    elif command in ("help", "-h", "--help"):
        show_help()
    else:
        print(f"Error: Unknown command '{command}'")
        show_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
