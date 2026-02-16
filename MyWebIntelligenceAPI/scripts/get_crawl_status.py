#!/usr/bin/env python3
"""
Script to get the status and results of a crawl job.
"""

import argparse
import sys
import requests
from typing import Optional

def get_token(base_url: str, username: str, password: str) -> Optional[str]:
    """Authenticate and get access token."""
    try:
        response = requests.post(
            f"{base_url}/api/v1/auth/login",
            data={"username": username, "password": password},
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )
        response.raise_for_status()
        return response.json()["access_token"]
    except Exception as e:
        print(f"Authentication failed: {e}")
        return None

def get_land_details(base_url: str, token: str, land_id: int) -> dict:
    """Get land details including crawl status."""
    try:
        headers = {"Authorization": f"Bearer {token}"}
        response = requests.get(
            f"{base_url}/api/v2/lands/{land_id}",
            headers=headers
        )
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Failed to get land details: {e}")
        return {}

def get_job_status(base_url: str, token: str, celery_task_id: str) -> dict:
    """Get Celery job status."""
    try:
        headers = {"Authorization": f"Bearer {token}"}
        response = requests.get(
            f"{base_url}/api/v1/jobs/{celery_task_id}",
            headers=headers
        )
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Failed to get job status: {e}")
        return {}

def get_land_crawl_jobs(base_url: str, token: str, land_id: int) -> list:
    """Get all crawl jobs for a land from database."""
    import asyncio
    # This would require database access - for now return empty
    return []

def main():
    parser = argparse.ArgumentParser(description="Get crawl job status and results")
    parser.add_argument("--base-url", default="http://localhost:8000", help="Base URL of the API")
    parser.add_argument("--username", default="admin@example.com", help="Username for authentication")
    parser.add_argument("--password", default="changeme", help="Password for authentication")
    parser.add_argument("--land-id", type=int, required=True, help="Land ID to check")
    parser.add_argument("--job-id", help="Specific Celery job ID to check (optional)")

    args = parser.parse_args()

    print(f"Authenticating as {args.username}...")
    token = get_token(args.base_url, args.username, args.password)
    if not token:
        print("Authentication failed. Exiting.")
        sys.exit(1)

    print(f"\n=== Land Details (ID: {args.land_id}) ===")
    land = get_land_details(args.base_url, token, args.land_id)

    if not land:
        print(f"Land {args.land_id} not found.")
        sys.exit(1)

    print(f"Name: {land.get('name')}")
    print(f"Description: {land.get('description')}")
    print(f"Crawl Status: {land.get('crawl_status')}")
    print(f"Total Expressions: {land.get('total_expressions')}")
    print(f"Total Domains: {land.get('total_domains')}")
    print(f"Last Crawl: {land.get('last_crawl')}")
    print(f"Start URLs: {len(land.get('start_urls', []))} URLs")
    print(f"Keywords: {len(land.get('words', []))} keywords")

    if args.job_id:
        print(f"\n=== Celery Job Status (ID: {args.job_id}) ===")
        job_status = get_job_status(args.base_url, token, args.job_id)

        if job_status:
            print(f"Job ID: {job_status.get('job_id')}")
            print(f"Status: {job_status.get('status')}")
            print(f"Progress: {job_status.get('progress')}%")
            print(f"Result: {job_status.get('result')}")
            if job_status.get('error_message'):
                print(f"Error: {job_status.get('error_message')}")

    print("\n=== Summary ===")
    if land.get('crawl_status') == 'completed':
        print(f"✓ Crawl completed successfully")
        print(f"  - {land.get('total_expressions', 0)} expressions collected")
        print(f"  - {land.get('total_domains', 0)} domains crawled")
    elif land.get('crawl_status') == 'running':
        print(f"⏳ Crawl in progress...")
    elif land.get('crawl_status') == 'failed':
        print(f"✗ Crawl failed")
    else:
        print(f"⏸ Crawl status: {land.get('crawl_status')}")

if __name__ == "__main__":
    main()
