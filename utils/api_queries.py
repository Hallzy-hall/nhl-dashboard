import requests
import pandas as pd
from datetime import datetime, timedelta # MODIFIED: Added timedelta
import streamlit as st
from utils.db_queries import get_teams, _create_supabase_client

def fetch_nhl_schedule():
    """
    Fetches the NHL schedule for a 7-day window: the previous day, the current day,
    and the next five days from the live NHL API.
    """
    all_games = []
    today = datetime.now()
    
    # Loop through a 7-day window (-1 day to +5 days)
    for i in range(-1, 6):
        date_to_fetch = today + timedelta(days=i)
        formatted_date = date_to_fetch.strftime('%Y-%m-%d')
        
        # Construct the API URL for the specific date
        api_url = f"https://api-web.nhle.com/v1/schedule/{formatted_date}"
        
        try:
            response = requests.get(api_url)
            response.raise_for_status() # Raise an exception for bad status codes
            data = response.json()
            
            # The games are located in the 'gameWeek' list for each day
            for day in data.get('gameWeek', []):
                for game in day.get('games', []):
                    game_id = game.get('id')
                    game_date = game.get('startTimeUTC') # Using startTimeUTC for precision
                    home_team = game.get('homeTeam', {}).get('abbrev')
                    away_team = game.get('awayTeam', {}).get('abbrev')
                    game_state = game.get('gameState') # e.g., 'OFF', 'LIVE', 'FUT'

                    if game_id and game_date and home_team and away_team:
                        all_games.append({
                            "id": game_id,
                            "startTimeUTC": game_date,
                            "home_team_abbr": home_team,
                            "away_team_abbr": away_team,
                            "gameScheduleState": game_state
                        })
                        
        except requests.exceptions.RequestException as e:
            st.error(f"Error fetching schedule data for {formatted_date}: {e}")
            continue # Continue to the next day if an error occurs

    return all_games
    
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
    
    team_abbr_to_id = pd.Series(teams_df.team_id.values, index=teams_df.nhl_team_abbr).to_dict()

    # 2. Fetch the schedule data from the new live API function
    schedule_games = fetch_nhl_schedule()
    if not schedule_games:
        st.warning("No games found in the schedule to update.")
        return

    # 3. Process the data and prepare it for the database
    games_to_upsert = []
    for game in schedule_games: # MODIFIED: Removed the 15-game limit
        home_team_abbr = game["home_team_abbr"]
        away_team_abbr = game["away_team_abbr"]

        home_team_id = team_abbr_to_id.get(home_team_abbr)
        away_team_id = team_abbr_to_id.get(away_team_abbr)

        if home_team_id and away_team_id:
            game_data = {
                "game_id": game["id"],
                "game_date": game["startTimeUTC"],
                "home_team_id": home_team_id,
                "away_team_id": away_team_id,
                "status": game.get("gameScheduleState", "SCHEDULED")
            }
            games_to_upsert.append(game_data)

    # 4. Upsert the data into our Supabase 'schedule' table
    if games_to_upsert:
        try:
            supabase = _create_supabase_client()
            supabase.table("schedule").upsert(games_to_upsert, on_conflict="game_id").execute()
            st.success(f"Successfully updated schedule with {len(games_to_upsert)} games.")
        except Exception as e:
            st.error(f"Error upserting schedule data: {e}")

# =============================================================================
#  PLAYER SYNC FUNCTIONS (UNCHANGED)
# =============================================================================

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
        for index, row in players_with_team_change.iterrows():
            if pd.isna(row['team_id_api']):
                _handle_ufa_player(supabase, str(row['player_id']), row['full_name_api'])
            else:
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
        return

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