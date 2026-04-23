#!/bin/bash

#
# Background HAPI FHIR Import Runner
#
# Runs bulk_import_loader.py in the background with logging
# Allows SSH disconnection without stopping the import
#

set -e

# Configuration
SOURCE_DIR="${SOURCE_DIR:-/data/ndjson}"
LOG_DIR="${LOG_DIR:-/data/hapi/logs}"
BATCH_SIZE="${BATCH_SIZE:-10000}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
LOG_FILE="${LOG_DIR}/import_${TIMESTAMP}.log"
PID_FILE="${LOG_DIR}/import.pid"
LATEST_LOG_LINK="${LOG_DIR}/import_latest.log"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo "=========================================="
echo "HAPI FHIR Background Import Runner"
echo "=========================================="
echo ""

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Change to project root
cd "$PROJECT_ROOT"

# Check if source directory exists
if [ ! -d "$SOURCE_DIR" ]; then
    echo -e "${RED}❌ Error: Source directory not found: $SOURCE_DIR${NC}"
    echo "   Set SOURCE_DIR environment variable to override"
    exit 1
fi

# Check Docker permissions
if ! docker ps &> /dev/null; then
    echo -e "${RED}❌ Error: Cannot access Docker${NC}"
    echo "   Run: sudo usermod -aG docker \$USER"
    echo "   Then log out and back in"
    exit 1
fi

# Check if hapi-fhir-cli is installed
if ! command -v hapi-fhir-cli &> /dev/null; then
    echo -e "${RED}❌ Error: hapi-fhir-cli is not installed or not in PATH${NC}"
    echo ""
    echo "   The bulk import process requires hapi-fhir-cli to be installed."
    echo ""
    echo "   Installation instructions:"
    echo "   1. Download from: https://github.com/hapifhir/hapi-fhir/releases"
    echo "   2. Look for 'hapi-fhir-cli' in the latest release"
    echo "   3. Download the JAR file"
    echo "   4. Create a wrapper script named 'hapi-fhir-cli' in your PATH:"
    echo ""
    echo "      #!/bin/bash"
    echo "      java -jar /path/to/hapi-fhir-cli.jar \"\$@\""
    echo ""
    echo "   5. Make it executable: chmod +x /path/to/hapi-fhir-cli"
    echo ""
    exit 1
fi

# Verify hapi-fhir-cli actually works
if ! hapi-fhir-cli help &> /dev/null; then
    echo -e "${RED}❌ Error: hapi-fhir-cli found but not working${NC}"
    echo "   Command 'hapi-fhir-cli help' failed"
    echo "   Verify Java is installed and hapi-fhir-cli is properly configured"
    exit 1
fi

echo -e "${GREEN}✓${NC} hapi-fhir-cli is installed and working"

# Create log directory
mkdir -p "$LOG_DIR"
echo -e "${GREEN}✓${NC} Log directory: $LOG_DIR"

# Read .env to find instance
ENV_FILE="$SCRIPT_DIR/.env"
if [ ! -f "$ENV_FILE" ]; then
    echo -e "${RED}❌ Error: No .env registry found${NC}"
    echo "   Run: python hload/hapi_manager.py run --name ... --port ... --data-dir ..."
    exit 1
fi

# Count non-comment lines in .env
INSTANCE_COUNT=$(grep -v '^#' "$ENV_FILE" | grep -v '^$' | wc -l | tr -d ' ')

if [ "$INSTANCE_COUNT" -eq "0" ]; then
    echo -e "${RED}❌ Error: No HAPI instances found in registry${NC}"
    echo "   Run: python hload/hapi_manager.py run --name ... --port ... --data-dir ..."
    exit 1
elif [ "$INSTANCE_COUNT" -gt "1" ]; then
    echo -e "${RED}❌ Error: Multiple HAPI instances found in registry${NC}"
    echo "   Please specify which instance to use with INSTANCE_NAME environment variable"
    echo ""
    echo "   Available instances:"
    grep -v '^#' "$ENV_FILE" | grep -v '^$' | while IFS='|' read -r name port data_dir status; do
        echo "     - $name (port $port)"
    done
    echo ""
    echo "   Usage: INSTANCE_NAME=my-hapi $0"
    exit 1
fi

# Get the single instance
INSTANCE_LINE=$(grep -v '^#' "$ENV_FILE" | grep -v '^$')
INSTANCE_NAME=$(echo "$INSTANCE_LINE" | cut -d'|' -f1)
INSTANCE_PORT=$(echo "$INSTANCE_LINE" | cut -d'|' -f2)

echo -e "${GREEN}✓${NC} Using instance: $INSTANCE_NAME (port $INSTANCE_PORT)"
echo -e "${GREEN}✓${NC} Source directory: $SOURCE_DIR"
echo -e "${GREEN}✓${NC} Batch size: $BATCH_SIZE"
echo -e "${GREEN}✓${NC} Log file: $LOG_FILE"
echo ""

# Check if import is already running
if [ -f "$PID_FILE" ]; then
    OLD_PID=$(cat "$PID_FILE")
    if ps -p "$OLD_PID" > /dev/null 2>&1; then
        echo -e "${YELLOW}⚠️  Warning: Import already running (PID: $OLD_PID)${NC}"
        echo "   Log: $LATEST_LOG_LINK"
        echo "   To stop: kill $OLD_PID"
        exit 1
    else
        echo -e "${YELLOW}⚠️  Cleaning up stale PID file${NC}"
        rm -f "$PID_FILE"
    fi
fi

# Build command
PYTHON_CMD="python3"
if ! command -v python3 &> /dev/null; then
    PYTHON_CMD="python"
fi

echo "🚀 Starting background import..."
echo "   Command: $PYTHON_CMD hload/hapi_manager.py bulk-import $SOURCE_DIR --name $INSTANCE_NAME --batch-size $BATCH_SIZE --verbose"
echo ""

# Run in background with nohup
# Don't use a CMD variable - pass arguments directly to avoid quote issues
# Use tee to send output to both terminal and log file
nohup "$PYTHON_CMD" hload/hapi_manager.py bulk-import "$SOURCE_DIR" \
    --name "$INSTANCE_NAME" \
    --batch-size "$BATCH_SIZE" \
    --verbose 2>&1 | tee "$LOG_FILE" &
IMPORT_PID=$!

# Save PID
echo "$IMPORT_PID" > "$PID_FILE"

# Create symlink to latest log
ln -sf "$LOG_FILE" "$LATEST_LOG_LINK"

echo -e "${GREEN}✅ Import started in background${NC}"
echo ""
echo "   Process ID: $IMPORT_PID"
echo "   Log file: $LOG_FILE"
echo "   Latest log: $LATEST_LOG_LINK"
echo ""
echo "📊 Monitor progress:"
echo "   tail -f $LATEST_LOG_LINK"
echo ""
echo "🔍 Check if running:"
echo "   ps aux | grep $IMPORT_PID"
echo "   # OR use the helper script:"
echo "   ./hload/check_import_progress.sh"
echo ""
echo "🛑 Stop import:"
echo "   kill $IMPORT_PID"
echo ""
echo "=========================================="
echo "You can now safely close this SSH session"
echo "=========================================="
