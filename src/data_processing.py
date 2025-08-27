import streamlit as st
import pandas as pd
from .calculations import calculate_toi_distribution
from .definitions import all_definitions
# MODIFIED: Import our new all-in-one roster function
from utils.db_queries import get_simulation_roster

# This function is for the old Lineup Builder page and can be left as is.
def structure_data_for_sim():
    # ... (this function remains unchanged)
    pass

# This function is for the old Lineup Builder page and can be left as is.
def run_toi_calculation(pim_for: int, pim_against: int):
    # ... (this function remains unchanged)
    pass

# ==============================================================================
# The functions below are for the 1_Dashboard.py page.
# ==============================================================================

def structure_dashboard_data_for_sim(team_type: str):
    """
    Prepares the roster and all player ratings for the main dashboard simulation
    by calling a single database function.
    """
    team_data = st.session_state.dashboard_data[team_type]
    
    team_id = team_data.get('team_id')
    if not team_id:
        return []

    # --- MODIFIED SECTION ---
    # Convert team_id to a standard Python int before passing it to the function.
    full_roster_data = get_simulation_roster(int(team_id))
    # --- END MODIFIED SECTION ---

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
        player_name = player["full_name"]
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
            # Add the new defensive ratings here as well
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

# This function is for the dashboard TOI calculator and is now correct
def run_dashboard_toi_calculation(home_pim: int, away_pim: int):
    # ... (this function remains unchanged)
    pass