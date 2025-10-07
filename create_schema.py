# create_schema.py (Corrected column name mismatch)
import pandas as pd
import json
import os
import toml

from src.simulation_engine import GameSimulator
from supabase import create_client, Client

# --- Step 1: Load Secrets ---
try:
    secrets_path = os.path.join(os.path.dirname(__file__), '.streamlit', 'secrets.toml')
    secrets = toml.load(secrets_path)
    supabase_url = secrets['connections']['supabase']['SUPABASE_URL']
    supabase_key = secrets['connections']['supabase']['SUPABASE_KEY']
    print("✅ Successfully loaded Supabase credentials from secrets.toml")
except Exception as e:
    print(f"❌ Error loading secrets.toml: {e}")
    exit()

# --- Step 2: Create a Supabase Client ---
try:
    supabase: Client = create_client(supabase_url, supabase_key)
    print("✅ Supabase client created.")
except Exception as e:
    print(f"❌ Error creating Supabase client: {e}")
    exit()

# --- Step 3: Define Self-Contained Functions to Get Data ---
def get_roster_data_standalone(client: Client, team_id: int):
    """Standalone function to get the full player roster."""
    try:
        response = client.rpc('get_full_player_data', {'team_id_param': int(team_id)}).execute()
        df = pd.DataFrame(response.data)
        
        # --- THE FIX IS HERE ---
        # Rename the 'full_name' column to 'name' to match the PlayerProfile dataclass
        if 'full_name' in df.columns:
            df.rename(columns={'full_name': 'name'}, inplace=True)
            
        return df
    except Exception as e:
        print(f"❌ Error fetching roster for team {team_id}: {e}")
        return pd.DataFrame()

def get_goalie_data_standalone(client: Client, team_id: int):
    """Standalone function to get all goalies for a team and select one."""
    try:
        response = client.rpc('get_full_goalie_data', {'team_id_param': int(team_id)}).execute()
        goalie_df = pd.DataFrame(response.data)
        if not goalie_df.empty:
            return goalie_df.iloc[0].to_dict()
        else:
            print(f"⚠️ No goalies found for team {team_id}.")
            return None
    except Exception as e:
        print(f"❌ Error fetching goalies for team {team_id}: {e}")
        return None

# --- Step 4: Fetch the Data ---
print("Fetching sample team data from Supabase...")
home_lineup = get_roster_data_standalone(supabase, 1)
home_goalie = get_goalie_data_standalone(supabase, 1)
away_lineup = get_roster_data_standalone(supabase, 2)
away_goalie = get_goalie_data_standalone(supabase, 2)

if home_lineup.empty or away_lineup.empty or not home_goalie or not away_goalie:
    print("❌ Failed to fetch necessary data. Aborting schema creation.")
    exit()

home_team_data = { "lineup": home_lineup, "goalie": home_goalie, "coach": {} }
away_team_data = { "lineup": away_lineup, "goalie": away_goalie, "coach": {} }
print("✅ Sample data fetched.")

# --- Step 5: Run the Simulation and Save the Schema ---
print("Running one-time simulation to generate schema...")
sim = GameSimulator(home_team_data, away_team_data)
results = sim.run_simulation()

schema = {
    'home_players': list(results['home_players'].columns),
    'away_players': list(results['away_players'].columns),
    'home_goalie': list(results['home_goalie'].columns),
    'away_goalie': list(results['away_goalie'].columns)
}
os.makedirs('schemas', exist_ok=True)
with open('schemas/dataframe_schema.json', 'w') as f:
    json.dump(schema, f, indent=4)

print("✅ Schema saved successfully to schemas/dataframe_schema.json")