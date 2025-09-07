# utils/db_queries.py

import streamlit as st
import pandas as pd
import json
import numpy as np
from io import StringIO
from supabase import create_client, Client

def _create_supabase_client():
    """Initializes and returns a Supabase client instance."""
    url = st.secrets.connections.supabase.SUPABASE_URL
    key = st.secrets.connections.supabase.SUPABASE_KEY
    return create_client(url, key)

class NumpyEncoder(json.JSONEncoder):
    """ Custom encoder for numpy data types """
    def default(self, obj):
        if isinstance(obj, (np.int_, np.intc, np.intp, np.int8,
                            np.int16, np.int32, np.int64, np.uint8,
                            np.uint16, np.uint32, np.uint64)):
            return int(obj)
        elif isinstance(obj, (np.float_, np.float16, np.float32, np.float64)):
            return float(obj)
        elif isinstance(obj, (np.ndarray,)):
            return obj.tolist()
        return json.JSONEncoder.default(self, obj)

@st.cache_data
def get_simulation_roster(team_id: int):
    """
    Fetches a complete player roster with all ratings (base, PP, PK)
    by calling a PostgreSQL function in Supabase.
    """
    if not team_id:
        return pd.DataFrame()
    try:
        supabase = _create_supabase_client()
        response = supabase.rpc('get_full_player_data', {'team_id_param': int(team_id)}).execute()
        return pd.DataFrame(response.data)
    except Exception as e:
        st.error(f"Error fetching simulation roster: {e}")
        return pd.DataFrame()

@st.cache_data
def get_goalie_ratings(player_ids: list):
    """Fetches all ratings for a list of goalie player_ids."""
    if not player_ids:
        return pd.DataFrame()
    try:
        supabase = _create_supabase_client()
        clean_player_ids = [int(pid) for pid in player_ids]
        response = supabase.table('goalie_ratings').select('*').in_('player_id', clean_player_ids).execute()
        return pd.DataFrame(response.data)
    except Exception as e:
        st.error(f"Error fetching goalie ratings: {e}")
        return pd.DataFrame()

@st.cache_data
def get_starting_goalie_id(team_id: int):
    """Fetches the player_id of the G1 goalie from the default_lineups table."""
    if not team_id:
        return None
    try:
        supabase = _create_supabase_client()
        response = supabase.table("default_lineups").select("player_id").eq("team_id", int(team_id)).eq("position_slot", "G1").limit(1).execute()
        if response.data:
            return response.data[0]['player_id']
        return None
    except Exception as e:
        st.error(f"Error fetching starting goalie ID: {e}")
        return None

@st.cache_data
def get_manual_goalie_ratings(player_ids: list):
    """Fetches all manual ratings for a given list of goalie IDs."""
    if not player_ids: return {}
    try:
        clean_player_ids = [int(pid) for pid in player_ids]
        supabase = _create_supabase_client()
        response = supabase.table('manual_goalie_ratings').select('*').in_('player_id', clean_player_ids).execute()
        manual_ratings = {}
        for row in response.data:
            player_id = str(row['player_id'])
            rating_name = row['rating_name']
            if player_id not in manual_ratings:
                manual_ratings[player_id] = {}
            manual_ratings[player_id][rating_name] = {'manual_value': row['manual_value'], 'weight': row['weight']}
        return manual_ratings
    except Exception as e:
        st.error(f"Error fetching manual goalie ratings: {e}")
        return {}

def save_manual_goalie_rating(player_id: str, player_name: str, rating_name: str, manual_value: float, weight: int):
    """Saves or updates a single manual rating for a goalie."""
    try:
        supabase = _create_supabase_client()
        supabase.table('manual_goalie_ratings').upsert({
            'player_id': int(player_id), 'player_name': player_name, 'rating_name': rating_name,
            'manual_value': manual_value, 'weight': weight, 'last_updated': 'now()'
        }, on_conflict='player_id, rating_name').execute()
        st.cache_data.clear()
    except Exception as e:
        st.error(f"Error saving manual goalie rating for {rating_name}: {e}")

