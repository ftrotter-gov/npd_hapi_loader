#!/usr/bin/env python3
"""
Bulk Import Loader using hapi-fhir-cli

This script uses the hapi-fhir-cli bulk-import command to load NDJSON files
into a HAPI FHIR server in a specific order to maintain referential integrity.

Uses util/ndjson_discovery.py to discover files following naming conventions.
"""

import argparse
import os
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Add parent directory to path to import util module
sys.path.insert(0, str(Path(__file__).parent.parent))

from util.ndjson_discovery import find_ndjson_files


class HapiInstanceRegistry:
    """Manages .env file with container instance registry"""
    
    ENV_FILE = Path(__file__).parent / ".env"
    
    @staticmethod
    def get_instance(*, name: str) -> Optional[Dict[str, str]]:
        """
        Get instance info by name.
        
        Args:
            name: Container name
            
        Returns:
            Instance info dictionary or None if not found
        """
        if not HapiInstanceRegistry.ENV_FILE.exists():
            return None
        
        with open(HapiInstanceRegistry.ENV_FILE, 'r') as f:
            for line in f:
                line = line.strip()
                # Skip empty lines and comments
                if not line or line.startswith('#'):
                    continue
                
                # Parse pipe-delimited format: NAME|PORT|DATA_DIR|STATUS
                parts = line.split('|')
                if len(parts) == 4:
                    instance_name, port, data_dir, status = parts
                    if instance_name == name:
                        return {
                            'port': port,
                            'data_dir': data_dir,
                            'status': status
                        }
        
        return None


