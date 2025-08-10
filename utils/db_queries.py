# utils/db_queries.py
import streamlit as st
import pandas as pd
from supabase import Client

@st.cache_data
def load_player_data(supabase: Client): # Pass the client as an argument
    """Fetches player names and IDs from Supabase and returns as a DataFrame."""
    response = supabase.table('players').select('player_id, full_name').execute()
    player_df = pd.DataFrame(response.data)
    return player_df