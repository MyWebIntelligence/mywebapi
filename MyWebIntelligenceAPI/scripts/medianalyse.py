#!/usr/bin/env python3
"""
Media Analysis CLI script for MyWebIntelligence API.

This script provides the new asynchronous media analysis functionality
with depth and minimum relevance parameters using Celery tasks.

The --depth and --minrel parameters are now ACTIVE and mandatory for proper filtering!

Usage:
    medianalyse --land-id 1 --depth 2 --minrel 0.5 [--monitor]

Examples:
    # Basic async media analysis with depth and minrel filters
    python scripts/medianalyse.py --land-id 1 --depth 2 --minrel 0.5

    # With monitoring
    python scripts/medianalyse.py --land-id 1 --depth 3 --minrel 0.3 --monitor

    # Monitor existing job
    python scripts/medianalyse.py --monitor --job-id 123
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from typing import Dict, Any, Optional

import requests


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run asynchronous media analysis with depth and relevance filters via Celery.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
The --depth and --minrel parameters are now ACTIVE and control which expressions are analyzed:
  --depth: Maximum crawl depth (0 = seed URLs only, 1 = one level deep, etc.)
  --minrel: Minimum relevance score (0.0 to 1.0, filters low-relevance expressions)

Examples:
  %(prog)s --land-id 1 --depth 2 --minrel 0.5 --monitor
  %(prog)s --land-id 1 --depth 0 --minrel 0.0  # Analyze all seed URL media
  %(prog)s --monitor --job-id 123  # Monitor existing job
        """
    )
    parser.add_argument(
        "--base-url",
        default=os.getenv("MYWI_BASE_URL", "http://localhost:8000"),
        help="Base URL of the API (default: http://localhost:8000)",
    )
    parser.add_argument(
        "--username",
        default=os.getenv("MYWI_USERNAME", "admin@example.com"),
        help="Username for authentication (default: admin@example.com)",
    )
    parser.add_argument(
        "--password",
        default=os.getenv("MYWI_PASSWORD", "changeme"),
        help="Password for authentication (default: changeme)",
    )
    parser.add_argument(
        "--land-id",
        type=int,
        help="ID of the land to analyze media for (required unless --job-id)",
    )
    parser.add_argument(
        "--depth",
        type=int,
        help="Maximum depth of expressions to analyze (ACTIVE parameter)",
    )
    parser.add_argument(
        "--minrel",
        type=float,
        help="Minimum relevance score for expressions (ACTIVE parameter, 0.0-1.0)",
    )
    parser.add_argument(
        "--monitor",
        action="store_true",
        help="Monitor job progress until completion",
    )
    parser.add_argument(
        "--job-id",
        type=int,
        help="Monitor existing job by ID (use with --monitor)",
    )
    parser.add_argument(
        "--check-interval",
        type=int,
        default=10,
        help="Job monitoring check interval in seconds (default: 10)",
    )
    parser.add_argument(
        "--max-wait",
        type=int,
        default=1800,  # 30 minutes
        help="Maximum wait time for job completion in seconds (default: 1800)",
    )
    return parser.parse_args()


def authenticate(base_url: str, username: str, password: str) -> str:
    """Authenticate and return JWT token."""
    response = requests.post(
        f"{base_url.rstrip('/')}/api/v1/auth/login",
        data={"username": username, "password": password},
        timeout=30,
    )
    response.raise_for_status()
    data = response.json()
    return data["access_token"]