def delete_manual_goalie_rating(player_id: str, rating_name: str):
    """Deletes a single manual rating for a goalie."""
    try:
        supabase = _create_supabase_client()
        supabase.table('manual_goalie_ratings').delete().match({'player_id': int(player_id), 'rating_name': rating_name}).execute()
        st.cache_data.clear()
    except Exception as e:
        st.error(f"Error deleting manual goalie rating for {rating_name}: {e}")

@st.cache_data
def get_teams():
    """Fetches the list of all teams, including their abbreviation."""
    try:
        supabase = _create_supabase_client()
        response = supabase.table('team_mapping').select('team_id, team_full_name, nhl_team_abbr, team_color_primary, team_color_secondary').order('team_full_name', desc=False).execute()
        return pd.DataFrame(response.data)
    except Exception as e:
        st.error(f"Error fetching teams: {e}")
        return pd.DataFrame()

@st.cache_data
def get_default_lineup(team_id: int):
    """Fetches the default even strength lineup for a given team_id."""
    try:
        supabase = _create_supabase_client()
        response = supabase.table('default_lineups').select('*').eq('team_id', int(team_id)).execute()
        return pd.DataFrame(response.data)
    except Exception as e:
        st.error(f"Error fetching default lineup: {e}")
        return pd.DataFrame()

@st.cache_data
def get_team_roster(team_abbr: str):
    """Fetches all players on a given team using their abbreviation."""
    try:
        supabase = _create_supabase_client()
        response = supabase.table('players').select('player_id, full_name, position').eq('team', team_abbr).execute()
        return pd.DataFrame(response.data)
    except Exception as e:
        st.error(f"Error fetching team roster: {e}")
        return pd.DataFrame()

@st.cache_data
def get_player_ratings(player_ids: list):
    """Fetches all base ratings for a list of player_ids."""
    if not player_ids:
        return pd.DataFrame()
    try:
        clean_player_ids = [int(pid) for pid in player_ids]
        supabase = _create_supabase_client()
        ratings_to_fetch = [
            "player_id", "toi_individual_rating", "shooting_volume", "shooting_accuracy", 
            "hdshot_creation", "mshot_creation", "ofinishing", "orebound_creation", 
            "oprime_playmaking", "osecond_playmaking", "faceoff_rating"
        ]
        response = supabase.table('base_ratings').select(','.join(ratings_to_fetch)).in_('player_id', clean_player_ids).execute()
        return pd.DataFrame(response.data)
    except Exception as e:
        st.error(f"Error fetching player ratings: {e}")
        return pd.DataFrame()

@st.cache_data
def get_default_pp_lineup(team_id: int):
    """Fetches the default Power Play lineup for a given team_id."""
    try:
        supabase = _create_supabase_client()
        response = supabase.table("default_lineups").select("full_name, pp_position, player_id").eq("team_id", int(team_id)).execute()
        return pd.DataFrame(response.data)
    except Exception as e:
        st.error(f"An error occurred in get_default_pp_lineup: {e}")
        return pd.DataFrame()

@st.cache_data
def get_default_pk_lineup(team_id: int):
    """Fetches the default Penalty Kill lineup for a given team_id."""
    try:
        supabase = _create_supabase_client()
        response = supabase.table("default_lineups").select("full_name, pk_position, player_id").eq("team_id", int(team_id)).execute()
        return pd.DataFrame(response.data)
    except Exception as e:
        st.error(f"An error occurred in get_default_pk_lineup: {e}")
        return pd.DataFrame()

def get_coach_by_team_id(team_id: int):
    """Fetches the full profile for a coach based on their team_id."""
    try:
        supabase = _create_supabase_client()
        response = supabase.table("coaches").select("*").eq("team_id", int(team_id)).limit(1).execute()
        return response.data[0] if response.data else {}
    except Exception as e:
        st.error(f"An error occurred fetching coach by team ID: {e}")
        return {}

