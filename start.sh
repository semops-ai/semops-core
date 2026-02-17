#!/bin/bash
# Wrapper script for starting services
# Works on both Linux and Windows (Git Bash)

# On Windows Git Bash, prevent MSYS from converting Unix paths
if [[ "$OSTYPE" == "msys" || "$OSTYPE" == "win32" ]]; then
    export MSYS_NO_PATHCONV=1
fi

python3 start_services.py "$@"