def start_media_analysis_async(
    session: requests.Session,
    base_url: str,
    land_id: int,
    depth: Optional[int],
    minrel: Optional[float],
) -> Dict[str, Any]:
    """Start asynchronous media analysis task via Celery."""
    payload: Dict[str, Any] = {}
    if depth is not None:
        payload["depth"] = depth
    if minrel is not None:
        payload["minrel"] = minrel

    print(f"Starting async media analysis for land {land_id}...")
    print(f"Parameters: depth={depth}, minrel={minrel}")
    
    response = session.post(
        f"{base_url.rstrip('/')}/api/v2/lands/{land_id}/media-analysis-async",
        json=payload,
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def get_job_status(
    session: requests.Session,
    base_url: str,
    job_id: int,
) -> Dict[str, Any]:
    """Get job status by ID."""
    response = session.get(
        f"{base_url.rstrip('/')}/api/v1/jobs/{job_id}",
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def monitor_job(
    session: requests.Session,
    base_url: str,
    job_id: int,
    check_interval: int = 10,
    max_wait_time: int = 1800,
) -> Dict[str, Any]:
    """Monitor job progress until completion."""
    print(f"Monitoring job {job_id}...")
    print(f"Check interval: {check_interval}s, Max wait time: {max_wait_time}s")
    print("=" * 60)
    
    start_time = time.time()
    last_status = None
    
    while True:
        elapsed = time.time() - start_time
        if elapsed > max_wait_time:
            print(f"\nTimeout after {max_wait_time}s")
            break
        
        try:
            status_response = get_job_status(session, base_url, job_id)
            job_status = status_response.get("status", "unknown")
            
            # Only print if status changed or every minute
            if job_status != last_status or int(elapsed) % 60 == 0:
                print(f"[{elapsed:.0f}s] Job {job_id} status: {job_status}")
                last_status = job_status
            
            if job_status in ["completed", "failed", "cancelled"]:
                print("=" * 60)
                return status_response
            
            if job_status == "running":
                result = status_response.get("result")
                if result and isinstance(result, dict):
                    analyzed = result.get("analyzed_media", 0)
                    total = result.get("total_media", 0)
                    failed = result.get("failed_analysis", 0)
                    if total > 0:
                        progress = (analyzed / total) * 100
                        print(f"  Progress: {analyzed}/{total} ({progress:.1f}%) - Failed: {failed}")
            
        except requests.exceptions.RequestException as e:
            print(f"Error checking job status: {e}")
        
        time.sleep(check_interval)
    
    # Final status check
    try:
        return get_job_status(session, base_url, job_id)
    except requests.exceptions.RequestException as e:
        return {"error": f"Failed to get final status: {e}"}


def pretty_print(title: str, data: Any) -> None:
    """Pretty print data with title."""
    print(f"\n=== {title} ===")
    if isinstance(data, (dict, list)):
        print(json.dumps(data, indent=2, ensure_ascii=False))
    else:
        print(data)


def print_analysis_summary(result: Dict[str, Any]) -> None:
    """Print a summary of analysis results."""
    print(f"\n=== Media Analysis Results ===")
    print(f"Land: {result.get('land_name', 'Unknown')} (ID: {result.get('land_id', 'N/A')})")
    print(f"Total Expressions: {result.get('total_expressions', 0)}")
    print(f"Filtered Expressions: {result.get('filtered_expressions', 0)}")
    print(f"Total Media: {result.get('total_media', 0)}")
    print(f"Analyzed Media: {result.get('analyzed_media', 0)}")
    print(f"Failed Analysis: {result.get('failed_analysis', 0)}")
    
    total_processed = result.get('analyzed_media', 0) + result.get('failed_analysis', 0)
    if total_processed > 0:
        success_rate = (result.get('analyzed_media', 0) / total_processed) * 100
        print(f"Success Rate: {success_rate:.1f}%")
    
    processing_time = result.get('processing_time', 0)
    if processing_time:
        print(f"Processing Time: {processing_time:.2f}s")
    
    filters = result.get('filters_applied', {})
    if filters:
        print(f"Filters Applied: {filters}")
    
    print("=" * 50)


def main() -> None:
    args = parse_args()

    # Validate arguments
    if not args.job_id and not args.land_id:
        print("Error: Either --land-id or --job-id is required", file=sys.stderr)
        sys.exit(1)

    if args.job_id and not args.monitor:
        print("Warning: --job-id provided without --monitor, enabling monitoring automatically")
        args.monitor = True

    if args.land_id and (args.depth is None or args.minrel is None):
        print("Warning: --depth and --minrel parameters are ACTIVE and should be specified!")
        print("Using defaults: depth=999 (no limit), minrel=0.0 (all expressions)")

    print(f"Authenticating as {args.username}...")
    token = authenticate(args.base_url, args.username, args.password)
    session = requests.Session()
    session.headers.update({"Authorization": f"Bearer {token}"})

    try:
        if args.job_id:
            # Monitor existing job
            print(f"Monitoring existing job {args.job_id}...")
            result = monitor_job(session, args.base_url, args.job_id, args.check_interval, args.max_wait)
            pretty_print("Final Job Status", result)
            
            # Print summary if result contains analysis data
            if result.get("result"):
                print_analysis_summary(result["result"])
        
        else:
            # Start new async analysis
            job_response = start_media_analysis_async(
                session, args.base_url, args.land_id, args.depth, args.minrel
            )
            pretty_print("Async Job Started", job_response)
            
            job_id = job_response.get("job_id")
            if job_id and args.monitor:
                # Monitor the job
                result = monitor_job(session, args.base_url, job_id, args.check_interval, args.max_wait)
                pretty_print("Final Job Status", result)
                
                # Print summary if result contains analysis data
                if result.get("result"):
                    print_analysis_summary(result["result"])
            else:
                print(f"\nJob started with ID: {job_id}")
                print(f"Monitor with: python {sys.argv[0]} --monitor --job-id {job_id}")

        print("\nMedia analysis completed successfully.")

    except requests.exceptions.RequestException as e:
        print(f"API Error: {e}", file=sys.stderr)
        if hasattr(e, 'response') and e.response is not None:
            try:
                error_detail = e.response.json()
                pretty_print("Error Details", error_detail)
            except:
                print(f"Response text: {e.response.text}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nOperation cancelled by user.", file=sys.stderr)
        sys.exit(1)
    except Exception as exc:
        print(f"Unexpected error: {exc}", file=sys.stderr)
        sys.exit(1)