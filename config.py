import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# --- API Configuration ---
# Use Perplexity API
PERPLEXITY_API_KEY = os.getenv("PERPLEXITY_API_KEY") # Ensure this key is set in your .env
PERPLEXITY_MODEL_NAME = os.getenv("PERPLEXITY_MODEL_NAME", "llama-3.1-sonar-small-128k-online") # Default model, adjust as needed

# --- Database Configuration ---
DB_PATH = "employer_info.db" # Path to the SQLite database file

# --- File Output Configuration ---
OUTPUT_DIR = "generated_resumes" # Directory to save the final resumes

# --- Web Scraping Configuration ---
SELENIUM_HEADLESS = True # Set to False to see the browser window during scraping
# Add other selenium settings if needed, like proxy, user agent string, etc.