import requests
import pandas as pd
from utils.db_queries import _create_supabase_client

def add_single_player(player_id: int, team_abbr: str):
    """
    Fetches a single player's data from the NHL API and inserts them into the database.

    Args:
        player_id (int): The NHL player ID.
        team_abbr (str): The 3-letter abbreviation for the player's team (e.g., 'ANA').
    """
    print(f"--- Starting Manual Add for Player ID: {player_id} ---")
    supabase = _create_supabase_client()

    # 1. Get Team ID from the database
    try:
        team_data = supabase.table('team_mapping').select('team_id').eq('nhl_team_abbr', team_abbr.upper()).single().execute()
        if not team_data.data:
            print(f"ERROR: No team found with abbreviation '{team_abbr}'. Aborting.")
            return
        team_id = team_data.data['team_id']
        print(f"Found Team ID: {team_id} for abbreviation {team_abbr.upper()}")
    except Exception as e:
        print(f"ERROR: Could not retrieve team ID for '{team_abbr}'. Details: {e}")
        return

    # 2. Fetch Player Details from NHL API
    try:
        url = f"https://api-web.nhle.com/v1/player/{player_id}/landing"
        res = requests.get(url, timeout=10).json()
        print(f"Successfully fetched player data for {res['firstName']['default']} {res['lastName']['default']}.")
    except Exception as e:
        print(f"ERROR: Could not fetch player data from NHL API for ID {player_id}. Details: {e}")
        return

    # 3. Prepare Player Data for Insertion
    player_data = {
        'player_id': str(res['playerId']),
        'full_name': f"{res['firstName']['default']} {res['lastName']['default']}",
        'position': res.get('position', 'N/A'),
        'jersey_number': res.get('sweaterNumber'),
        'team': team_abbr.upper(),
        'team_id': team_id,
        'birth_date': res.get('birthDate'),
        'birth_city': res.get('birthCity', {}).get('default'),
        'birth_country': res.get('birthCountry'),
        'headshot_url': res.get('headshot'),
        'height_in_inches': res.get('heightInInches'),
        'weight_in_pounds': res.get('weightInPounds')
        # 'is_active' line has been removed
    }

    # 4. Insert into Supabase
    try:
        # Using upsert=True will insert the new player or update them if they already exist.
        supabase.table('players').upsert(player_data, on_conflict='player_id').execute()
        print(f"✅ Successfully added/updated {player_data['full_name']} in the database for team {team_abbr.upper()}.")
    except Exception as e:
        print(f"ERROR: Failed to insert player into the database. Details: {e}")

    print("--- Manual Add Process Complete ---")