class BulkImportLoader:
    """
    Loads FHIR resources using hapi-fhir-cli bulk-import command.
    
    Creates temporary subdirectories with symlinks to load resources
    one type at a time in a specific order.
    """
    
    # Resource loading order to maintain referential integrity
    RESOURCE_ORDER = [
        "Organization",
        "Location", 
        "Endpoint",
        "Practitioner",
        "OrganizationAffiliation",
        "PractitionerRole",
    ]
    
    @staticmethod
    def _find_available_port(*, start_port: int = 9090, max_attempts: int = 100) -> int:
        """
        Find an available port starting from start_port.
        
        The hapi-fhir-cli bulk-import command starts its own temporary server,
        so we need to find an available port for it to use.
        
        Args:
            start_port: Port to start searching from
            max_attempts: Maximum number of ports to try
            
        Returns:
            Available port number
            
        Raises:
            RuntimeError: If no available port found within max_attempts
        """
        for port_offset in range(max_attempts):
            port = start_port + port_offset
            try:
                # Try to bind to the port
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                    sock.bind(('0.0.0.0', port))
                    return port
            except OSError:
                # Port is in use, try next one
                continue
        
        raise RuntimeError(
            f"bulk_import_loader.py Error: Could not find available port in range "
            f"{start_port}-{start_port + max_attempts - 1}"
        )
    
    @staticmethod
    def validate_cli_available(*, cli_path: str) -> bool:
        """
        Check if hapi-fhir-cli is available and executable.
        
        Args:
            cli_path: Path to hapi-fhir-cli executable
            
        Returns:
            True if CLI is available, False otherwise
        """
        # First check if command is in PATH using shutil.which
        resolved_path = shutil.which(cli_path)
        if resolved_path is None:
            return False
        
        # Then verify it runs (hapi-fhir-cli uses 'help' not '--help')
        try:
            result = subprocess.run(
                [cli_path, "help"],
                capture_output=True,
                timeout=10
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError, PermissionError):
            return False
    
    @staticmethod
    def _create_temp_directory(*, source_dir: Path, resource_type: str) -> Path:
        """
        Create temporary subdirectory for a specific resource type.
        
        Args:
            source_dir: Source directory containing NDJSON files
            resource_type: FHIR resource type
            
        Returns:
            Path to temporary directory
        """
        temp_dir = source_dir / f".bulk_import_tmp_{resource_type}"
        temp_dir.mkdir(exist_ok=True)
        return temp_dir
    
    @staticmethod
    def _create_symlink(*, source_file: Path, temp_dir: Path) -> Path:
        """
        Create symlink in temporary directory.
        
        Args:
            source_file: Original NDJSON file
            temp_dir: Temporary directory
            
        Returns:
            Path to created symlink
        """
        symlink_path = temp_dir / source_file.name
        
        # Remove existing symlink if present
        if symlink_path.exists() or symlink_path.is_symlink():
            symlink_path.unlink()
        
        # Create new symlink
        symlink_path.symlink_to(source_file.absolute())
        return symlink_path
    
    @staticmethod
    def _cleanup_temp_directory(*, temp_dir: Path, verbose: bool = False) -> None:
        """
        Remove temporary directory and all contents.
        
        Args:
            temp_dir: Temporary directory to remove
            verbose: Enable verbose logging
        """
        if temp_dir.exists():
            if verbose:
                print(f"  🧹 Cleaning up: {temp_dir}")
            shutil.rmtree(temp_dir)
    
    @staticmethod
    def _count_lines(*, file_path: Path) -> int:
        """
        Count lines in a file using wc -l.
        
        Args:
            file_path: Path to file
            
        Returns:
            Number of lines in file
        """
        try:
            result = subprocess.run(
                ['wc', '-l', str(file_path)],
                capture_output=True,
                text=True,
                check=True
            )
            # wc -l output is like "  12345 filename"
            line_count = int(result.stdout.split()[0])
            return line_count
        except (subprocess.CalledProcessError, ValueError, IndexError):
            return 0
    
    @staticmethod
    def _run_bulk_import(
        *,
        cli_path: str,
        temp_dir: Path,
        target_url: str,
        port: int,
        fhir_version: str,
        batch_size: int = None,
        verbose: bool = False
    ) -> Tuple[subprocess.CompletedProcess, float]:
        """
        Execute hapi-fhir-cli bulk-import command with timing.
        
        Args:
            cli_path: Path to hapi-fhir-cli executable
            temp_dir: Directory containing NDJSON files to import
            target_url: Target HAPI server URL
            port: Port for CLI temporary server
            fhir_version: FHIR version (e.g., 'r4')
            batch_size: Batch size for processing resources (optional)
            verbose: Enable verbose logging
            
        Returns:
            Tuple of (CompletedProcess result, elapsed_time in seconds)
            
        Raises:
            subprocess.CalledProcessError: If command fails
        """
        command = [
            cli_path,
            "bulk-import",
            "-v", fhir_version,
            "--port", str(port),
            "--source-directory", str(temp_dir),
            "--target-base", target_url
        ]
        
        if batch_size is not None:
            command.extend(["--batch-size", str(batch_size)])
        
        if verbose:
            print(f"  🔧 Command: {' '.join(command)}")
        
        start_time = time.time()
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=False  # We'll handle errors manually
        )
        elapsed_time = time.time() - start_time
        
        return result, elapsed_time
    
    @staticmethod
    def load_resources(
        *,
        source_dir: Path,
        cli_path: str = "hapi-fhir-cli",
        target_url: str = "http://localhost:8080/fhir",
        port: int = 9090,
        fhir_version: str = "r4",
        batch_size: int = None,
        cleanup: bool = True,
        verbose: bool = False,
        stop_on_error: bool = True
    ) -> Dict[str, bool]:
        """
        Load FHIR resources using hapi-fhir-cli bulk-import.
        
        Args:
            source_dir: Directory containing NDJSON files
            cli_path: Path to hapi-fhir-cli executable
            target_url: Target HAPI server URL
            port: Port for CLI temporary server
            fhir_version: FHIR version
            batch_size: Batch size for processing resources (optional)
            cleanup: Whether to cleanup temporary directories
            verbose: Enable verbose logging
            stop_on_error: Stop on first error
            
        Returns:
            Dictionary mapping resource type to success status
            
        Raises:
            FileNotFoundError: If source directory doesn't exist
            RuntimeError: If hapi-fhir-cli is not available
        """
        if not source_dir.exists():
            raise FileNotFoundError(
                f"bulk_import_loader.py Error: Source directory not found: {source_dir}"
            )
        
        if not source_dir.is_dir():
            raise ValueError(
                f"bulk_import_loader.py Error: Not a directory: {source_dir}"
            )
        
        # Validate CLI is available
        if not BulkImportLoader.validate_cli_available(cli_path=cli_path):
            raise RuntimeError(
                f"bulk_import_loader.py Error: hapi-fhir-cli not found or not executable: {cli_path}"
            )
        
        # Find an available port for the CLI's temporary server
        # (The CLI starts its own server, separate from the target HAPI server)
        try:
            actual_port = BulkImportLoader._find_available_port(start_port=port)
            if actual_port != port:
                print(f"⚠️  Note: Requested CLI port {port} is in use, using port {actual_port} instead")
                print()
        except RuntimeError as error:
            raise RuntimeError(str(error))
        
        print("=" * 80)
        print("HAPI FHIR Bulk Import Loader")
        print("=" * 80)
        print(f"Source Directory:  {source_dir}")
        print(f"Target Server:     {target_url}")
        print(f"CLI Path:          {cli_path}")
        print(f"CLI Port:          {actual_port}")
        print(f"FHIR Version:      {fhir_version}")
        if batch_size is not None:
            print(f"Batch Size:        {batch_size}")
        print(f"Resource Order:    {', '.join(BulkImportLoader.RESOURCE_ORDER)}")
        print("=" * 80)
        print()
        
        # Discover NDJSON files
        print("🔍 Discovering NDJSON files...")
        discovered_files = find_ndjson_files(
            directory=source_dir,
            resource_types=BulkImportLoader.RESOURCE_ORDER
        )
        
        if not discovered_files:
            print("  ⚠️  No matching NDJSON files found")
            return {}
        
        print(f"  ✓ Found {len(discovered_files)} resource types:")
        for resource_type, file_path in discovered_files.items():
            print(f"    • {resource_type}: {file_path.name}")
        print()
        
        # Load resources in order
        print("🚀 Starting bulk import process...")
        print()
        
        results: Dict[str, bool] = {}
        temp_directories: List[Path] = []
        performance_stats: List[Dict[str, any]] = []
        
        for resource_type in BulkImportLoader.RESOURCE_ORDER:
            if resource_type not in discovered_files:
                print(f"⏭️  Skipping {resource_type} (no file found)")
                print()
                continue
            
            source_file = discovered_files[resource_type]
            
            # Count lines in the file
            line_count = BulkImportLoader._count_lines(file_path=source_file)
            print(f"📂 Loading {resource_type} from: {source_file.name}")
            print(f"   📊 File contains {line_count:,} resources")
            
            temp_dir = None
            try:
                # Create temporary directory and symlink
                temp_dir = BulkImportLoader._create_temp_directory(
                    source_dir=source_dir,
                    resource_type=resource_type
                )
                temp_directories.append(temp_dir)
                
                if verbose:
                    print(f"  📁 Created temp directory: {temp_dir}")
                
                symlink = BulkImportLoader._create_symlink(
                    source_file=source_file,
                    temp_dir=temp_dir
                )
                
                if verbose:
                    print(f"  🔗 Created symlink: {symlink}")
                
                # Run bulk import - ALWAYS show the command
                command = [
                    cli_path,
                    "bulk-import",
                    "-v", fhir_version,
                    "--port", str(actual_port),
                    "--source-directory", str(temp_dir),
                    "--target-base", target_url
                ]
                if batch_size is not None:
                    command.extend(["--batch-size", str(batch_size)])
                print(f"  🔧 Running command:")
                print(f"     {' '.join(command)}")
                print(f"  ⏳ Executing bulk import...")
                
                result, elapsed_time = BulkImportLoader._run_bulk_import(
                    cli_path=cli_path,
                    temp_dir=temp_dir,
                    target_url=target_url,
                    port=actual_port,
                    fhir_version=fhir_version,
                    batch_size=batch_size,
                    verbose=verbose
                )
                
                # Always show output
                if result.stdout:
                    print(f"\n  📋 Output:\n{result.stdout}")
                if result.stderr:
                    print(f"\n  ⚠️  Stderr:\n{result.stderr}")
                
                if result.returncode == 0:
                    # Calculate performance metrics
                    time_per_resource = elapsed_time / line_count if line_count > 0 else 0
                    resources_per_second = line_count / elapsed_time if elapsed_time > 0 else 0
                    time_for_1m = (1_000_000 * time_per_resource) / 60  # in minutes
                    
                    print(f"  ✅ Successfully imported {resource_type}")
                    print(f"     ⏱️  Upload time: {elapsed_time:.2f} seconds")
                    print(f"     📈 Speed: {resources_per_second:.2f} resources/second")
                    print(f"     📊 Time per resource: {time_per_resource*1000:.2f} ms")
                    print(f"     🚀 Estimated time for 1M resources: {time_for_1m:.2f} minutes ({time_for_1m/60:.2f} hours)")
                    
                    results[resource_type] = True
                    performance_stats.append({
                        'resource_type': resource_type,
                        'line_count': line_count,
                        'elapsed_time': elapsed_time,
                        'resources_per_second': resources_per_second,
                        'time_per_resource_ms': time_per_resource * 1000
                    })
                else:
                    print(f"  ❌ Failed to import {resource_type} (exit code: {result.returncode})")
                    print(f"     ⏱️  Time before failure: {elapsed_time:.2f} seconds")
                    results[resource_type] = False
                    
                    if stop_on_error:
                        print(f"\n⚠️  Stopping on error (--stop-on-error is enabled)")
                        break
                
                # Cleanup temp directory if requested
                if cleanup:
                    BulkImportLoader._cleanup_temp_directory(
                        temp_dir=temp_dir,
                        verbose=verbose
                    )
                    temp_directories.remove(temp_dir)
                
            except Exception as error:
                print(f"  ❌ Exception during import: {error}")
                results[resource_type] = False
                
                if stop_on_error:
                    print(f"\n⚠️  Stopping on error")
                    break
            
            print()
        
        # Final cleanup if needed
        if cleanup:
            for temp_dir in temp_directories:
                BulkImportLoader._cleanup_temp_directory(
                    temp_dir=temp_dir,
                    verbose=verbose
                )
        
        # Print summary
        print("=" * 80)
        print("IMPORT SUMMARY")
        print("=" * 80)
        successful = sum(1 for success in results.values() if success)
        failed = sum(1 for success in results.values() if not success)
        print(f"Successful: {successful}")
        print(f"Failed:     {failed}")
        print(f"Skipped:    {len(BulkImportLoader.RESOURCE_ORDER) - len(results)}")
        print("=" * 80)
        
        # Print performance summary
        if performance_stats:
            print()
            print("=" * 80)
            print("PERFORMANCE SUMMARY")
            print("=" * 80)
            
            total_resources = sum(stat['line_count'] for stat in performance_stats)
            total_time = sum(stat['elapsed_time'] for stat in performance_stats)
            
            if total_time > 0:
                overall_speed = total_resources / total_time
                overall_time_per_resource = total_time / total_resources if total_resources > 0 else 0
                overall_time_for_1m = (1_000_000 * overall_time_per_resource) / 60
                
                print(f"Total resources imported: {total_resources:,}")
                print(f"Total time: {total_time:.2f} seconds ({total_time/60:.2f} minutes)")
                print(f"Overall speed: {overall_speed:.2f} resources/second")
                print(f"Overall time per resource: {overall_time_per_resource*1000:.2f} ms")
                print(f"Estimated time for 1M resources: {overall_time_for_1m:.2f} minutes ({overall_time_for_1m/60:.2f} hours)")
            
            print("=" * 80)
        
        if failed > 0:
            print()
            print("=" * 80)
            print("❌❌❌ IMPORT FAILED ❌❌❌")
            print("=" * 80)
            print(f"⚠️  {failed} resource type(s) failed to import.")
            print("⚠️  Check the error messages above for details.")
            print("⚠️  The import process was NOT successful.")
            print("=" * 80)
        else:
            print()
            print("=" * 80)
            print("✅✅✅ IMPORT SUCCESSFUL ✅✅✅")
            print("=" * 80)
            print("✅ All resources imported successfully!")
            print("=" * 80)
        
        return results