def get_manual_ratings_for_players(player_ids: list):
    """Fetches all manual ratings for a given list of player IDs."""
    if not player_ids:
        return {}
    try:
        clean_player_ids = [int(pid) for pid in player_ids]
        supabase = _create_supabase_client()
        response = supabase.table('manual_player_ratings').select('*').in_('player_id', clean_player_ids).execute()
        manual_ratings = {}
        for row in response.data:
            player_id = str(row['player_id'])
            rating_name = row['rating_name']
            if player_id not in manual_ratings:
                manual_ratings[player_id] = {}
            manual_ratings[player_id][rating_name] = {'manual_value': row['manual_value'], 'weight': row['weight']}
        return manual_ratings
    except Exception as e:
        st.error(f"Error fetching manual ratings: {e}")
        return {}

def save_manual_rating(player_id: str, player_name: str, rating_name: str, manual_value: float, weight: int):
    """Saves or updates a single manual rating for a player."""
    try:
        supabase = _create_supabase_client()
        supabase.table('manual_player_ratings').upsert({
            'player_id': int(player_id), 'player': player_name, 'rating_name': rating_name,
            'manual_value': manual_value, 'weight': weight, 'last_updated': 'now()'
        }, on_conflict='player_id, rating_name').execute()
        st.cache_data.clear()
    except Exception as e:
        st.error(f"Error saving manual rating for {rating_name}: {e}")

def delete_manual_rating(player_id: str, rating_name: str):
    """Deletes a single manual rating for a player."""
    try:
        supabase = _create_supabase_client()
        supabase.table('manual_player_ratings').delete().match({'player_id': int(player_id), 'rating_name': rating_name}).execute()
        st.cache_data.clear()
    except Exception as e:
        st.error(f"Error deleting manual rating for {rating_name}: {e}")

def log_rating_change(player_id, player_name, rating_name, old_value, new_value, old_weight, new_weight):
    """Inserts a single record into the rating_change_log table."""
    try:
        supabase = _create_supabase_client()
        supabase.table('rating_change_log').insert({
            'player_id': int(player_id), 
            'player_name': player_name, 
            'rating_name': rating_name,
            'old_manual_value': old_value, 
            'new_manual_value': new_value,
            'old_weight': old_weight, 
            'new_weight': new_weight
        }).execute()
    except Exception as e:
        print(f"Error logging rating change: {e}")
        
@st.cache_data(ttl=3600)
def get_schedule():
    """Retrieves the upcoming schedule from the database and formats it for display."""
    try:
        supabase = _create_supabase_client()
        response = supabase.rpc('get_schedule_with_team_names').execute()
        if response.data:
            df = pd.DataFrame(response.data)
            df['display_name'] = df['away_team_name'] + ' @ ' + df['home_team_name'] + ' (' + pd.to_datetime(df['game_date']).dt.strftime('%Y-%m-%d') + ')'
            return df.sort_values('game_date')
        return pd.DataFrame()
    except Exception as e:
        st.error(f"Error fetching schedule from DB: {e}")
        return pd.DataFrame()
    
@st.cache_data
def get_full_goalie_data(team_id: int):
    """
    Fetches a complete goalie roster with all ratings
    by calling a PostgreSQL function in Supabase.
    """
    if not team_id:
        return pd.DataFrame()
    try:
        supabase = _create_supabase_client()
        response = supabase.rpc('get_full_goalie_data', {'team_id_param': int(team_id)}).execute()
        return pd.DataFrame(response.data)
    except Exception as e:
        st.error(f"Error fetching full goalie data: {e}")
        return pd.DataFrame()
    
def save_coach_ratings(team_id: int, ratings_payload: dict):
    """Updates specified ratings for a coach based on their team_id."""
    try:
        supabase = _create_supabase_client()
        supabase.table('coaches').update(ratings_payload).eq('team_id', int(team_id)).execute()
        st.cache_data.clear()
    except Exception as e:
        st.error(f"Error saving coach ratings: {e}")

def save_simulation_results(game_id: int, results: dict):
    """Saves a simulation result dictionary to the database."""
    try:
        serializable_results = results.copy()
        for key, value in serializable_results.items():
            if isinstance(value, pd.DataFrame):
                serializable_results[key] = value.to_json(orient='split')
        
        json_data = json.dumps(serializable_results, cls=NumpyEncoder)

        supabase = _create_supabase_client()
        supabase.table('simulation_results').upsert({
            'game_id': int(game_id),
            'results_data': json_data
        }, on_conflict='game_id').execute()

    except Exception as e:
        st.error(f"Error saving simulation results: {e}")

