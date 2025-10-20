import sys
import os
import pandas as pd
import random

# --- FIX: Add the project root directory to the Python path ---
# This ensures that modules in subdirectories (like src) can find modules
# in the root directory (like shared_simulation_constants).
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
# -----------------------------------------------------------

# --- Import the components we need to test ---
from results_adjuster import MarkovSimulator
from shared_simulation_constants import PlayerProfile, GoalieProfile

def create_mock_team_data(team_id: int, team_name: str) -> dict:
    """
    Generates a complete, structured dictionary of mock team data,
    including players, a goalie, and line combinations.
    """
    players = []
    player_id_start = team_id * 1000
    
    # Create 12 Forwards and 6 Defensemen
    for i in range(18):
        pos = "C" if i % 4 == 0 else "W" if i < 12 else "D"
        line_num = (i // 3) + 1 if pos != 'D' else (i - 12) // 2 + 1
        line_name = f"F{line_num}" if pos != 'D' else f"D{line_num}"
        
        player_data = {
            'player_id': player_id_start + i,
            'full_name': f"{team_name} Player {i+1}",
            'position': pos,
            'line': line_name,
            'st_roles': [],
            # Add all other player ratings with random values for testing
            'shooting_volume': random.randint(950, 1050),
            'ofinishing': random.randint(950, 1050),
            'faceoff_rating': random.randint(950, 1050)
            # In a real test, you would populate all ratings
        }
        # Get all fields from the dataclass to ensure we match the structure
        # FIX: Changed f.name to f. The loop variable 'f' is already the string name of the field.
        profile_fields = {f for f in PlayerProfile.__dataclass_fields__}
        
        # Fill any missing rating fields with a default of 1000
        for field in profile_fields:
            if field not in player_data:
                player_data[field] = 1000

        players.append(player_data)

    lineup_df = pd.DataFrame(players)

    # Create mock lines
    lines = {
        'F1': lineup_df[lineup_df['line'] == 'F1']['player_id'].tolist(),
        'F2': lineup_df[lineup_df['line'] == 'F2']['player_id'].tolist(),
        'F3': lineup_df[lineup_df['line'] == 'F3']['player_id'].tolist(),
        'F4': lineup_df[lineup_df['line'] == 'F4']['player_id'].tolist(),
        'D1': lineup_df[lineup_df['line'] == 'D1']['player_id'].tolist(),
        'D2': lineup_df[lineup_df['line'] == 'D2']['player_id'].tolist(),
        'D3': lineup_df[lineup_df['line'] == 'D3']['player_id'].tolist(),
    }
    
    # Create mock goalie
    goalie_data = {
        'player_id': player_id_start + 100,
        'full_name': f"{team_name} Goalie",
        'g_high_danger_sv_rating': 1020,
        'g_medium_danger_sv_rating': 1010,
        'g_low_danger_sv_rating': 1000,
        'g_rebound_control_rating': 990,
        'g_freeze_puck_rating': 1010
    }

    return {
        'id': team_id,
        'lineup': lineup_df,
        'lines': lines,
        'goalie': goalie_data
    }


if __name__ == "__main__":
    # 1. Create mock data for two teams
    home_team = create_mock_team_data(10, "Home Blues")
    away_team = create_mock_team_data(20, "Away Reds")

    # 2. Instantiate the simulator with a small number of sims for a quick test
    print("Initializing Markov Simulator...")
    # Use a small number like 100 for a very fast test run
    simulator = MarkovSimulator(home_team, away_team, num_simulations=100)

    # 3. Run the simulation
    results = simulator.run_monte_carlo_simulation()

    # 4. Print the aggregated results to the console
    print("\n--- AGGREGATED SIMULATION RESULTS ---")
    
    print("\nHome Team Totals:")
    print(results['home_total'].to_string())

    print("\n\nHome Players (Top 5 by Goals):")
    # Displaying a subset of columns for readability
    home_players_df = results['home_players']
    display_cols = ['Player', 'Goals_Total', 'Assists_Total', 'Shots_Total', 'TOI_Total']
    # Ensure columns exist before trying to display them
    existing_cols = [col for col in display_cols if col in home_players_df.columns]
    print(home_players_df.sort_values(by='Goals_Total', ascending=False).head(5)[existing_cols].to_string(index=False))

    print("\n\nAway Team Totals:")
    print(results['away_total'].to_string())

    print("\n\nTest complete.")


