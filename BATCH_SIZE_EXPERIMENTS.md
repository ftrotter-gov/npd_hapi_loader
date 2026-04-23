# Batch Size Experiments

This document explains how to run batch size experiments for HAPI FHIR bulk imports.

## Overview

The `run_batch_size_experiments.py` script automates running multiple HAPI FHIR import experiments with different batch sizes to measure performance characteristics. Each experiment:

1. Creates a new HAPI FHIR Docker container
2. Runs bulk import with a specific batch size
3. Logs all output to `{experiment_dir}/run.log`
4. Stops and removes the container
5. Moves to the next experiment

All experiments run **sequentially** (not in parallel) to avoid resource conflicts.

## Experiments

The script runs 5 experiments with the following configurations:

| Experiment | Batch Size | Port | Directory |
|------------|------------|------|-----------|
| exp-500    | 500        | 8500 | /Volumes/eBolt/hapi_instance/exp-500 |
| exp-1000   | 1000       | 8501 | /Volumes/eBolt/hapi_instance/exp-1000 |
| exp-5000   | 5000       | 8502 | /Volumes/eBolt/hapi_instance/exp-5000 |
| exp-10000  | 10000      | 8503 | /Volumes/eBolt/hapi_instance/exp-10000 |
| exp-20000  | 20000      | 8504 | /Volumes/eBolt/hapi_instance/exp-20000 |

## Usage

### Basic Usage

```bash
python hload/run_batch_size_experiments.py /Volumes/eBolt/sliced_ndjson/WY/
```

This will:
- Use `/Volumes/eBolt/sliced_ndjson/WY/` as the source for NDJSON files
- Create experiments in `/Volumes/eBolt/hapi_instance/exp-*/`
- Log each experiment to its own `run.log` file

### Custom Base Directory

```bash
python hload/run_batch_size_experiments.py /path/to/ndjson \
  --base-dir /custom/experiment/path
```

### Custom CLI Path

```bash
python hload/run_batch_size_experiments.py /path/to/ndjson \
  --cli-path /usr/local/bin/hapi-fhir-cli
```

## Directory Structure

After running experiments, the directory structure will be:

```
/Volumes/eBolt/hapi_instance/
├── exp-500/
│   ├── run.log                    # Complete log of experiment
│   └── _container_storage/        # HAPI database (can be removed)
├── exp-1000/
│   ├── run.log
│   └── _container_storage/
├── exp-5000/
│   ├── run.log
│   └── _container_storage/
├── exp-10000/
│   ├── run.log
│   └── _container_storage/
└── exp-20000/
    ├── run.log
    └── _container_storage/
```

## Log Files

Each `run.log` contains:

1. **Experiment Header**: Batch size, port, directories, start time
2. **Container Creation**: Output from creating HAPI container
3. **Bulk Import**: Complete output from bulk import with timing
4. **Container Deletion**: Output from removing container
5. **Experiment Footer**: End time, success/failure status

### Example Log Entry

```
================================================================================
BATCH SIZE EXPERIMENT: exp-500
================================================================================
Experiment Name:  exp-500
Batch Size:       500
Port:             8500
Experiment Dir:   /Volumes/eBolt/hapi_instance/exp-500
Source Dir:       /Volumes/eBolt/sliced_ndjson/WY/
Start Time:       2026-04-07T05:30:00.000000
================================================================================

[... detailed output ...]

================================================================================
EXPERIMENT exp-500 COMPLETED
End Time:         2026-04-07T05:45:00.000000
Success:          Yes
================================================================================
```

## Analyzing Results

After experiments complete, you can:

### 1. Compare Timing

```bash
for exp in exp-500 exp-1000 exp-5000 exp-10000 exp-20000; do
  echo "$exp:"
  grep "Upload time:" /Volumes/eBolt/hapi_instance/$exp/run.log
  echo
done
```

### 2. Extract Performance Metrics

```bash
grep -A 3 "Successfully imported" /Volumes/eBolt/hapi_instance/exp-*/run.log
```

### 3. Check for Errors

```bash
grep -i "error\|failed" /Volumes/eBolt/hapi_instance/exp-*/run.log
```

## What Gets Measured

For each resource type (Organization, Location, Endpoint, Practitioner, etc.):

- **Upload time**: Total seconds for import
- **Speed**: Resources per second
- **Time per resource**: Milliseconds per resource
- **Estimated time for 1M resources**: Projected time for scaling

## Requirements

- Docker installed and running
- hapi-fhir-cli in PATH (or specify with `--cli-path`)
- Python 3.6+
- Source NDJSON files following naming conventions

## Troubleshooting

### Container Port Conflicts

If ports 8500-8504 are already in use, you'll need to:
1. Stop conflicting containers
2. Or modify the script to use different ports

### Out of Disk Space

Each experiment creates a HAPI database. After experiments, you can remove `_container_storage` directories:

```bash
rm -rf /Volumes/eBolt/hapi_instance/exp-*/_container_storage
```

Keep the `run.log` files for analysis.

### Failed Experiments

If an experiment fails:
1. Check the `run.log` file for errors
2. Ensure NDJSON files are present
3. Verify hapi-fhir-cli is working: `hapi-fhir-cli help`
4. Check Docker resources (memory, disk space)

## Implementation Details

### Sequential Execution

Experiments run one at a time with:
- Container startup and readiness checks
- Bulk import with specified batch size
- Container cleanup before next experiment
- 5-second pause between experiments

### Logging

Both console output and log files capture:
- All stdout and stderr from commands
- Timing information
- Success/failure status
- Complete hapi-fhir-cli output

### Cleanup

After each experiment:
- Container is stopped and removed
- Registry entry is cleaned up
- Database files remain for analysis (can be manually removed)

## Related Scripts

- **hapi_manager.py**: Manages HAPI containers
- **bulk_import_loader.py**: Handles bulk imports with batch size support
- **util/ndjson_discovery.py**: Discovers NDJSON files

## Example Session

```bash
$ python hload/run_batch_size_experiments.py /Volumes/eBolt/sliced_ndjson/WY/

================================================================================
BATCH SIZE EXPERIMENT SUITE
================================================================================
Source Directory:    /Volumes/eBolt/sliced_ndjson/WY/
Base Directory:      /Volumes/eBolt/hapi_instance
CLI Path:            hapi-fhir-cli
Number of Experiments: 5

Experiments:
  • exp-500: batch_size=500, port=8500
  • exp-1000: batch_size=1000, port=8501
  • exp-5000: batch_size=5000, port=8502
  • exp-10000: batch_size=10000, port=8503
  • exp-20000: batch_size=20000, port=8504
================================================================================

[... experiments run ...]

================================================================================
EXPERIMENT SUITE SUMMARY
================================================================================
Total Time: 1234.56 seconds (20.58 minutes)

Results:
  exp-500: ✅ SUCCESS
  exp-1000: ✅ SUCCESS
  exp-5000: ✅ SUCCESS
  exp-10000: ✅ SUCCESS
  exp-20000: ✅ SUCCESS

Successful: 5/5
Failed:     0/5

Log files:
  • exp-500: /Volumes/eBolt/hapi_instance/exp-500/run.log
  • exp-1000: /Volumes/eBolt/hapi_instance/exp-1000/run.log
  • exp-5000: /Volumes/eBolt/hapi_instance/exp-5000/run.log
  • exp-10000: /Volumes/eBolt/hapi_instance/exp-10000/run.log
  • exp-20000: /Volumes/eBolt/hapi_instance/exp-20000/run.log
================================================================================
```
