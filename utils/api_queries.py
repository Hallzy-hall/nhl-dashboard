# utils/api_queries.py

import requests
import pandas as pd
from datetime import datetime
import streamlit as st
from utils.db_queries import get_teams, _create_supabase_client

# utils/api_queries.py

def fetch_nhl_schedule():
    """
    MOCK FUNCTION: Returns a hardcoded list of the first 15 games of the
    2024-2025 season to be used for development during the off-season.
    """
    st.warning("Using mock schedule data for development.", icon="⚠️")
    mock_games = [
        {'id': 2024020001, 'startTimeUTC': '2024-10-08T23:00:00Z', 'homeTeam': {'abbrev': 'TBL'}, 'awayTeam': {'abbrev': 'BUF'}, 'gameScheduleState': 'SCHEDULED'},
        {'id': 2024020002, 'startTimeUTC': '2024-10-08T23:00:00Z', 'homeTeam': {'abbrev': 'BOS'}, 'awayTeam': {'abbrev': 'FLA'}, 'gameScheduleState': 'SCHEDULED'},
        {'id': 2024020003, 'startTimeUTC': '2024-10-09T02:00:00Z', 'homeTeam': {'abbrev': 'VAN'}, 'awayTeam': {'abbrev': 'EDM'}, 'gameScheduleState': 'SCHEDULED'},
        {'id': 2024020004, 'startTimeUTC': '2024-10-09T23:00:00Z', 'homeTeam': {'abbrev': 'WSH'}, 'awayTeam': {'abbrev': 'CAR'}, 'gameScheduleState': 'SCHEDULED'},
        {'id': 2024020005, 'startTimeUTC': '2024-10-09T23:30:00Z', 'homeTeam': {'abbrev': 'NJD'}, 'awayTeam': {'abbrev': 'MTL'}, 'gameScheduleState': 'SCHEDULED'},
        {'id': 2024020006, 'startTimeUTC': '2024-10-10T00:00:00Z', 'homeTeam': {'abbrev': 'TOR'}, 'awayTeam': {'abbrev': 'OTT'}, 'gameScheduleState': 'SCHEDULED'},
        {'id': 2024020007, 'startTimeUTC': '2024-10-10T02:00:00Z', 'homeTeam': {'abbrev': 'SEA'}, 'awayTeam': {'abbrev': 'SJS'}, 'gameScheduleState': 'SCHEDULED'},
        {'id': 2024020008, 'startTimeUTC': '2024-10-10T23:00:00Z', 'homeTeam': {'abbrev': 'NYR'}, 'awayTeam': {'abbrev': 'PIT'}, 'gameScheduleState': 'SCHEDULED'},
        {'id': 2024020009, 'startTimeUTC': '2024-10-11T00:00:00Z', 'homeTeam': {'abbrev': 'DAL'}, 'awayTeam': {'abbrev': 'NSH'}, 'gameScheduleState': 'SCHEDULED'},
        {'id': 2024020010, 'startTimeUTC': '2024-10-11T01:00:00Z', 'homeTeam': {'abbrev': 'COL'}, 'awayTeam': {'abbrev': 'ARI'}, 'gameScheduleState': 'SCHEDULED'},
        {'id': 2024020011, 'startTimeUTC': '2024-10-11T23:00:00Z', 'homeTeam': {'abbrev': 'CBJ'}, 'awayTeam': {'abbrev': 'PHI'}, 'gameScheduleState': 'SCHEDULED'},
        {'id': 2024020012, 'startTimeUTC': '2024-10-11T23:00:00Z', 'homeTeam': {'abbrev': 'FLA'}, 'awayTeam': {'abbrev': 'TBL'}, 'gameScheduleState': 'SCHEDULED'},
        {'id': 2024020013, 'startTimeUTC': '2024-10-12T00:00:00Z', 'homeTeam': {'abbrev': 'MIN'}, 'awayTeam': {'abbrev': 'STL'}, 'gameScheduleState': 'SCHEDULED'},
        {'id': 2024020014, 'startTimeUTC': '2024-10-12T02:30:00Z', 'homeTeam': {'abbrev': 'ANA'}, 'awayTeam': {'abbrev': 'VGK'}, 'gameScheduleState': 'SCHEDULED'},
        {'id': 2024020015, 'startTimeUTC': '2024-10-12T17:00:00Z', 'homeTeam': {'abbrev': 'WPG'}, 'awayTeam': {'abbrev': 'CGY'}, 'gameScheduleState': 'SCHEDULED'},
    ]
    return mock_games


    
