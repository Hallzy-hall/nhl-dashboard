import os
import sys
import time
import pandas as pd
import toml
from typing import Dict, Any
import numpy as np
import requests # <-- ADDED for making the API call directly

# --- Robust Pathing ---
try:
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = script_dir
    sys.path.insert(0, project_root)
except NameError:
    script_dir = os.getcwd()
    sys.path.insert(0, script_dir)

# --- ADVANCED STREAMLIT MOCKING ---
class MagicSecrets:
    def __init__(self, secrets_dict):
        self._secrets = secrets_dict
    def __getattr__(self, name):
        if name in self._secrets:
            value = self._secrets[name]
            if isinstance(value, dict):
                return MagicSecrets(value)
            return value
        raise AttributeError(f"'MagicSecrets' object has no attribute '{name}'")

class MockStreamlit:
    def __init__(self, secrets_dict: Dict[str, Any]):
        self.secrets = MagicSecrets(secrets_dict)
    def cache_data(self, func=None, **kwargs):
        def decorator(f):
            def wrapper(*args, **kwargs):
                return f(*args, **kwargs)
            return wrapper
        if func: return decorator(func)
        return decorator
    def __getattr__(self, name):
        if name != "secrets":
            return lambda *args, **kwargs: print(f"Mocked st.{name}:", *args)
        return self.secrets

# --- FIX: Integrated Cloud Engine Logic ---
def run_cloud_simulations(
    num_sims: int,
    home_team_data: Dict[str, Any],
    away_team_data: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Triggers the remote simulation on a Supabase Edge Function and returns the results.
    This logic is now self-contained within the test harness.
    """
    edge_function_url = os.getenv("SUPABASE_EDGE_FUNCTION_URL")
    anon_key = os.getenv("SUPABASE_ANON_KEY")

    if not edge_function_url or not anon_key:
        raise ConnectionError("Supabase environment variables are not set.")

    # Prepare the JSON Payload
    payload = {
        "numSims": num_sims,
        "homeTeamData": {
            "lineup": home_team_data["lineup"].to_dict(orient="records"),
            "coach": home_team_data["coach"], "goalie": home_team_data["goalie"]
        },
        "awayTeamData": {
            "lineup": away_team_data["lineup"].to_dict(orient="records"),
            "coach": away_team_data["coach"], "goalie": away_team_data["goalie"]
        }
    }

    # Construct the required headers for Supabase functions
    headers = {
        "Authorization": f"Bearer {anon_key}",
        "apikey": anon_key, # Best practice to include both
        "Content-Type": "application/json"
    }
    
    print("Sending simulation request to the cloud...")
    response = requests.post(edge_function_url, json=payload, headers=headers, timeout=300)

    if response.status_code != 200:
        raise Exception(f"Cloud function failed with status {response.status_code}: {response.text}")

    return response.json()

# --- Main Test Script ---
def main():
    """Main function to test the local Supabase Edge Function."""
    try:
        secrets_path = os.path.join(project_root, '.streamlit', 'secrets.toml')
        with open(secrets_path, 'r') as f: secrets = toml.load(f)
        supabase_creds = secrets['connections']['supabase']
        db_key = supabase_creds['SUPABASE_KEY']
        anon_key = supabase_creds['SUPABASE_ANON_KEY']
        
        os.environ['SUPABASE_URL'] = supabase_creds['SUPABASE_URL']
        os.environ['SUPABASE_KEY'] = db_key
        os.environ['SUPABASE_EDGE_FUNCTION_URL'] = "http://127.0.0.1:54321/functions/v1/run-simulation"
        os.environ['SUPABASE_ANON_KEY'] = anon_key
        
    except (FileNotFoundError, KeyError) as e:
        print(f"\n---! CONFIGURATION ERROR !---")
        print(f"Could not find or parse Supabase credentials in `.streamlit/secrets.toml`: {e}")
        sys.exit(1)

    sys.modules['streamlit'] = MockStreamlit(secrets)
    
    try:
        from utils.db_queries import get_simulation_roster, get_coach_by_team_id, get_full_goalie_data
        print("Successfully imported project modules.")
    except ImportError as e:
        print(f"\n---! IMPORT ERROR !--- \n{e}")
        sys.exit(1)

    # --- Data Fetching ---
    HOME_TEAM_ID, AWAY_TEAM_ID, NUM_SIMS = 23, 24, 1000
    try:
        print("Fetching data...")
        home_lineup_df = get_simulation_roster(team_id=HOME_TEAM_ID).replace({np.nan: None})
        away_lineup_df = get_simulation_roster(team_id=AWAY_TEAM_ID).replace({np.nan: None})
        home_coach = get_coach_by_team_id(team_id=HOME_TEAM_ID)
        away_coach = get_coach_by_team_id(team_id=AWAY_TEAM_ID)
        home_goalie = get_full_goalie_data(team_id=HOME_TEAM_ID).iloc[0].replace({np.nan: None}).to_dict()
        away_goalie = get_full_goalie_data(team_id=AWAY_TEAM_ID).iloc[0].replace({np.nan: None}).to_dict()

        home_team_data = {"lineup": home_lineup_df, "coach": home_coach, "goalie": home_goalie}
        away_team_data = {"lineup": away_lineup_df, "coach": away_coach, "goalie": away_goalie}
        print("Data fetching complete.")
    except Exception as e:
        print(f"\n---! DATABASE ERROR !---\n{e}")
        sys.exit(1)

    # --- Simulation Execution ---
    print(f"\nSending {NUM_SIMS} simulations to LOCAL cloud function...")
    start_time = time.time()
    results = run_cloud_simulations(NUM_SIMS, home_team_data, away_team_data)
    end_time = time.time()
    print(f"Total execution time: {end_time - start_time:.4f} seconds")

    # --- Output Validation ---
    print("\n--- Output Validation ---")
    if 'all_game_scores' in results:
        scores = pd.DataFrame(results['all_game_scores'], columns=['home', 'away'])
        print(f"Average Score: {scores['home'].mean():.2f} - {scores['away'].mean():.2f}")
    else:
        print("Validation Failed: No scores returned.")

if __name__ == "__main__":
    main()

