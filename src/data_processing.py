import streamlit as st
import pandas as pd
import json
import numpy as np
import datetime
from supabase import create_client, Client
from .calculations import calculate_toi_distribution
from .definitions import all_definitions
from utils.db_queries import get_simulation_roster

# ==============================================================================
# --- DATABASE UTILITY FUNCTIONS ---
# ==============================================================================

# This will be populated by init_connection()
supabase: Client = None

def init_connection():
    """Initializes the connection to the Supabase database."""
    global supabase
    if supabase is None:
        try:
            url = st.secrets["connections"]["supabase"]["SUPABASE_URL"]
            key = st.secrets["connections"]["supabase"]["SUPABASE_KEY"]
            supabase = create_client(url, key)
        except Exception as e:
            st.error(f"Failed to connect to Supabase. Please check your secrets.toml file. Error: {e}")
            supabase = None # Ensure supabase is None if connection fails
    return supabase

class CustomEncoder(json.JSONEncoder):
    """
    Custom JSON encoder to handle special data types like NumPy's and pandas DataFrames.
    """
    def default(self, obj):
        if isinstance(obj, np.integer):
            return int(obj)
        if isinstance(obj, np.floating):
            return float(obj)
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        if isinstance(obj, pd.DataFrame):
            return obj.to_dict(orient='records')
        return super(CustomEncoder, self).default(obj)

def save_simulation_results(game_id: int, results_data: dict):
    """Saves or updates simulation results for a given game_id in the database."""
    if supabase is None:
        init_connection()
    if supabase is None:
        st.error("Database connection not available. Cannot save results.")
        return

    try:
        # Serialize the dictionary to a JSON string using our custom encoder
        json_string = json.dumps(results_data, cls=CustomEncoder)
        
        timestamp = datetime.datetime.utcnow().isoformat()
        
        supabase.table('simulation_results').upsert({
            'game_id': game_id,
            'results_data': json_string,
            'simulation_timestamp': timestamp
        }).execute()
        st.toast(f"Simulation results saved successfully for game {game_id}!", icon="✅")
    except Exception as e:
        st.error(f"An error occurred while saving simulation results: {e}")

def load_simulation_results(game_id: int):
    """
    Loads simulation results for a given game_id from the database and
    reconstructs necessary DataFrames.
    """
    if supabase is None:
        init_connection()
    if supabase is None:
        st.error("Database connection not available. Cannot load results.")
        return None

    try:
        response = supabase.table('simulation_results').select('results_data').eq('game_id', game_id).single().execute()
        if response.data and 'results_data' in response.data:
            results_data = response.data['results_data']
            
            parsed_data = None
            if isinstance(results_data, dict):
                parsed_data = results_data
            elif isinstance(results_data, str):
                parsed_data = json.loads(results_data)

            # --- FIX: Convert lists back into DataFrames after loading ---
            if parsed_data:
                if 'raw_data' in parsed_data and parsed_data['raw_data']:
                    raw_data = parsed_data['raw_data']
                    if 'home_players' in raw_data and isinstance(raw_data.get('home_players'), list):
                        raw_data['home_players'] = pd.DataFrame(raw_data['home_players'])
                    if 'away_players' in raw_data and isinstance(raw_data.get('away_players'), list):
                        raw_data['away_players'] = pd.DataFrame(raw_data['away_players'])
                return parsed_data
            # --- END FIX ---
                
        return None
    except Exception as e:
        return None

# ==============================================================================
# --- DATA PROCESSING FUNCTIONS ---
# ==============================================================================

def structure_data_for_sim():
    """Placeholder for old Lineup Builder functionality."""
    pass

def run_toi_calculation(pim_for: int, pim_against: int):
    """
    Placeholder for old Lineup Builder TOI calculation.
    This function is likely deprecated but is kept to prevent import errors
    from the lineup_builder_page.py file.
    """
    st.warning("`run_toi_calculation` is a deprecated function.")
    return {}

def structure_dashboard_data_for_sim(team_type: str):
    """
    Prepares the roster and all player ratings for the main dashboard simulation
    by calling a single database function.
    """
    team_data = st.session_state.dashboard_data[team_type]
    
    team_id = team_data.get('team_id')
    if not team_id:
        return []

    full_roster_data = get_simulation_roster(int(team_id))

    if full_roster_data.empty:
        st.warning(f"Could not fetch complete roster for {team_type} team.")
        return []

    manual_ratings_all = team_data.get('manual_ratings', {})
    player_roles = {}
    
    for line_name, positions in all_definitions.items():
        for pos in positions:
            widget_key = f"{team_type}_{line_name}_{pos}_name"
            player_name = st.session_state.get(widget_key)
            if player_name:
                if player_name not in player_roles: player_roles[player_name] = []
                if line_name.startswith("Line"): role_prefix = "F" + line_name.split(" ")[1]
                elif line_name.startswith("Pair"): role_prefix = "D" + line_name.split(" ")[1]
                else:
                    parts = line_name.split(" ")
                    role_prefix = parts[0] + parts[2]
                player_roles[player_name].append(role_prefix)

    roster_for_sim = []
    
    for _, player in full_roster_data.iterrows():
        player_name = player["name"]
        player_id = str(player["player_id"])
        assigned_roles = player_roles.get(player_name, [])
        if not assigned_roles: continue

        line = next((r for r in assigned_roles if r.startswith(('F', 'D'))), None)
        st_roles = [r for r in assigned_roles if r.startswith(('PP', 'PK'))]

        player_dict = {
            "name": player_name,
            "position": player["position"],
            "line": line,
            "st_roles": st_roles,
            "player_id": player_id
        }

        player_manual_ratings = manual_ratings_all.get(player_id, {})

        ALL_RATINGS = [
            "toi_individual_rating", "shooting_volume", "shooting_accuracy", 
            "hdshot_creation", "mshot_creation", "ofinishing", "orebound_creation", 
            "oprime_playmaking", "osecond_playmaking", "faceoff_rating", "ozone_entry", 
            "opuck_possession", "ocycle_play", "openalty_drawn", "d_breakout_ability", 
            "d_entry_denial", "o_forechecking_pressure", "d_cycle_defense", 
            "d_shot_blocking", "min_penalty", "maj_penalty",
            "o_hd_shot_creation_rating", "o_md_shot_creation_rating", "o_ld_shot_creation_rating",
            "d_hd_shot_suppression_rating", "d_md_shot_suppression_rating", "d_ld_shot_suppression_rating",
            "pp_shot_volume", "pp_shot_on_net", "pp_chance_creation",
            "pp_playmaking", "pp_finishing", "pp_rebound_creation",
            "pk_shot_suppression", "pk_clearing_ability", "pk_shot_blocking"
        ]

        for rating_name in ALL_RATINGS:
            if rating_name in player:
                base_rating = player.get(rating_name, 1000)
                final_rating = base_rating
                
                manual_rating_info = player_manual_ratings.get(rating_name)
                if manual_rating_info:
                    manual_value = manual_rating_info.get('manual_value', base_rating)
                    manual_weight = manual_rating_info.get('weight', 0) / 100.0
                    base_weight = 1.0 - manual_weight
                    final_rating = (base_rating * base_weight) + (manual_value * manual_weight)
                
                player_dict[rating_name] = final_rating
            else:
                player_dict[rating_name] = 1000

        roster_for_sim.append(player_dict)

    return roster_for_sim