def update_schedule_in_db():
    """
    Fetches the latest NHL schedule, maps teams to internal IDs using their
    abbreviations, and upserts the data into the 'schedule' table in Supabase.
    """
    # 1. Fetch our team mapping to match abbreviations to IDs
    teams_df = get_teams()
    if teams_df.empty:
        st.error("Could not retrieve team mapping from database. Aborting schedule update.")
        return
    
    # --- MODIFIED: Create a lookup dictionary using team abbreviation ---
    team_abbr_to_id = pd.Series(teams_df.team_id.values, index=teams_df.nhl_team_abbr).to_dict()

    # 2. Fetch the schedule data from the new API
    schedule_games = fetch_nhl_schedule()
    if not schedule_games:
        return

    # 3. Process the data and prepare it for the database
    games_to_upsert = []
    for game in schedule_games[:15]: # Ensure we only process the first 15 games
        home_team_abbr = game["homeTeam"]["abbrev"]
        away_team_abbr = game["awayTeam"]["abbrev"]

        home_team_id = team_abbr_to_id.get(home_team_abbr)
        away_team_id = team_abbr_to_id.get(away_team_abbr)

        if home_team_id and away_team_id:
            game_data = {
                "game_id": game["id"],
                "game_date": game["startTimeUTC"],
                "home_team_id": home_team_id,
                "away_team_id": away_team_id,
                "status": game.get("gameScheduleState", "SCHEDULED") # Use a default status
            }
            games_to_upsert.append(game_data)

    # 4. Upsert the data into our Supabase 'schedule' table
    if games_to_upsert:
        try:
            supabase = _create_supabase_client()
            supabase.table("schedule").upsert(games_to_upsert, on_conflict="game_id").execute()
            st.success(f"Successfully updated schedule with {len(games_to_upsert)} upcoming games.")
        except Exception as e:
            st.error(f"Error upserting schedule data: {e}")

