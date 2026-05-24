import csv
import logging
from pathlib import Path
from typing import Any

from backend.app.config import settings
from backend.app.repositories.database import connect

logger = logging.getLogger(__name__)

TRANSPORT_DATA_DIR = Path("backend/data/trasport")

def import_transport_data():
    """Imports GTFS data from .txt files in backend/data/trasport into PostgreSQL."""
    files_to_import = [
        ("agency.txt", "transport_agency"),
        ("stops.txt", "transport_stops"),
        ("routes.txt", "transport_routes"),
        ("calendar.txt", "transport_calendar"),
        ("calendar_dates.txt", "transport_calendar_dates"),
        ("trips.txt", "transport_trips"),
        ("stop_times.txt", "transport_stop_times"),
    ]

    with connect() as conn:
        with conn.cursor() as cursor:
            for filename, table_name in files_to_import:
                file_path = TRANSPORT_DATA_DIR / filename
                if not file_path.exists():
                    logger.warning(f"Transport file {file_path} not found, skipping.")
                    continue

                logger.info(f"Importing {filename} into {table_name}...")
                
                # Clear table first to avoid conflicts on re-import
                # We do it in reverse order of dependencies or just disable FK checks
                # For simplicity, we can use TRUNCATE CASCADE if we are sure
                cursor.execute(f"TRUNCATE TABLE {table_name} CASCADE")

                with open(file_path, mode='r', encoding='utf-8-sig') as f:
                    reader = csv.DictReader(f)
                    columns = reader.fieldnames
                    if not columns:
                        continue
                    
                    # Filter columns to match our schema (just in case GTFS has extra)
                    cursor.execute(f"SELECT column_name FROM information_schema.columns WHERE table_name = '{table_name}'")
                    db_columns = {row['column_name'] for row in cursor.fetchall()}
                    valid_columns = [col for col in columns if col in db_columns]
                    
                    placeholders = ", ".join(["%s"] * len(valid_columns))
                    insert_query = f"INSERT INTO {table_name} ({', '.join(valid_columns)}) VALUES ({placeholders})"
                    
                    batch = []
                    for row in reader:
                        # Convert empty strings to None for DB compatibility
                        processed_row = [row[col] if row[col] != "" else None for col in valid_columns]
                        batch.append(tuple(processed_row))
                        if len(batch) >= 1000:
                            cursor.executemany(insert_query, batch)
                            batch = []
                    if batch:
                        cursor.executemany(insert_query, batch)
                
                conn.commit()
                logger.info(f"Successfully imported {filename}.")

def search_transport_info(query_text: str) -> list[dict[str, Any]]:
    """
    Search for transport information based on query text.
    This is a placeholder for more complex join queries.
    """
    # Example: search for stop names
    search_query = """
        SELECT stop_id, stop_name, stop_lat, stop_lon
        FROM transport_stops
        WHERE stop_name ILIKE %s
        LIMIT 5
    """
    with connect() as conn:
        with conn.cursor() as cursor:
            cursor.execute(search_query, (f"%{query_text}%",))
            return list(cursor.fetchall())

def get_stop_times_by_stop_name(stop_name: str, current_time: str = "00:00:00") -> list[dict[str, Any]]:
    """
    Get upcoming stop times for a specific stop name, starting from current_time.
    """
    query = """
        SELECT 
            r.route_short_name, 
            r.route_long_name, 
            st.arrival_time, 
            st.departure_time,
            t.trip_headsign
        FROM transport_stops s
        JOIN transport_stop_times st ON s.stop_id = st.stop_id
        JOIN transport_trips t ON st.trip_id = t.trip_id
        JOIN transport_routes r ON t.route_id = r.route_id
        WHERE s.stop_name ILIKE %s AND st.departure_time >= %s
        ORDER BY st.departure_time
        LIMIT 10
    """
    with connect() as conn:
        with conn.cursor() as cursor:
            cursor.execute(query, (f"%{stop_name}%", current_time))
            return list(cursor.fetchall())

def query_transport(sql_query: str, params: tuple = None) -> list[dict[str, Any]]:
    """Executes a custom SQL query on transport tables."""
    with connect() as conn:
        with conn.cursor() as cursor:
            cursor.execute(sql_query, params)
            return list(cursor.fetchall())
