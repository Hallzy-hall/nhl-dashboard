import streamlit as st
import pandas as pd
from supabase import create_client, Client

def _create_supabase_client():
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

@st.cache_data
def get_teams():
    """Fetches the list of all teams, including their abbreviation."""
    try:
        supabase = _create_supabase_client()
        response = supabase.table('team_mapping').select('team_id, team_full_name, nhl_team_abbr').order('team_full_name', desc=False).execute()
        return pd.DataFrame(response.data)
    except Exception as e:
        st.error(f"Error fetching teams: {e}")
        return pd.DataFrame()

@st.cache_data
def get_default_lineup(team_id: int):
    """Fetches the default lineup for a given team_id."""
    try:
        supabase = _create_supabase_client()
        response = supabase.table('default_lineups').select('*').eq('team_id', team_id).execute()
        return pd.DataFrame(response.data)
    except Exception as e:
        st.error(f"Error fetching default lineup: {e}")
        return pd.DataFrame()

@st.cache_data
def get_team_roster(team_abbr: str):
    """Fetches all players on a given team using their abbreviation."""
    try:
        supabase = _create_supabase_client()
        response = supabase.table('players').select('player_id, full_name').eq('team', team_abbr).execute()
        return pd.DataFrame(response.data)
    except Exception as e:
        st.error(f"Error fetching team roster: {e}")
        return pd.DataFrame()

# --- NEW FUNCTION ---
@st.cache_data
def get_player_ratings(player_ids: list):
    """
    Fetches the 'por' rating for a list of player_ids from the base_ratings table.
    """
    if not player_ids:
        return pd.DataFrame()
    try:
        supabase = _create_supabase_client()
        # .in_() fetches all rows where player_id is in the provided list
        response = supabase.table('base_ratings').select('player_id, por').in_('player_id', player_ids).execute()
        return pd.DataFrame(response.data)
    except Exception as e:
        st.error(f"Error fetching player ratings: {e}")
        return pd.DataFrame()