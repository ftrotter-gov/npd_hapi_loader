#!/usr/bin/env python3
"""
Batch Size Experiment Runner

Runs multiple HAPI FHIR import experiments with different batch sizes to
measure performance characteristics. Each experiment gets its own container
and logs to its own run.log file.
"""

import argparse
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import List, Dict


class ExperimentRunner:
    """
    Orchestrates batch size experiments for HAPI FHIR bulk imports.
    """
    
    # Experiment configurations: (name, batch_size, port)
    EXPERIMENTS = [
        ("exp-500", 500, 8500),
        ("exp-1000", 1000, 8501),
        ("exp-5000", 5000, 8502),
        ("exp-10000", 10000, 8503),
        ("exp-20000", 20000, 8504),
    ]
    
    @staticmethod
    def _run_command_with_logging(
        *,
        command: List[str],
        log_file: Path,
        description: str
    ) -> int:
        """
        Run a command and log output to file.
        
        Args:
            command: Command to execute
            log_file: Path to log file
            description: Description of command for logging
            
        Returns:
            Return code from command
        """
        with open(log_file, 'a') as log:
            # Write header
            log.write("=" * 80 + "\n")
            log.write(f"{description}\n")
            log.write(f"Time: {datetime.now().isoformat()}\n")
            log.write(f"Command: {' '.join(command)}\n")
            log.write("=" * 80 + "\n\n")
            log.flush()
            
            # Run command with output to both log and stdout
            process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1
            )
            
            # Stream output to both log and console
            for line in process.stdout:
                print(line, end='')
                log.write(line)
                log.flush()
            
            process.wait()
            
            # Write footer
            log.write("\n")
            log.write("=" * 80 + "\n")
            log.write(f"Exit code: {process.returncode}\n")
            log.write("=" * 80 + "\n\n")
            log.flush()
            
            return process.returncode
    
    @staticmethod
    def _wait_for_container_ready(*, container_name: str, port: int, timeout: int = 600) -> bool:
        """
        Wait for HAPI container to be ready by checking the metadata endpoint.
        Checks every 30 seconds until HAPI responds or timeout is reached.
        
        Args:
            container_name: Name of Docker container
            port: Port where HAPI is exposed
            timeout: Maximum seconds to wait (default: 600 = 10 minutes)
            
        Returns:
            True if container is ready, False if timeout
        """
        print(f"  ⏳ Waiting for container '{container_name}' to be ready...")
        print(f"     HAPI typically takes 30-90 seconds to fully initialize...")
        print(f"     Will check every 30 seconds until ready (timeout: {timeout}s)")
        start_time = time.time()
        
        # First verify container is running
        container_running = False
        for attempt in range(3):
            try:
                result = subprocess.run(
                    ["docker", "ps", "--filter", f"name=^{container_name}$", "--format", "{{.Status}}"],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                
                if result.returncode == 0 and result.stdout.strip():
                    container_running = True
                    print(f"     ✓ Container is running")
                    break
            except subprocess.TimeoutExpired:
                pass
            
            if attempt < 2:
                time.sleep(5)
        
        if not container_running:
            print(f"  ❌ Container did not start")
            return False
        
        # Now wait for HAPI to respond on metadata endpoint
        metadata_url = f"http://localhost:{port}/fhir/metadata"
        print(f"     Testing HAPI web interface at {metadata_url}")
        print(f"     Checking every 30 seconds...")
        
        check_interval = 30  # Check every 30 seconds as requested
        last_check_time = 0
        
        while True:
            elapsed = time.time() - start_time
            
            # Check if timeout reached
            if elapsed >= timeout:
                print(f"  ❌ Timeout ({timeout}s) waiting for container '{container_name}' to respond")
                return False
            
            # Only check every 30 seconds
            if elapsed - last_check_time >= check_interval or last_check_time == 0:
                last_check_time = elapsed
                
                print(f"     [{int(elapsed)}s] Checking HAPI endpoint...")
                
                try:
                    result = subprocess.run(
                        ["curl", "-s", "-o", "/dev/null", "-w", "%{http_code}", metadata_url],
                        capture_output=True,
                        text=True,
                        timeout=10
                    )
                    
                    http_code = result.stdout.strip()
                    
                    # Check if we got a 200 OK
                    if result.returncode == 0 and http_code == "200":
                        print(f"  ✅ Container '{container_name}' is ready and responding (HTTP {http_code})")
                        print(f"     Total startup time: {int(elapsed)} seconds")
                        return True
                    else:
                        if http_code:
                            print(f"     Response: HTTP {http_code} (not ready yet)")
                        else:
                            print(f"     No response yet (connection failed)")
                        
                except subprocess.TimeoutExpired:
                    print(f"     Request timed out (HAPI still starting...)")
                except Exception as e:
                    print(f"     Check failed: {e}")
            
            # Sleep briefly before next iteration
            time.sleep(5)
    
    @staticmethod
    def run_experiment(
        *,
        name: str,
        batch_size: int,
        port: int,
        base_dir: Path,
        source_dir: Path,
        cli_path: str = "hapi-fhir-cli"
    ) -> bool:
        """
        Run a single experiment.
        
        Args:
            name: Experiment name (e.g., 'exp-500')
            batch_size: Batch size for import
            port: Port for HAPI container
            base_dir: Base directory for experiment data
            source_dir: Source directory containing NDJSON files
            cli_path: Path to hapi-fhir-cli executable
            
        Returns:
            True if experiment succeeded, False otherwise
        """
        print("\n" + "=" * 80)
        print(f"EXPERIMENT: {name}")
        print(f"Batch Size: {batch_size}")
        print(f"Port: {port}")
        print("=" * 80)
        
        # Create experiment directory
        exp_dir = base_dir / name
        exp_dir.mkdir(parents=True, exist_ok=True)
        
        log_file = exp_dir / "run.log"
        
        # Write experiment header to log
        with open(log_file, 'w') as log:
            log.write("=" * 80 + "\n")
            log.write(f"BATCH SIZE EXPERIMENT: {name}\n")
            log.write("=" * 80 + "\n")
            log.write(f"Experiment Name:  {name}\n")
            log.write(f"Batch Size:       {batch_size}\n")
            log.write(f"Port:             {port}\n")
            log.write(f"Experiment Dir:   {exp_dir}\n")
            log.write(f"Source Dir:       {source_dir}\n")
            log.write(f"Start Time:       {datetime.now().isoformat()}\n")
            log.write("=" * 80 + "\n\n")
        
        # Get path to hapi_manager.py
        hapi_manager = Path(__file__).parent / "hapi_manager.py"
        
        try:
            # Step 1: Create and start HAPI container
            print(f"\n📦 Step 1: Creating HAPI container '{name}'...")
            cmd = [
                sys.executable,
                str(hapi_manager),
                "run",
                "--name", name,
                "--port", str(port),
                "--data-dir", str(exp_dir)
            ]
            
            returncode = ExperimentRunner._run_command_with_logging(
                command=cmd,
                log_file=log_file,
                description=f"Creating HAPI Container: {name}"
            )
            
            if returncode != 0:
                print(f"❌ Failed to create container")
                return False
            
            # Wait for container to be ready
            if not ExperimentRunner._wait_for_container_ready(container_name=name, port=port):
                print(f"❌ Container did not become ready in time")
                return False
            
            # Step 2: Run bulk import
            print(f"\n📥 Step 2: Running bulk import with batch size {batch_size}...")
            
            # Get path to bulk_import_loader.py
            bulk_loader = Path(__file__).parent / "bulk_import_loader.py"
            
            cmd = [
                sys.executable,
                str(bulk_loader),
                str(source_dir),
                "--name", name,
                "--batch-size", str(batch_size),
                "--verbose"
            ]
            
            returncode = ExperimentRunner._run_command_with_logging(
                command=cmd,
                log_file=log_file,
                description=f"Bulk Import (Batch Size: {batch_size})"
            )
            
            success = (returncode == 0)
            
            if success:
                print(f"✅ Bulk import completed successfully")
            else:
                print(f"⚠️  Bulk import completed with errors (exit code: {returncode})")
            
            # Step 3: Stop and remove container
            print(f"\n🗑️  Step 3: Stopping and removing container '{name}'...")
            cmd = [
                sys.executable,
                str(hapi_manager),
                "delete",
                "--name", name
            ]
            
            ExperimentRunner._run_command_with_logging(
                command=cmd,
                log_file=log_file,
                description=f"Deleting Container: {name}"
            )
            
            # Write experiment footer to log
            with open(log_file, 'a') as log:
                log.write("\n")
                log.write("=" * 80 + "\n")
                log.write(f"EXPERIMENT {name} COMPLETED\n")
                log.write(f"End Time:         {datetime.now().isoformat()}\n")
                log.write(f"Success:          {'Yes' if success else 'No'}\n")
                log.write("=" * 80 + "\n")
            
            print(f"\n📊 Experiment {name} completed. Log file: {log_file}")
            
            return success
            
        except Exception as error:
            print(f"\n❌ Exception during experiment: {error}")
            
            # Try to cleanup container
            try:
                print(f"🧹 Attempting to cleanup container '{name}'...")
                subprocess.run(
                    [sys.executable, str(hapi_manager), "delete", "--name", name],
                    timeout=30
                )
            except Exception:
                pass
            
            return False
    
    @staticmethod
    def run_all_experiments(
        *,
        source_dir: Path,
        base_dir: Path,
        cli_path: str = "hapi-fhir-cli"
    ) -> Dict[str, bool]:
        """
        Run all batch size experiments sequentially.
        
        Args:
            source_dir: Source directory containing NDJSON files
            base_dir: Base directory for experiment data
            cli_path: Path to hapi-fhir-cli executable
            
        Returns:
            Dictionary mapping experiment name to success status
        """
        print("=" * 80)
        print("BATCH SIZE EXPERIMENT SUITE")
        print("=" * 80)
        print(f"Source Directory:    {source_dir}")
        print(f"Base Directory:      {base_dir}")
        print(f"CLI Path:            {cli_path}")
        print(f"Number of Experiments: {len(ExperimentRunner.EXPERIMENTS)}")
        print()
        print("Experiments:")
        for name, batch_size, port in ExperimentRunner.EXPERIMENTS:
            print(f"  • {name}: batch_size={batch_size}, port={port}")
        print("=" * 80)
        
        # Validate source directory
        if not source_dir.exists():
            print(f"\n❌ Error: Source directory does not exist: {source_dir}")
            sys.exit(1)
        
        if not source_dir.is_dir():
            print(f"\n❌ Error: Source path is not a directory: {source_dir}")
            sys.exit(1)
        
        # Create base directory
        base_dir.mkdir(parents=True, exist_ok=True)
        
        # Run experiments
        results = {}
        start_time = time.time()
        
        for i, (name, batch_size, port) in enumerate(ExperimentRunner.EXPERIMENTS, 1):
            print(f"\n\n{'=' * 80}")
            print(f"RUNNING EXPERIMENT {i}/{len(ExperimentRunner.EXPERIMENTS)}")
            print(f"{'=' * 80}")
            
            success = ExperimentRunner.run_experiment(
                name=name,
                batch_size=batch_size,
                port=port,
                base_dir=base_dir,
                source_dir=source_dir,
                cli_path=cli_path
            )
            
            results[name] = success
            
            # Brief pause between experiments
            if i < len(ExperimentRunner.EXPERIMENTS):
                print(f"\n⏸️  Pausing 5 seconds before next experiment...")
                time.sleep(5)
        
        # Print summary
        total_time = time.time() - start_time
        
        print("\n\n" + "=" * 80)
        print("EXPERIMENT SUITE SUMMARY")
        print("=" * 80)
        print(f"Total Time: {total_time:.2f} seconds ({total_time/60:.2f} minutes)")
        print()
        print("Results:")
        for name, success in results.items():
            status = "✅ SUCCESS" if success else "❌ FAILED"
            print(f"  {name}: {status}")
        print()
        
        successful = sum(1 for s in results.values() if s)
        failed = sum(1 for s in results.values() if not s)
        
        print(f"Successful: {successful}/{len(results)}")
        print(f"Failed:     {failed}/{len(results)}")
        print()
        print("Log files:")
        for name in results.keys():
            log_file = base_dir / name / "run.log"
            print(f"  • {name}: {log_file}")
        print("=" * 80)
        
        return results


def main():
    """Main entry point for command-line execution."""
    parser = argparse.ArgumentParser(
        description="Run batch size experiments for HAPI FHIR bulk import",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
This script runs 5 experiments with different batch sizes:
  - exp-500:   batch size 500   (port 8500)
  - exp-1000:  batch size 1000  (port 8501)
  - exp-5000:  batch size 5000  (port 8502)
  - exp-10000: batch size 10000 (port 8503)
  - exp-20000: batch size 20000 (port 8504)

Each experiment:
  1. Creates a new HAPI FHIR container
  2. Runs bulk import with the specified batch size
  3. Logs all output to {base_dir}/{exp_name}/run.log
  4. Stops and removes the container

Experiments run sequentially (not in parallel).

Example:
  %(prog)s /Volumes/eBolt/sliced_ndjson/WY/
  %(prog)s /path/to/ndjson --base-dir /custom/path
        """
    )
    
    parser.add_argument(
        "source_dir",
        type=Path,
        help="Directory containing NDJSON files to import"
    )
    
    parser.add_argument(
        "--base-dir",
        type=Path,
        default=Path("/Volumes/eBolt/hapi_instance"),
        help="Base directory for experiment data (default: /Volumes/eBolt/hapi_instance)"
    )
    
    parser.add_argument(
        "--cli-path",
        type=str,
        default="hapi-fhir-cli",
        help="Path to hapi-fhir-cli executable (default: hapi-fhir-cli in PATH)"
    )
    
    args = parser.parse_args()
    
    try:
        results = ExperimentRunner.run_all_experiments(
            source_dir=args.source_dir,
            base_dir=args.base_dir,
            cli_path=args.cli_path
        )
        
        # Exit with error if any experiments failed
        failed_count = sum(1 for success in results.values() if not success)
        sys.exit(1 if failed_count > 0 else 0)
        
    except KeyboardInterrupt:
        print("\n\n⚠️  Experiment suite cancelled by user.")
        sys.exit(130)
    except Exception as error:
        print(f"\n❌ Fatal error: {error}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
