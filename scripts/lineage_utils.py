#!/usr/bin/env python3
"""
Lineage Tracking Utilities

Provides functions for logging lineage events to /lineage/events.ndjson
with configuration-based enable/disable support.
"""

import os
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Dict, Any, Literal

# Event types
EventType = Literal[
 "entity_created",
 "entity_updated",
 "entity_deleted",
 "edge_created",
 "edge_deleted",
 "delivery_queued",
 "delivery_published",
 "delivery_failed",
 "delivery_removed",
 "ingestion_started",
 "ingestion_completed",
 "github_pr_merged",
 "github_issue_created",
 "github_release_published",
]

# Lineage tracking modes
TrackingMode = Literal["full", "minimal", "off"]


class LineageTracker:
 """
 Centralized lineage event tracker with configurable enable/disable.
 """

 def __init__(self, lineage_file: Optional[str] = None):
 """
 Initialize lineage tracker.

 Args:
 lineage_file: Path to lineage events file (defaults to /lineage/events.ndjson)
 """
 self.lineage_file = lineage_file or self._get_default_lineage_file
 self.enabled = self._is_enabled
 self.mode = self._get_tracking_mode

 def _get_default_lineage_file(self) -> str:
 """Get default lineage file path."""
 # Assuming script is in /scripts, go up one level to repo root
 repo_root = Path(__file__).parent.parent
 return str(repo_root / "lineage" / "events.ndjson")

 def _is_enabled(self) -> bool:
 """Check if lineage tracking is enabled via environment variable."""
 enabled = os.getenv("ENABLE_LINEAGE_TRACKING", "false").lower
 return enabled in ("true", "1", "yes", "on")

 def _get_tracking_mode(self) -> TrackingMode:
 """Get lineage tracking mode from environment."""
 mode = os.getenv("LINEAGE_TRACKING_MODE", "minimal").lower
 if mode in ("full", "minimal", "off"):
 return mode
 return "minimal" # Default to minimal if invalid value

 def _is_major_event(self, event_type: EventType) -> bool:
 """
 Determine if an event is considered 'major' for minimal tracking.

 Major events:
 - Publishing/ingestion operations
 - Delivery status changes
 - GitHub merges/releases
 - Entity creation (but not updates)
 """
 major_events = {
 "entity_created",
 "delivery_published",
 "delivery_failed",
 "ingestion_completed",
 "github_pr_merged",
 "github_release_published",
 }
 return event_type in major_events

 def should_log(self, event_type: EventType) -> bool:
 """
 Determine if an event should be logged based on current settings.

 Args:
 event_type: Type of event to log

 Returns:
 True if event should be logged, False otherwise
 """
 # If tracking disabled or mode is 'off', don't log
 if not self.enabled or self.mode == "off":
 return False

 # If mode is 'full', log everything
 if self.mode == "full":
 return True

 # If mode is 'minimal', only log major events
 if self.mode == "minimal":
 return self._is_major_event(event_type)

 return False

 def log_event(
 self,
 event_type: EventType,
 data: Dict[str, Any],
 user: Optional[str] = None,
 timestamp: Optional[datetime] = None,
 ) -> bool:
 """
 Log a lineage event to the events.ndjson file.

 Args:
 event_type: Type of event being logged
 data: Event-specific data (entity_id, delivery_id, etc.)
 user: Optional user/system that triggered the event
 timestamp: Optional timestamp (defaults to now)

 Returns:
 True if event was logged, False if tracking is disabled

 Example:
 tracker.log_event(
 "entity_created",
 {"entity_id": "blog-post-ai", "content_kind": "blog_post"},
 user="tim"
 )
 """
 # Check if we should log this event
 if not self.should_log(event_type):
 return False

 # Build event object
 event = {
 "timestamp": (timestamp or datetime.now(timezone.utc)).isoformat,
 "type": event_type,
 **data,
 }

 if user:
 event["user"] = user

 # Append to NDJSON file
 try:
 with open(self.lineage_file, "a") as f:
 f.write(json.dumps(event) + "\n")
 return True
 except Exception as e:
 print(f"Warning: Failed to log lineage event: {e}")
 return False

 def get_status(self) -> Dict[str, Any]:
 """
 Get current lineage tracking status.

 Returns:
 Dictionary with tracking configuration
 """
 return {
 "enabled": self.enabled,
 "mode": self.mode,
 "lineage_file": self.lineage_file,
 "file_exists": os.path.exists(self.lineage_file),
 }


# Singleton instance for convenience
_default_tracker: Optional[LineageTracker] = None


def get_tracker -> LineageTracker:
 """Get the default lineage tracker singleton."""
 global _default_tracker
 if _default_tracker is None:
 _default_tracker = LineageTracker
 return _default_tracker


def log_event(
 event_type: EventType,
 data: Dict[str, Any],
 user: Optional[str] = None,
 timestamp: Optional[datetime] = None,
) -> bool:
 """
 Convenience function to log an event using the default tracker.

 Args:
 event_type: Type of event being logged
 data: Event-specific data
 user: Optional user/system that triggered the event
 timestamp: Optional timestamp (defaults to now)

 Returns:
 True if event was logged, False if tracking is disabled

 Example:
 from scripts.lineage_utils import log_event

 log_event(
 "entity_created",
 {"entity_id": "blog-post-ai", "content_kind": "blog_post"},
 user="tim"
 )
 """
 tracker = get_tracker
 return tracker.log_event(event_type, data, user, timestamp)


def get_tracking_status -> Dict[str, Any]:
 """Get current lineage tracking status."""
 tracker = get_tracker
 return tracker.get_status


if __name__ == "__main__":
 # CLI for checking status
 import sys

 if len(sys.argv) > 1 and sys.argv[1] == "status":
 status = get_tracking_status
 print("Lineage Tracking Status:")
 print(f" Enabled: {status['enabled']}")
 print(f" Mode: {status['mode']}")
 print(f" File: {status['lineage_file']}")
 print(f" File exists: {status['file_exists']}")
 else:
 print("Usage: python lineage_utils.py status")