def main():
    """Main entry point for command-line execution."""
    parser = argparse.ArgumentParser(
        description="Load FHIR resources using hapi-fhir-cli bulk-import",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s /path/to/ndjson/files
  %(prog)s /path/to/ndjson --target-url http://localhost:8080/fhir
  %(prog)s /path/to/ndjson --port 9090 --verbose
  %(prog)s /path/to/ndjson --cli-path /usr/local/bin/hapi-fhir-cli --no-cleanup
        """
    )
    
    parser.add_argument(
        "source_dir",
        type=Path,
        help="Directory containing NDJSON files"
    )
    
    parser.add_argument(
        "--cli-path",
        type=str,
        default="hapi-fhir-cli",
        help="Path to hapi-fhir-cli executable (default: hapi-fhir-cli in PATH)"
    )
    
    # Create mutually exclusive group for --name or --target-url
    target_group = parser.add_mutually_exclusive_group(required=False)
    target_group.add_argument(
        "--name",
        type=str,
        help="Container name (port will be looked up from registry)"
    )
    target_group.add_argument(
        "--target-url",
        type=str,
        help="Target HAPI FHIR server URL (default: http://localhost:8080/fhir if neither --name nor --target-url specified)"
    )
    
    parser.add_argument(
        "--port",
        type=int,
        default=9090,
        help="Port for CLI temporary server (default: 9090)"
    )
    
    parser.add_argument(
        "--fhir-version",
        type=str,
        default="r4",
        choices=["dstu2", "dstu3", "r4", "r5"],
        help="FHIR version (default: r4)"
    )
    
    parser.add_argument(
        "--batch-size",
        type=int,
        help="Batch size for processing resources (default: hapi-fhir-cli default)"
    )
    
    parser.add_argument(
        "--no-cleanup",
        action="store_true",
        help="Keep temporary directories (for debugging)"
    )
    
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose logging"
    )
    
    parser.add_argument(
        "--continue-on-error",
        action="store_true",
        help="Continue loading even if a resource fails"
    )
    
    args = parser.parse_args()
    
    # Determine target URL
    target_url = None
    if args.name:
        # Look up instance from registry
        instance = HapiInstanceRegistry.get_instance(name=args.name)
        if not instance:
            print(f"❌ Error: Instance '{args.name}' not found in registry.", file=sys.stderr)
            print(f"   Use --target-url instead, or run 'python hload/hapi_manager.py list' to see available instances.", file=sys.stderr)
            sys.exit(1)
        port = instance['port']
        target_url = f"http://localhost:{port}/fhir"
        print(f"📦 Using instance '{args.name}' on port {port}")
        print(f"   Target URL: {target_url}")
        print()
    elif args.target_url:
        target_url = args.target_url
    else:
        # Default
        target_url = "http://localhost:8080/fhir"
    
    try:
        results = BulkImportLoader.load_resources(
            source_dir=args.source_dir,
            cli_path=args.cli_path,
            target_url=target_url,
            port=args.port,
            fhir_version=args.fhir_version,
            batch_size=args.batch_size,
            cleanup=not args.no_cleanup,
            verbose=args.verbose,
            stop_on_error=not args.continue_on_error
        )
        
        # Exit with error code if any imports failed
        failed_count = sum(1 for success in results.values() if not success)
        sys.exit(1 if failed_count > 0 else 0)
        
    except Exception as error:
        print(f"\n❌ Fatal error: {error}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