def sync_all_player_data():
    """
    Comprehensive script to sync the Supabase 'players' table with the NHL API.
    """
    st.info("Starting comprehensive player data synchronization...")
    print("--- Starting Player Roster Sync ---")
    
    supabase = _create_supabase_client()
    
    api_players_df = _fetch_all_players_from_api()
    if api_players_df.empty:
        st.error("Could not fetch player data from API. Aborting sync.")
        return

    db_players_df = pd.DataFrame(supabase.table('players').select('player_id, full_name, team, team_id').execute().data)
    db_players_df['player_id'] = db_players_df['player_id'].astype(str)
    
    st.info(f"Fetched {len(api_players_df)} players from API. Found {len(db_players_df)} players in the database.")
    print(f"Fetched {len(api_players_df)} players from API. Found {len(db_players_df)} players in the database.")

    comparison_df = pd.merge(
        db_players_df,
        api_players_df,
        on='player_id',
        how='outer',
        suffixes=('_db', '_api'),
        indicator=True
    )

    new_players = comparison_df[comparison_df['_merge'] == 'right_only']
    inactive_players = comparison_df[comparison_df['_merge'] == 'left_only']
    existing_players = comparison_df[comparison_df['_merge'] == 'both']
    players_with_team_change = existing_players[existing_players['team'] != existing_players['team_api']]

    if not new_players.empty:
        st.info(f"Found {len(new_players)} new players to add.")
        print(f"Found {len(new_players)} new players to add.")
        cols_to_insert = [
            'player_id', 'full_name_api', 'position', 'jersey_number', 'team_api', 
            'birth_date', 'birth_city', 'birth_country', 'headshot_url', 'team_id_api', 
            'height_in_inches', 'weight_in_pounds'
        ]
        new_players_to_insert = new_players[cols_to_insert].rename(columns={
            'full_name_api': 'full_name', 'team_api': 'team', 'team_id_api': 'team_id'
        })
        _bulk_insert_players(supabase, new_players_to_insert)

    if not inactive_players.empty:
        st.info(f"Found {len(inactive_players)} inactive players to update to UFA.")
        print(f"Found {len(inactive_players)} inactive players to update to UFA.")
        for index, row in inactive_players.iterrows():
            _handle_ufa_player(supabase, str(row['player_id']), row['full_name'])

    if not players_with_team_change.empty:
        st.info(f"Found {len(players_with_team_change)} players with team changes.")
        print(f"Found {len(players_with_team_change)} players with team changes.")
        # --- MODIFIED: This loop now handles players who become UFAs ---
        for index, row in players_with_team_change.iterrows():
            # Check if the new team_id is valid
            if pd.isna(row['team_id_api']):
                # If the new team_id is missing, the player is now a UFA
                _handle_ufa_player(supabase, str(row['player_id']), row['full_name_api'])
            else:
                # Otherwise, they changed to a different, known team
                _update_player_team(supabase, str(row['player_id']), row['full_name_api'], int(row['team_id_api']), row['team_api'])
            
    st.success("Player data synchronization complete!")
    print("--- Player Roster Sync Complete ---")

def _fetch_all_players_from_api():
    """
    Gets a comprehensive list of all players (current and recent seasons) from the API.
    """
    teams_df = get_teams()
    if teams_df.empty: return pd.DataFrame()

    unique_player_ids = set()
    
    print("Fetching current rosters...")
    for abbr in teams_df['nhl_team_abbr']:
        try:
            url = f"https://api-web.nhle.com/v1/roster/{abbr}/current"
            res = requests.get(url, timeout=10).json()
            for pos in ['forwards', 'defensemen', 'goalies']:
                for player in res.get(pos, []):
                    unique_player_ids.add(player['id'])
        except Exception:
            print(f"  - Could not fetch current roster for {abbr}")

    current_year = datetime.now().year
    print("\nFetching historical rosters for comprehensive list...")
    for year in range(2021, current_year + 1):
        season = f"{year-1}{year}"
        print(f"  -> Season {season}")
        for abbr in teams_df['nhl_team_abbr']:
            try:
                url = f"https://api-web.nhle.com/v1/roster/{abbr}/{season}"
                res = requests.get(url, timeout=10).json()
                for pos in ['forwards', 'defensemen', 'goalies']:
                    for player in res.get(pos, []):
                        unique_player_ids.add(player['id'])
            except Exception:
                continue

    print(f"\nFetching details for {len(unique_player_ids)} unique players...")
    all_player_details = []
    team_abbr_to_id = pd.Series(teams_df.team_id.values, index=teams_df.nhl_team_abbr).to_dict()

    for i, player_id in enumerate(list(unique_player_ids)):
        if (i + 1) % 100 == 0:
            print(f"    - Processed {i+1}/{len(unique_player_ids)} players...")
        try:
            url = f"https://api-web.nhle.com/v1/player/{player_id}/landing"
            res = requests.get(url, timeout=10).json()
            team_abbr = res.get('currentTeamAbbrev')
            
            all_player_details.append({
                'player_id': str(res['playerId']),
                'full_name_api': f"{res['firstName']['default']} {res['lastName']['default']}",
                'position': res.get('position', 'N/A'),
                'jersey_number': res.get('sweaterNumber'),
                'team_api': team_abbr,
                'birth_date': res.get('birthDate'),
                'birth_city': res.get('birthCity', {}).get('default'),
                'birth_country': res.get('birthCountry'),
                'headshot_url': res.get('headshot'),
                'team_id_api': team_abbr_to_id.get(team_abbr),
                'height_in_inches': res.get('heightInInches'),
                'weight_in_pounds': res.get('weightInPounds')
            })
        except Exception:
            continue
            
    return pd.DataFrame(all_player_details)

