from pathlib import Path
from dotenv import load_dotenv

# Load .env from backend/ directory
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(env_path)
