import sqlite3
import logging
from typing import Optional
from .models import SearchResults
from .config import DB_PATH

logger = logging.getLogger(__name__)

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS employer_info (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employer_name TEXT UNIQUE NOT NULL,
            company_info TEXT,
            job_specific_info TEXT,
            last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()
    logger.info(f"Database initialized at {DB_PATH}")

def get_employer_info(employer_name: str) -> Optional[SearchResults]:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        'SELECT employer_name, company_info, job_specific_info FROM employer_info WHERE employer_name = ?',
        (employer_name,)
    )
    row = cursor.fetchone()
    conn.close()
    if row:
        return SearchResults(employer_name=row[0], company_info=row[1], job_specific_info=row[2])
    return None

def store_employer_info(search_results: SearchResults):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute('''
            INSERT INTO employer_info (employer_name, company_info, job_specific_info)
            VALUES (?, ?, ?)
            ON CONFLICT(employer_name) DO UPDATE SET
                company_info=excluded.company_info,
                job_specific_info=excluded.job_specific_info,
                last_updated=CURRENT_TIMESTAMP
        ''', (search_results.employer_name, search_results.company_info, search_results.job_specific_info))
        conn.commit()
        logger.info(f"Stored/Updated info for {search_results.employer_name}")
    except sqlite3.Error as e:
        logger.error(f"Database error: {e}")
    finally:
        conn.close()
