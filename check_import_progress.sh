#!/bin/bash

#
# Check HAPI FHIR Import Progress
#
# Shows status of background import and recent log entries
#

# Configuration
LOG_DIR="${LOG_DIR:-/data/hapi/logs}"
PID_FILE="${LOG_DIR}/import.pid"
LATEST_LOG_LINK="${LOG_DIR}/import_latest.log"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo "=========================================="
echo "HAPI FHIR Import Progress Check"
echo "=========================================="
echo ""

# Check if PID file exists
if [ ! -f "$PID_FILE" ]; then
    echo -e "${YELLOW}⚠️  No import process found${NC}"
    echo "   PID file not found: $PID_FILE"
    echo ""
    echo "   To start import: ./hload/run_background_import.sh"
    exit 0
fi

# Read PID
IMPORT_PID=$(cat "$PID_FILE")

# Check if process is running
if ps -p "$IMPORT_PID" > /dev/null 2>&1; then
    echo -e "${GREEN}✅ Import is RUNNING${NC}"
    echo "   Process ID: $IMPORT_PID"
    
    # Show process info
    echo ""
    echo "📊 Process Info:"
    ps -p "$IMPORT_PID" -o pid,ppid,cmd,etime,pmem,pcpu --no-headers | \
        awk '{printf "   PID: %s\n   Parent PID: %s\n   Command: %s\n   Runtime: %s\n   Memory: %s%%\n   CPU: %s%%\n", $1, $2, $3" "$4" "$5" "$6" "$7" "$8, $9, $10, $11}'
else
    echo -e "${RED}❌ Import is NOT RUNNING${NC}"
    echo "   PID file exists but process $IMPORT_PID is not running"
    echo "   (Process may have completed or crashed)"
    echo ""
    rm -f "$PID_FILE"
fi

# Check log file
echo ""
if [ -f "$LATEST_LOG_LINK" ]; then
    echo "📋 Log file: $LATEST_LOG_LINK"
    
    # Get log file size
    LOG_SIZE=$(du -h "$LATEST_LOG_LINK" | cut -f1)
    echo "   Size: $LOG_SIZE"
    
    # Count lines
    LINE_COUNT=$(wc -l < "$LATEST_LOG_LINK")
    echo "   Lines: $LINE_COUNT"
    
    echo ""
    echo "📄 Last 20 lines of log:"
    echo "=========================================="
    tail -n 20 "$LATEST_LOG_LINK"
    echo "=========================================="
    
    echo ""
    echo "💡 To follow the log in real-time:"
    echo "   tail -f $LATEST_LOG_LINK"
else
    echo -e "${YELLOW}⚠️  Log file not found: $LATEST_LOG_LINK${NC}"
fi

echo ""

# Show all log files
echo "📁 All import logs in $LOG_DIR:"
if [ -d "$LOG_DIR" ]; then
    ls -lht "$LOG_DIR"/import_*.log 2>/dev/null | head -n 5 || echo "   No log files found"
fi

echo ""
echo "=========================================="
