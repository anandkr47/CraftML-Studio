#!/bin/bash
# Quick script to check backend logs
# Usage: ./scripts/check_backend_logs.sh

# Where the desktop app writes the backend's output (Tauri's per-user log directory)
if [ "$(uname -s)" = "Darwin" ]; then
    LOG_DIR="$HOME/Library/Logs/com.craftml.studio"
else
    LOG_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/com.craftml.studio/logs"
fi
STDOUT_LOG="$LOG_DIR/backend-stdout.log"
STDERR_LOG="$LOG_DIR/backend-stderr.log"

echo ""
echo "=== Backend Logs ==="
echo "Log Directory: $LOG_DIR"
echo ""

if [ -f "$STDOUT_LOG" ]; then
    echo "📄 STDOUT Log ($STDOUT_LOG):"
    echo "======================================================================"
    tail -n 50 "$STDOUT_LOG"
    echo "======================================================================"
else
    echo "⚠️  STDOUT log not found"
fi

echo ""
echo ""

if [ -f "$STDERR_LOG" ]; then
    echo "❌ STDERR Log ($STDERR_LOG):"
    echo "======================================================================"
    tail -n 50 "$STDERR_LOG"
    echo "======================================================================"
else
    echo "⚠️  STDERR log not found"
fi

echo ""
echo "=== End of Logs ==="