# --- MODIFIED: This function now also creates default base ratings ---
def _bulk_insert_players(supabase, df):
    """Helper to insert a dataframe of new players and their default base ratings."""
    if df.empty:
        return

    # 1. Insert new players into the 'players' table
    try:
        player_data_to_insert = df.to_dict(orient='records')
        supabase.table('players').insert(player_data_to_insert).execute()
        print(f"  -> Successfully inserted {len(df)} new players into 'players' table.")
    except Exception as e:
        print(f"  -> ERROR inserting new players into 'players' table: {e}")
        return # Stop if we can't insert the players, as ratings would fail anyway

    # 2. Create and insert default base ratings for those new players
    try:
        ratings_to_insert = []
        rating_columns = [
            "toi_individual_rating", "shooting_volume", "shooting_accuracy",
            "hdshot_creation", "mshot_creation", "ofinishing", "orebound_creation",
            "oprime_playmaking", "osecond_playmaking", "faceoff_rating", "ozone_entry",
            "opuck_possession", "ocycle_play", "openalty_drawn", "d_breakout_ability",
            "d_entry_denial", "o_forechecking_pressure", "d_cycle_defense",
            "d_shot_blocking", "min_penalty", "maj_penalty"
        ]
        
        for index, row in df.iterrows():
            new_rating_row = {
                'player_id': row['player_id'],
                'team': row['team'],
                'team_id': row['team_id']
            }
            # Set every specified rating column to a default of 800
            for col in rating_columns:
                new_rating_row[col] = 800
            ratings_to_insert.append(new_rating_row)

        supabase.table('base_ratings').insert(ratings_to_insert).execute()
        print(f"  -> Successfully inserted default base ratings for {len(df)} new players.")
    except Exception as e:
        print(f"  -> ERROR inserting default base ratings: {e}")

def _update_player_team(supabase, player_id, player_name, new_team_id, new_team_abbr):
    """Updates a player's team across all relevant tables."""
    print(f"  -> Updating {player_name} ({player_id}) to new team: {new_team_abbr}")
    try:
        supabase.table('players').update({'team': new_team_abbr, 'team_id': new_team_id}).eq('player_id', player_id).execute()
        supabase.table('base_ratings').update({'team': new_team_abbr, 'team_id': new_team_id}).eq('player_id', player_id).execute()
        supabase.table('goalie_ratings').update({'team': new_team_abbr, 'team_id': new_team_id}).eq('player_id', player_id).execute()
        supabase.table('default_lineups').update({'team_id': new_team_id}).eq('player_id', player_id).execute()
    except Exception as e:
        print(f"  -> ERROR updating player {player_id}: {e}")

def _handle_ufa_player(supabase, player_id, player_name):
    """Sets a player to UFA and nullifies their lineup positions."""
    print(f"  -> Setting {player_name} ({player_id}) to UFA.")
    UFA_TEAM_ID = 50
    UFA_TEAM_ABBR = "UFA"
    try:
        _update_player_team(supabase, player_id, player_name, UFA_TEAM_ID, UFA_TEAM_ABBR)
        supabase.table('default_lineups').update({
            'position_slot': None,
            'pp_position': None,
            'pk_position': None
        }).eq('player_id', player_id).execute()
    except Exception as e:
        print(f"  -> ERROR setting player {player_id} to UFA: {e}")