import sqlite3
from config import DB_PATH
from models import SearchResults
import logging
from typing import Optional # Добавлен импорт Optional

logger = logging.getLogger(__name__)

def init_db():
    """Initializes the SQLite database and creates the table if it doesn't exist."""
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
    """Retrieves employer information from the database."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT employer_name, company_info, job_specific_info FROM employer_info WHERE employer_name = ?', (employer_name,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return SearchResults(employer_name=row[0], company_info=row[1], job_specific_info=row[2])
    return None

def store_employer_info(search_results: SearchResults):
    """Stores or updates employer information in the database."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute('''
            INSERT OR REPLACE INTO employer_info (employer_name, company_info, job_specific_info)
            VALUES (?, ?, ?)
        ''', (search_results.employer_name, search_results.company_info, search_results.job_specific_info))
        conn.commit()
        logger.info(f"Stored/Updated info for {search_results.employer_name} in database.")
    except sqlite3.Error as e:
        logger.error(f"Database error while storing info for {search_results.employer_name}: {e}")
    finally:
        conn.close()