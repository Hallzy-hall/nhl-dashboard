import sys
import os

# This line adds the parent directory (your main project folder) to the Python path.
# It allows this script to find and import from your 'utils' folder.
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from utils.api_queries import update_schedule_in_db

def main():
    """
    Main function to trigger the NHL schedule update process.
    """
    print("--- Starting nightly NHL schedule sync ---")
    update_schedule_in_db()
    print("--- NHL schedule sync complete ---")

if __name__ == "__main__":
    main()