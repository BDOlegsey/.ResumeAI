# config.py
import os
from dotenv import load_dotenv

load_dotenv()

# Perplexity API (ключ читается ChatPerplexity из PPLX_API_KEY)
PPLX_API_KEY = os.getenv("PPLX_API_KEY", "")

# База данных
DB_PATH = "employer_info.db"

# Папка вывода
OUTPUT_DIR = "generated_resumes"
