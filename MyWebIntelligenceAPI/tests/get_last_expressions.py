
import argparse
import json
import os
import sys
import asyncio
from datetime import datetime
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy import text
import warnings

# Suppress SQLAlchemy 2.0 warnings for cleaner output
warnings.filterwarnings("ignore", category=DeprecationWarning)

# Add project root to the Python path to allow imports from the 'app' module
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, PROJECT_ROOT)

try:
    from app.config import settings
except ImportError:
    print("Error: Could not import settings from app.config.", file=sys.stderr)
    print("Please ensure that the script is run from the project's root directory or that the PYTHONPATH is set correctly.", file=sys.stderr)
    sys.exit(1)

async def get_last_expressions(db_uri: str, land_id: int, limit: int):
    """
    Connects to the database asynchronously and fetches the last N approved expressions for a given land.

    Args:
        db_uri: The asynchronous database connection string.
        land_id: The ID of the land to fetch expressions from.
        limit: The number of recent expressions to fetch.

    Returns:
        A list of dictionaries, where each dictionary represents an expression.
    """
    if not db_uri:
        raise ValueError("Database URI not found. Please check your app.config.settings.")

    engine = create_async_engine(db_uri)
    AsyncSessionLocal = async_sessionmaker(autocommit=False, autoflush=False, bind=engine)

    async with AsyncSessionLocal() as db:
        # Query now filters for approved_at NOT NULL and orders by it.
        query = text(f"""
            SELECT *
            FROM expressions
            WHERE land_id = :land_id AND approved_at IS NOT NULL
            ORDER BY approved_at DESC
            LIMIT :limit
        """)

        result = await db.execute(query, {"land_id": land_id, "limit": limit})
        
        columns = result.keys()
        expressions_data = [dict(zip(columns, row)) for row in result.fetchall()]

        # Convert non-serializable types (like datetime) to strings for JSON output
        for item in expressions_data:
            for key, value in item.items():
                if hasattr(value, 'isoformat'):  # Handles datetime, date objects
                    item[key] = value.isoformat()
        
        return expressions_data

async def main():
    """
    Main async function to parse arguments, fetch expressions, and write them to a timestamped JSON file.
    """
    parser = argparse.ArgumentParser(
        description="Fetch the last X approved expressions for a given land ID and save them to a JSON file.",
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("land_id", type=int, help="The ID of the land (Y).")
    parser.add_argument(
        "limit",
        type=int,
        nargs='?',
        default=10,
        help="The number of recent expressions to fetch (X). Defaults to 10."
    )
    
    args = parser.parse_args()

    try:
        db_uri = str(settings.DATABASE_URL)
        expressions = await get_last_expressions(db_uri, args.land_id, args.limit)
        
        if not expressions:
            print(f"No approved expressions found for land_id {args.land_id}.", file=sys.stderr)
        else:
            timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
            filename = f"expressions{timestamp}.json"
            
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(expressions, f, indent=2, ensure_ascii=False)
            
            print(f"Successfully wrote {len(expressions)} expressions to '{filename}'.")

    except Exception as e:
        print(f"An error occurred: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
