"""SQLite storage and CSV export for mall data.

Provides functions to persist districts and malls to SQLite database
and export data to CSV files.
"""

from __future__ import annotations

import csv
import logging
import sqlite3
from pathlib import Path
from typing import Iterator, List, Optional

from mall_crawler.config import DB_PATH, OUTPUT_CSV
from mall_crawler.models import District, MallPoi

logger = logging.getLogger(__name__)


def init_database(db_path: Optional[Path] = None) -> sqlite3.Connection:
    """Initialize the SQLite database and create tables.
    
    Args:
        db_path: Path to the database file. Defaults to config.DB_PATH.
        
    Returns:
        SQLite connection object.
    """
    if db_path is None:
        db_path = DB_PATH
    
    # Ensure parent directory exists
    db_path.parent.mkdir(parents=True, exist_ok=True)
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Create districts table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS districts (
            adcode TEXT PRIMARY KEY,
            country TEXT NOT NULL,
            province_name TEXT NOT NULL,
            city_name TEXT NOT NULL,
            district_name TEXT NOT NULL,
            citycode TEXT,
            center_lon REAL,
            center_lat REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Create malls table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS malls (
            poi_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            type TEXT,
            typecode TEXT,
            lon REAL NOT NULL,
            lat REAL NOT NULL,
            address TEXT,
            province_name TEXT,
            city_name TEXT,
            district_name TEXT,
            pcode TEXT,
            citycode TEXT,
            adcode TEXT,
            business_area TEXT,
            tel TEXT,
            source_district_adcode TEXT,
            name_keywords TEXT,
            is_potential_trash_mall INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Create indices for common queries
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_malls_adcode ON malls(adcode)
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_malls_province ON malls(province_name)
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_malls_city ON malls(city_name)
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_malls_trash ON malls(is_potential_trash_mall)
    """)
    
    conn.commit()
    logger.info(f"Database initialized at {db_path}")
    
    return conn


def upsert_districts(conn: sqlite3.Connection, districts: List[District]) -> int:
    """Insert or update districts in the database.
    
    Args:
        conn: SQLite connection.
        districts: List of District objects to upsert.
        
    Returns:
        Number of districts upserted.
    """
    cursor = conn.cursor()
    
    for d in districts:
        cursor.execute("""
            INSERT INTO districts (
                adcode, country, province_name, city_name, district_name,
                citycode, center_lon, center_lat
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(adcode) DO UPDATE SET
                country = excluded.country,
                province_name = excluded.province_name,
                city_name = excluded.city_name,
                district_name = excluded.district_name,
                citycode = excluded.citycode,
                center_lon = excluded.center_lon,
                center_lat = excluded.center_lat
        """, (
            d.adcode, d.country, d.province_name, d.city_name, d.district_name,
            d.citycode, d.center_lon, d.center_lat
        ))
    
    conn.commit()
    logger.info(f"Upserted {len(districts)} districts")
    return len(districts)


def upsert_mall(conn: sqlite3.Connection, mall: MallPoi) -> bool:
    """Insert or update a single mall in the database.
    
    Args:
        conn: SQLite connection.
        mall: MallPoi object to upsert.
        
    Returns:
        True if the operation was successful.
    """
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            INSERT INTO malls (
                poi_id, name, type, typecode, lon, lat, address,
                province_name, city_name, district_name,
                pcode, citycode, adcode, business_area, tel,
                source_district_adcode, name_keywords, is_potential_trash_mall
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(poi_id) DO UPDATE SET
                name = excluded.name,
                type = excluded.type,
                typecode = excluded.typecode,
                lon = excluded.lon,
                lat = excluded.lat,
                address = excluded.address,
                province_name = excluded.province_name,
                city_name = excluded.city_name,
                district_name = excluded.district_name,
                pcode = excluded.pcode,
                citycode = excluded.citycode,
                adcode = excluded.adcode,
                business_area = excluded.business_area,
                tel = excluded.tel,
                source_district_adcode = excluded.source_district_adcode,
                name_keywords = excluded.name_keywords,
                is_potential_trash_mall = excluded.is_potential_trash_mall,
                updated_at = CURRENT_TIMESTAMP
        """, (
            mall.poi_id, mall.name, mall.type, mall.typecode,
            mall.lon, mall.lat, mall.address,
            mall.province_name, mall.city_name, mall.district_name,
            mall.pcode, mall.citycode, mall.adcode,
            mall.business_area, mall.tel, mall.source_district_adcode,
            mall.name_keywords, 1 if mall.is_potential_trash_mall else 0
        ))
        conn.commit()
        return True
        
    except sqlite3.Error as e:
        logger.error(f"Failed to upsert mall {mall.poi_id}: {e}")
        return False


def upsert_malls_batch(conn: sqlite3.Connection, malls: List[MallPoi]) -> int:
    """Insert or update multiple malls in the database.
    
    Args:
        conn: SQLite connection.
        malls: List of MallPoi objects to upsert.
        
    Returns:
        Number of malls successfully upserted.
    """
    count = 0
    for mall in malls:
        if upsert_mall(conn, mall):
            count += 1
    return count


def get_mall_count(conn: sqlite3.Connection) -> int:
    """Get total number of malls in the database.
    
    Args:
        conn: SQLite connection.
        
    Returns:
        Total mall count.
    """
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM malls")
    return cursor.fetchone()[0]


def get_all_malls(conn: sqlite3.Connection) -> Iterator[dict]:
    """Get all malls from the database.
    
    Args:
        conn: SQLite connection.
        
    Yields:
        Dictionary representation of each mall.
    """
    cursor = conn.cursor()
    cursor.execute("""
        SELECT 
            poi_id, name, type, typecode, lon, lat, address,
            province_name, city_name, district_name,
            pcode, citycode, adcode, business_area, tel,
            source_district_adcode, name_keywords, is_potential_trash_mall
        FROM malls
        ORDER BY province_name, city_name, district_name, name
    """)
    
    columns = [
        "poi_id", "name", "type", "typecode", "lon", "lat", "address",
        "province_name", "city_name", "district_name",
        "pcode", "citycode", "adcode", "business_area", "tel",
        "source_district_adcode", "name_keywords", "is_potential_trash_mall"
    ]
    
    for row in cursor:
        yield dict(zip(columns, row))


def export_malls_to_csv(conn: sqlite3.Connection, output_path: Optional[Path] = None) -> Path:
    """Export all malls to a CSV file.
    
    Args:
        conn: SQLite connection.
        output_path: Path for the CSV file. Defaults to config.OUTPUT_CSV.
        
    Returns:
        Path to the exported CSV file.
    """
    if output_path is None:
        output_path = OUTPUT_CSV
    
    # Ensure parent directory exists
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    # CSV header
    fieldnames = [
        "poi_id", "name", "type", "typecode", "lon", "lat", "address",
        "province_name", "city_name", "district_name",
        "pcode", "citycode", "adcode", "business_area", "tel",
        "source_district_adcode", "name_keywords", "is_potential_trash_mall"
    ]
    
    count = 0
    with open(output_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        
        for mall in get_all_malls(conn):
            writer.writerow(mall)
            count += 1
    
    logger.info(f"Exported {count} malls to {output_path}")
    return output_path


def get_processed_district_adcodes(conn: sqlite3.Connection) -> set:
    """Get set of district adcodes that have already been processed.
    
    Useful for resuming an interrupted crawl.
    
    Args:
        conn: SQLite connection.
        
    Returns:
        Set of adcodes that have malls in the database.
    """
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT source_district_adcode FROM malls")
    return {row[0] for row in cursor.fetchall()}




