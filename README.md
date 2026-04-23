# HAPI Loader Study

This directory contains tools for loading FHIR resources into a HAPI FHIR server.

## Quick Start

The unified `hapi_manager.py` tool provides all functionality for managing HAPI FHIR Docker containers:

```bash
# Create and start a new instance
python hload/hapi_manager.py run --name my-hapi --port 8081 --data-dir /path/to/storage

# List all tracked instances
python hload/hapi_manager.py list

# Get detailed info about an instance
python hload/hapi_manager.py info --name my-hapi

# Load implementation guide
python hload/hapi_manager.py load-ig --name my-hapi

# Bulk import NDJSON files
python hload/hapi_manager.py bulk-import /path/to/ndjson --name my-hapi

# Delete instance (keeps data)
python hload/hapi_manager.py delete --name my-hapi

# Delete instance and all data (requires confirmation)
python hload/hapi_manager.py delete --name my-hapi --remove-data
```

## Background Import (for SSH sessions)

For long-running imports on remote servers, use the background import scripts that allow you to disconnect SSH without stopping the import:

```bash
# Start import in background with logging
./hload/run_background_import.sh

# Check progress anytime
./hload/check_import_progress.sh

# Watch the log in real-time
tail -f /data/hapi/logs/import_latest.log
```

**Features:**
- ✅ Runs in background with `nohup` (survives SSH disconnect)
- ✅ Auto-detects single HAPI instance from `.env`
- ✅ Batch size of 10,000 resources by default
- ✅ Timestamped log files in `/data/hapi/logs/`
- ✅ Process ID tracking for monitoring
- ✅ Prevents multiple simultaneous imports

**Configuration:**

Set environment variables to customize behavior:

```bash
# Custom source directory (default: /data/ndjson)
SOURCE_DIR=/path/to/my/ndjson ./hload/run_background_import.sh

# Custom log directory (default: /data/hapi/logs)
LOG_DIR=/var/log/hapi ./hload/run_background_import.sh

# Custom batch size (default: 10000)
BATCH_SIZE=5000 ./hload/run_background_import.sh

# Combine multiple settings
SOURCE_DIR=/data/ndjson LOG_DIR=/var/log/hapi BATCH_SIZE=10000 \
  ./hload/run_background_import.sh
```

**For multiple instances:**

If you have multiple HAPI instances in your registry, specify which one:

```bash
INSTANCE_NAME=my-hapi ./hload/run_background_import.sh
```

