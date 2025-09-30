import os
import sys

# Add the src directory to Python path for absolute imports FIRST
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv

from src.web.app_factory import create_app

# Load environment variables from .env file
load_dotenv()


CONFIG_PATH = "/config/app_state.yaml"

# Create the Flask app
app = create_app()

if __name__ == "__main__":
    port = int(os.environ.get("FLASK_RUN_PORT", 5001))
    app.run(host="0.0.0.0", port=port, debug=False)
