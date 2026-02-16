#!/usr/bin/env python3
"""
Script to delete all lands and their associated data.
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

def get_all_lands(base_url: str, token: str) -> list:
    """Retrieve all lands."""
    try:
        headers = {"Authorization": f"Bearer {token}"}
        all_lands = []
        page = 1
        page_size = 100

        while True:
            response = requests.get(
                f"{base_url}/api/v2/lands",
                params={"page": page, "page_size": page_size},
                headers=headers
            )
            response.raise_for_status()
            data = response.json()

            items = data.get("items", [])
            all_lands.extend(items)

            if not data.get("has_next", False):
                break

            page += 1

        return all_lands
    except Exception as e:
        print(f"Failed to retrieve lands: {e}")
        print(f"Response: {response.text if 'response' in locals() else 'No response'}")
        return []

def delete_land(base_url: str, token: str, land_id: int) -> bool:
    """Delete a single land."""
    try:
        headers = {"Authorization": f"Bearer {token}"}
        response = requests.delete(
            f"{base_url}/api/v2/lands/{land_id}",
            headers=headers
        )
        response.raise_for_status()
        return True
    except Exception as e:
        print(f"Failed to delete land {land_id}: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(description="Delete all lands from the database")
    parser.add_argument("--base-url", default="http://localhost:8000", help="Base URL of the API")
    parser.add_argument("--username", default="admin@example.com", help="Username for authentication")
    parser.add_argument("--password", default="changeme", help="Password for authentication")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be deleted without actually deleting")

    args = parser.parse_args()

    print(f"Authenticating as {args.username}...")
    token = get_token(args.base_url, args.username, args.password)
    if not token:
        print("Authentication failed. Exiting.")
        sys.exit(1)

    print("Retrieving all lands...")
    lands = get_all_lands(args.base_url, token)

    if not lands:
        print("No lands found.")
        return

    print(f"\nFound {len(lands)} land(s) to delete:")
    for land in lands:
        print(f"  - ID: {land['id']}, Name: {land['name']}")

    if args.dry_run:
        print("\n[DRY RUN] No lands were deleted.")
        return

    print(f"\nDeleting {len(lands)} land(s)...")
    deleted_count = 0
    failed_count = 0

    for land in lands:
        land_id = land["id"]
        land_name = land["name"]
        print(f"Deleting land {land_id} ({land_name})...", end=" ")

        if delete_land(args.base_url, token, land_id):
            print("✓ Deleted")
            deleted_count += 1
        else:
            print("✗ Failed")
            failed_count += 1

    print(f"\n=== Summary ===")
    print(f"Successfully deleted: {deleted_count}")
    print(f"Failed to delete: {failed_count}")
    print(f"Total: {len(lands)}")

if __name__ == "__main__":
    main()