See [Background Import Workflow](#background-import-workflow) section below for detailed usage.

## Main Tool

### hapi_manager.py

Unified CLI tool for managing HAPI FHIR Docker containers with instance tracking.

**Features:**

- **Instance tracking**: Automatically tracks containers in `.env` registry
- **Port conflict detection**: Prevents starting containers on already-used ports
- **Custom storage locations**: Store container data anywhere on your system
- **Named instances**: Reference containers by name instead of remembering ports
- **Integrated commands**: All HAPI operations in one tool
- **Shell command wrapping**: Uses proven bash scripts under the hood

**Requirements:**

- Docker installed and running
- Python 3.6+
- `hapi-fhir-cli` installed for bulk import operations

#### Commands

##### run - Create/Start Container

Start or create a HAPI FHIR container with custom name, port, and storage location.

```bash
python hload/hapi_manager.py run --name CONTAINER_NAME --port PORT --data-dir DATA_DIR
```

**Arguments:**

- `--name`: Unique container name (required)
- `--port`: Port to expose (required, must be unique)
- `--data-dir`: Data directory path - can be relative or absolute (required)

**What it does:**

- Creates `{data-dir}/_container_storage/` for Docker volume mount
- Allows you to keep README files and notes in `{data-dir}/`
- Registers instance in `.env` tracking file
- Checks for port conflicts with other tracked instances

**Example:**

```bash
python hload/hapi_manager.py run --name my-hapi --port 8081 --data-dir /Volumes/eBolt/hapi_instances/my_hapi
```

This creates:

- `/Volumes/eBolt/hapi_instances/my_hapi/_container_storage/` (Docker volume)
- Container accessible at `http://localhost:8081/fhir`

##### delete - Remove Container

Stop and remove a HAPI FHIR container, optionally removing its data.

```bash
python hload/hapi_manager.py delete --name CONTAINER_NAME [--remove-data]
```

**Arguments:**

- `--name`: Container name (required)
- `--data-dir`: Data directory path (optional, retrieved from registry if not specified)
- `--remove-data`: Remove data directory (requires typing 'DELETE' to confirm)

**Example:**

```bash
# Delete container but keep data
python hload/hapi_manager.py delete --name my-hapi

# Delete container and all data (with confirmation prompt)
python hload/hapi_manager.py delete --name my-hapi --remove-data
```

##### list - Show All Instances

List all tracked HAPI FHIR instances from the registry.

```bash
python hload/hapi_manager.py list
```

**Output example:**

```text
====================================================================================================
TRACKED HAPI FHIR INSTANCES
====================================================================================================
NAME                      PORT     STATUS       DATA_DIR
----------------------------------------------------------------------------------------------------
my-hapi                   8081     running      /Volumes/eBolt/hapi_instances/my_hapi
test-instance             8082     running      /tmp/test_hapi
====================================================================================================
Total: 2 instance(s)
```

##### info - Show Instance Details

Display detailed information about a specific instance.

```bash
python hload/hapi_manager.py info --name CONTAINER_NAME
```

**Example:**

```bash
python hload/hapi_manager.py info --name my-hapi
```

**Output:**

- Port number
- Data directory location
- Storage path
- Server URL
- Current Docker container status (running/stopped/not found)

##### load-ig - Upload Implementation Guide

Upload an implementation guide package to a HAPI server.

```bash
python hload/hapi_manager.py load-ig IG_FILE --name CONTAINER_NAME
# OR
python hload/hapi_manager.py load-ig IG_FILE --port PORT
```

**Arguments:**

- `IG_FILE`: Path to IG package file (.tgz) - positional, required
- `--name`: Container name (port looked up from registry)
- `--port`: Port number (if not using --name)

**Example:**

```bash
# Using tracked instance name
python hload/hapi_manager.py load-ig ./ndh_package.tgz --name my-hapi

# Using port directly
python hload/hapi_manager.py load-ig /path/to/my-ig.tgz --port 8081

# With absolute path
python hload/hapi_manager.py load-ig /Volumes/eBolt/packages/ndh_package.tgz --name my-hapi
```

##### bulk-import - Import NDJSON Files

Bulk import NDJSON files into a HAPI FHIR server using `hapi-fhir-cli`.

```bash
python hload/hapi_manager.py bulk-import SOURCE_DIR --name CONTAINER_NAME [OPTIONS]
# OR
python hload/hapi_manager.py bulk-import SOURCE_DIR --port PORT [OPTIONS]
```

**Arguments:**

- `source_dir`: Directory containing NDJSON files (required)
- `--name`: Container name (port looked up from registry)
- `--port`: Port number (if not using --name)
- `--cli-path`: Path to hapi-fhir-cli executable (default: hapi-fhir-cli in PATH)
- `--verbose`: Enable verbose logging
- `--no-cleanup`: Keep temporary directories for debugging
- `--continue-on-error`: Continue loading even if a resource fails

**Example:**

```bash
# Using tracked instance name
python hload/hapi_manager.py bulk-import /path/to/ndjson --name my-hapi --verbose

# Using port directly with options
python hload/hapi_manager.py bulk-import /path/to/ndjson --port 8081 --continue-on-error
```

**How it works:**

- Uses `util/ndjson_discovery.py` to discover NDJSON files
- Loads resources in correct order: Organization → Location → Endpoint → Practitioner → OrganizationAffiliation → PractitionerRole
- Creates temporary subdirectories with symlinks (no file copying)
- Wraps the existing `bulk_import_loader.py` functionality

## Instance Registry

The `.env` file in the `hload/` directory tracks all container instances:

**Format:** `NAME|PORT|DATA_DIR|STATUS`

**Example:**

```text
my-hapi|8081|/Volumes/eBolt/hapi_instances/my_hapi|running
test-instance|8082|/tmp/test_hapi|running
```

**Note:** This file is auto-managed by `hapi_manager.py`. Do not edit manually.

## Data Directory Structure

When you create an instance with `--data-dir /path/to/my_instance`, the structure is:

```text
/path/to/my_instance/
├── _container_storage/          # Docker volume mount (PostgreSQL data)
├── README.md                    # Your notes (optional)
└── config.txt                   # Your configuration (optional)
```

The `_container_storage/` directory is used by Docker. You can add other files to the parent directory for documentation, configuration, or notes.

## Legacy Scripts

The original shell scripts are preserved for reference:

- `run_hapi_docker.sh` - Start HAPI container (replaced by `hapi_manager.py run`)
- `hard_delete_hapi_docker.sh` - Delete container (replaced by `hapi_manager.py delete`)
- `load_ig.sh` - Load IG (replaced by `hapi_manager.py load-ig`)
- `bulk_import_loader.py` - Bulk import (wrapped by `hapi_manager.py bulk-import`)

**Note:** The legacy scripts do not support instance tracking or custom storage locations. Use `hapi_manager.py` for all new workflows.

## File Naming Convention

All tools follow the naming conventions from `NamingConventions.md`:

- `ResourceType.ndjson` (exact match, preferred)
- `ResourceType.descriptor.ndjson` (with descriptor)
- `ResourceType.descriptor1.descriptor2.ndjson` (multiple descriptors)

Only `.ndjson` files are processed (NOT `.ndjson.gz`)

## Troubleshooting

### Port Already in Use

If you get a "port already in use" error:

1. Check tracked instances: `python hload/hapi_manager.py list`
2. Choose a different port or stop the conflicting container

### Container Not Starting

Check Docker logs:

```bash
docker logs CONTAINER_NAME
```

### Instance Not Found in Registry

If an instance isn't tracked but the container exists:

```bash
# List Docker containers
docker ps -a

# Use --port directly instead of --name
python hload/hapi_manager.py load-ig --port 8081
```

### Cleaning Up Registry

If the registry gets out of sync with actual Docker containers, you can manually edit `hload/.env` or delete it to start fresh.

## Examples

### Complete Workflow

```bash
# 1. Create a new HAPI instance
python hload/hapi_manager.py run \
  --name production-hapi \
  --port 8081 \
  --data-dir /Volumes/eBolt/hapi_prod

# 2. Wait for container to be ready (check logs)
docker logs production-hapi

# 3. Load implementation guide
python hload/hapi_manager.py load-ig ./ndh_package.tgz --name production-hapi

# 4. Bulk import NDJSON data
python hload/hapi_manager.py bulk-import \
  /Volumes/eBolt/palantir/ndjson/initial \
  --name production-hapi \
  --verbose

# 5. Check instance info
python hload/hapi_manager.py info --name production-hapi

# 6. Access FHIR server
# http://localhost:8081/fhir
```

### Multiple Instances

```bash
# Development instance
python hload/hapi_manager.py run \
  --name dev-hapi \
  --port 8081 \
  --data-dir ./hapi_dev

# Testing instance
python hload/hapi_manager.py run \
  --name test-hapi \
  --port 8082 \
  --data-dir ./hapi_test

# Production instance
python hload/hapi_manager.py run \
  --name prod-hapi \
  --port 8083 \
  --data-dir /Volumes/eBolt/hapi_prod

# List all instances
python hload/hapi_manager.py list
```

## Background Import Workflow

For long-running imports on remote servers (especially via SSH), use the dedicated background import scripts.

### Prerequisites

1. **Fix Docker permissions** (Ubuntu/Linux only):

```bash
# Add your user to docker group
sudo usermod -aG docker $USER

# Log out and back in, then verify
docker ps  # Should work without sudo
```

2. **Create necessary directories**:

```bash
# Create data directories
sudo mkdir -p /data/hapi /data/ndjson /data/hapi/logs
sudo chown $USER:$USER /data/hapi /data/ndjson /data/hapi/logs
```

3. **Set up HAPI instance**:

```bash
# Create a HAPI instance with storage under /data/hapi/
python hload/hapi_manager.py run \
  --name hapi-prod \
  --port 8080 \
  --data-dir /data/hapi/production

# Verify it's running
python hload/hapi_manager.py list
```

### Starting Background Import

The script automatically detects your HAPI instance from `.env` and uses sensible defaults:

```bash
# Simple - uses defaults:
# - Source: /data/ndjson
# - Logs: /data/hapi/logs/
# - Batch size: 10000
./hload/run_background_import.sh
```

**Custom configuration:**

```bash
# Custom source directory
SOURCE_DIR=/path/to/my/ndjson ./hload/run_background_import.sh

# Custom log location
LOG_DIR=/var/log/hapi ./hload/run_background_import.sh

# Custom batch size (smaller for memory-constrained systems)
BATCH_SIZE=5000 ./hload/run_background_import.sh

# Combine settings
SOURCE_DIR=/data/ndjson LOG_DIR=/data/hapi/logs BATCH_SIZE=10000 \
  ./hload/run_background_import.sh
```

**Expected output:**

```
HAPI FHIR Background Import Runner

✓ Log directory: /data/hapi/logs
✓ Using instance: hapi-prod (port 8080)
✓ Source directory: /data/ndjson
✓ Batch size: 10000
✓ Log file: /data/hapi/logs/import_20260416_094500.log

🚀 Starting background import...
   Command: python3 hapi_manager.py bulk-import "/data/ndjson" --name "hapi-prod" --batch-size 10000 --verbose

✅ Import started in background

   Process ID: 12345
   Log file: /data/hapi/logs/import_20260416_094500.log
   Latest log: /data/hapi/logs/import_latest.log

📊 Monitor progress:
   tail -f /data/hapi/logs/import_latest.log

You can now safely close this SSH session
```

### Monitoring Progress

**Check status:**

```bash
./hload/check_import_progress.sh
```

This shows:
- Whether import is running
- Process ID and runtime
- Memory and CPU usage
- Last 20 lines of log

**Watch live progress:**

```bash
# Follow the log in real-time (Ctrl+C to stop watching)
tail -f /data/hapi/logs/import_latest.log

# Show last 100 lines
tail -n 100 /data/hapi/logs/import_latest.log
```

**Check manually:**

```bash
# Check if process is running
ps aux | grep bulk_import_loader.py

# View full log
less /data/hapi/logs/import_latest.log

# Search for errors
grep -i error /data/hapi/logs/import_latest.log
```

### Stopping the Import

If you need to stop the import:

```bash
# Get the PID
cat /data/hapi/logs/import.pid

# Stop gracefully
kill $(cat /data/hapi/logs/import.pid)

# Force stop if needed
kill -9 $(cat /data/hapi/logs/import.pid)
```

### After Import Completes

The import will automatically stop when finished. Check the final status:

```bash
# Check if still running
./hload/check_import_progress.sh

# View final summary in log
tail -n 50 /data/hapi/logs/import_latest.log
```

### Log File Management

Logs are timestamped and kept for historical reference:

```bash
# List all import logs
ls -lh /data/hapi/logs/import_*.log

# View specific log
less /data/hapi/logs/import_20260416_094500.log

# Clean up old logs (manual)
find /data/hapi/logs -name "import_*.log" -mtime +30 -delete
```

### Troubleshooting Background Import

**Import won't start:**

1. Check Docker permissions: `docker ps` (should work without sudo)
2. Verify source directory exists: `ls -la /data/ndjson`
3. Check HAPI instance is running: `python hload/hapi_manager.py list`

**Import stopped unexpectedly:**

1. Check the log for errors: `tail -n 100 /data/hapi/logs/import_latest.log`
2. Check disk space: `df -h /data`
3. Check HAPI container logs: `docker logs hapi-prod`

**Multiple instances in registry:**

If you have multiple HAPI instances, specify which one:

```bash
INSTANCE_NAME=hapi-prod ./hload/run_background_import.sh
```

### Ubuntu VM Setup Example

Complete setup for Ubuntu VM with storage under `/data/hapi/`:

```bash
# 1. Fix Docker permissions
sudo usermod -aG docker $USER
exit  # Log out and back in

# 2. Create directories
sudo mkdir -p /data/hapi /data/ndjson /data/hapi/logs
sudo chown $USER:$USER /data/hapi /data/ndjson /data/hapi/logs

# 3. Copy NDJSON files to /data/ndjson/
# (use scp, rsync, or whatever method you prefer)

# 4. Create HAPI instance
cd ~/gitgov/DSACMS/FHIRTableSaw
python hload/hapi_manager.py run \
  --name hapi-prod \
  --port 8080 \
  --data-dir /data/hapi/production

# 5. Wait for HAPI to start (30-60 seconds)
docker logs -f hapi-prod
# Press Ctrl+C when you see "Started Application"

# 6. Start background import
./hload/run_background_import.sh

# 7. Disconnect SSH safely
exit

# 8. Reconnect later to check progress
ssh user@your-server
cd ~/gitgov/DSACMS/FHIRTableSaw
./hload/check_import_progress.sh
```

=====================
