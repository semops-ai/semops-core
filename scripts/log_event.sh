#!/usr/bin/env bash
# log_event.sh - append a JSON line to lineage/events.ndjson

set -euo pipefail
mkdir -p lineage
payload="${1:-}"
if [ -z "$payload" ]; then
 echo "Usage: log_event.sh '{"verb":"custom","subject":"..."}'"
 exit 1
fi
echo "$payload" | jq -c '.' >> lineage/events.ndjson
echo "Appended."