def load_simulation_results(game_id: int):
    """Loads and deserializes simulation results from the database."""
    try:
        supabase = _create_supabase_client()
        response = supabase.table('simulation_results').select('results_data').eq('game_id', int(game_id)).limit(1).execute()

        if response.data:
            results_json = response.data[0]['results_data']
            loaded_results = json.loads(results_json)

            for key, value in loaded_results.items():
                if isinstance(value, str):
                    try:
                        if '"columns"' in value and '"data"' in value:
                            loaded_results[key] = pd.read_json(StringIO(value), orient='split')
                    except Exception:
                        pass

            return loaded_results
        return None
    except Exception as e:
        st.error(f"Error loading simulation results: {e}")
        return None
    
def save_dashboard_state(game_id: int, team_type: str, team_data: dict):
    """Saves the relevant dashboard state for one team to the database."""
    try:
        payload = {
            f'{team_type}_lineup': team_data['lineup'].to_json(orient='split'),
            f'{team_type}_pp_lineup': team_data['pp_lineup'].to_json(orient='split'),
            f'{team_type}_pk_lineup': team_data['pk_lineup'].to_json(orient='split'),
            f'{team_type}_starting_goalie': json.dumps(team_data.get('starting_goalie'))
        }

        supabase = _create_supabase_client()
        supabase.table('dashboard_state').upsert({
            'game_id': int(game_id),
            **payload
        }, on_conflict='game_id').execute()

    except Exception as e:
        st.error(f"Error saving dashboard state for {team_type}: {e}")

def load_dashboard_state(game_id: int):
    """Loads the entire saved dashboard state for a game."""
    try:
        supabase = _create_supabase_client()
        response = supabase.table('dashboard_state').select('*').eq('game_id', int(game_id)).limit(1).execute()
        
        if response.data:
            return response.data[0]
        return None
        
    except Exception as e:
        st.error(f"Error loading dashboard state: {e}")
        return None

@st.cache_data
def get_player_shooting_actuals(player_ids: list):
    """
    Fetches the real-world (actuals) 5v5 shooting stats for a list of players
    by calling a PostgreSQL function in Supabase.
    """
    if not player_ids:
        return pd.DataFrame()
    try:
        clean_player_ids = [int(pid) for pid in player_ids]
        supabase = _create_supabase_client()
        response = supabase.rpc('get_player_shooting_actuals', {'player_ids_param': clean_player_ids}).execute()
        return pd.DataFrame(response.data)
    except Exception as e:
        st.error(f"Error fetching player shooting actuals: {e}")
        return pd.DataFrame()

@st.cache_data
def get_player_possession_actuals(player_ids: list):
    """
    Fetches the real-world (actuals) 5v5 possession and playmaking stats for a list of players
    by calling a PostgreSQL function in Supabase.
    """
    if not player_ids:
        return pd.DataFrame()
    try:
        clean_player_ids = [int(pid) for pid in player_ids]
        supabase = _create_supabase_client()
        response = supabase.rpc('get_player_possession_actuals', {'player_ids_param': clean_player_ids}).execute()
        return pd.DataFrame(response.data)
    except Exception as e:
        st.error(f"Error fetching player possession actuals: {e}")
        return pd.DataFrame()

# --- NEW FUNCTION FOR TRANSITION TAB ---
@st.cache_data
def get_player_transition_actuals(player_ids: list):
    """
    Fetches the real-world (actuals) 5v5 transition stats for a list of players
    by calling a PostgreSQL function in Supabase.
    """
    if not player_ids:
        return pd.DataFrame()
    try:
        clean_player_ids = [int(pid) for pid in player_ids]
        supabase = _create_supabase_client()
        response = supabase.rpc('get_player_transition_actuals', {'player_ids_param': clean_player_ids}).execute()
        return pd.DataFrame(response.data)
    except Exception as e:
        st.error(f"Error fetching player transition actuals: {e}")
        return pd.DataFrame()