#!/usr/bin/env python3
"""Main entry point for the AMap mall crawler.

This script orchestrates the crawling pipeline:
1. Load configuration and AMap API key
2. Fetch all districts in China (with caching)
3. For each district, fetch shopping mall POIs
4. Persist results to SQLite database
5. Export all malls to CSV
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from datetime import datetime
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from mall_crawler.amap_client import AmapClient
from mall_crawler.config import DB_PATH, OUTPUT_CSV, get_amap_key
from mall_crawler.storage import (
    export_malls_to_csv,
    get_mall_count,
    get_processed_district_adcodes,
    init_database,
    upsert_districts,
    upsert_mall,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def run_crawler(
    resume: bool = True,
    skip_export: bool = False,
    limit_districts: int = 0,
) -> None:
    """Run the mall crawler pipeline.
    
    Args:
        resume: Whether to resume from previously processed districts.
        skip_export: Whether to skip CSV export at the end.
        limit_districts: Limit the number of districts to process (0 = all).
    """
    start_time = time.time()
    
    # Load API key
    logger.info("Loading AMap API key...")
    api_key = get_amap_key()
    logger.info("API key loaded successfully")
    
    # Initialize database
    logger.info(f"Initializing database at {DB_PATH}...")
    conn = init_database()
    
    # Initialize API client
    client = AmapClient(api_key)
    
    # Fetch all districts
    logger.info("Fetching all districts in China...")
    districts = client.fetch_all_districts(use_cache=True)
    logger.info(f"Found {len(districts)} districts")
    
    # Save districts to database
    upsert_districts(conn, districts)
    
    # Get already processed districts for resume
    processed_adcodes = set()
    if resume:
        processed_adcodes = get_processed_district_adcodes(conn)
        if processed_adcodes:
            logger.info(f"Resuming: {len(processed_adcodes)} districts already processed")
    
    # Apply limit if specified
    districts_to_process = districts
    if limit_districts > 0:
        districts_to_process = districts[:limit_districts]
        logger.info(f"Limited to first {limit_districts} districts")
    
    # Process each district
    total_districts = len(districts_to_process)
    total_malls = 0
    processed_count = 0
    skipped_count = 0
    error_count = 0
    
    logger.info(f"Starting to crawl malls from {total_districts} districts...")
    
    for idx, district in enumerate(districts_to_process, 1):
        # Skip if already processed
        if district.adcode in processed_adcodes:
            skipped_count += 1
            continue
        
        try:
            mall_count = 0
            for mall in client.fetch_malls_by_district(district):
                upsert_mall(conn, mall)
                mall_count += 1
                total_malls += 1
            
            processed_count += 1
            
            # Log progress every 50 districts or when malls are found
            if processed_count % 50 == 0 or mall_count > 0:
                logger.info(
                    f"[{idx}/{total_districts}] {district.province_name}/{district.city_name}/"
                    f"{district.district_name} ({district.adcode}): {mall_count} malls, "
                    f"total: {get_mall_count(conn)}"
                )
                
        except KeyboardInterrupt:
            logger.warning("Interrupted by user")
            break
            
        except Exception as e:
            error_count += 1
            logger.error(f"Error processing district {district}: {e}")
            continue
    
    # Summary
    elapsed = time.time() - start_time
    stats = client.get_stats()
    
    logger.info("=" * 60)
    logger.info("Crawl completed!")
    logger.info(f"  Total districts: {total_districts}")
    logger.info(f"  Processed: {processed_count}")
    logger.info(f"  Skipped (already done): {skipped_count}")
    logger.info(f"  Errors: {error_count}")
    logger.info(f"  Total malls fetched: {total_malls}")
    logger.info(f"  Total malls in DB: {get_mall_count(conn)}")
    logger.info(f"  API requests: {stats['request_count']}")
    logger.info(f"  API errors: {stats['error_count']}")
    logger.info(f"  Time elapsed: {elapsed:.1f}s ({elapsed/60:.1f}min)")
    logger.info("=" * 60)
    
    # Export to CSV
    if not skip_export:
        logger.info("Exporting malls to CSV...")
        csv_path = export_malls_to_csv(conn)
        logger.info(f"CSV exported to: {csv_path}")
    
    conn.close()


def main():
    """Parse arguments and run the crawler."""
    parser = argparse.ArgumentParser(
        description="Crawl shopping malls in China using AMap API"
    )
    parser.add_argument(
        "--no-resume",
        action="store_true",
        help="Don't resume from previous run, start fresh",
    )
    parser.add_argument(
        "--skip-export",
        action="store_true",
        help="Skip CSV export at the end",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Limit number of districts to process (for testing)",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging",
    )
    
    args = parser.parse_args()
    
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
    
    try:
        run_crawler(
            resume=not args.no_resume,
            skip_export=args.skip_export,
            limit_districts=args.limit,
        )
    except Exception as e:
        logger.error(f"Crawler failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()




