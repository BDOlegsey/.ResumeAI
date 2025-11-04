import os
from dotenv import load_dotenv

load_dotenv()

PPLX_API_KEY = os.getenv("PPLX_API_KEY", "")
DB_PATH = "employer_info.db"
