import streamlit as st
import pandas as pd
from utils.db_queries import load_player_data

# --- PAGE CONFIGURATION ---
st.set_page_config(
    page_title="NHL Lineup Simulation Tool",
    page_icon="🏒",
    layout="wide"
)

# --- INITIALIZE SUPABASE CONNECTION ---
try:
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    supabase: Client = create_client(url, key)
except KeyError:
    st.error("Supabase credentials not found. Please add them to your Streamlit Secrets.")
    st.stop()


# --- DATA FETCHING FUNCTION ---
@st.cache_data
def load_player_data():
    """Fetches player names and IDs from Supabase and returns as a DataFrame."""
    # MODIFIED: Changed 'player_name' to 'full_name' to match your database
    response = supabase.table('players').select('player_id, full_name').execute()
    player_df = pd.DataFrame(response.data)
    return player_df

# Now just call the clean, imported function
player_df = load_player_data(supabase)
player_names = player_df['full_name'].tolist() if not player_df.empty else []


# --- SIDEBAR ---
with st.sidebar:
    st.header("Game Setup")
    mock_teams = ["Edmonton Oilers", "Toronto Maple Leafs"]
    home_team = st.selectbox("Home Team", options=mock_teams)
    away_team = st.selectbox("Away Team", options=mock_teams, index=1)
    
    st.divider()
    
    st.header("Player Editor")
    selected_player_name = st.selectbox("Select Player", options=player_names)

    if selected_player_name:
        # MODIFIED: Changed 'player_name' to 'full_name'
        selected_player_id = player_df[player_df['full_name'] == selected_player_name]['player_id'].iloc[0]
        
        st.write(f"You selected: **{selected_player_name}**")
        st.write(f"Associated `player_id`: **{selected_player_id}**")
        
        if st.button(f"Edit {selected_player_name}'s Ratings"):
            st.info(f"Pop-up for editing Player ID {selected_player_id} would appear here.")


# --- MAIN PAGE ---
st.title("Lineup Builder")
st.write(f"Building lines for **{home_team}** vs. **{away_team}**")

col_ev, col_pp = st.columns(2)

with col_ev:
    st.subheader("Even Strength")
    st.markdown("**Line 1**")
    line1_cols = st.columns(3)
    line1_cols[0].selectbox("LW", options=player_names, key="l1_lw")
    line1_cols[1].selectbox("C", options=player_names, key="l1_c")
    line1_cols[2].selectbox("RW", options=player_names, key="l1_rw")

with col_pp:
    st.subheader("Special Teams")
    st.markdown("**Power Play 1**")
    pp1_cols = st.columns(3)
    pp1_cols[0].selectbox("F1", options=player_names, key="pp1_f1")
    pp1_cols[1].selectbox("F2", options=player_names, key="pp1_f2")
    pp1_cols[2].selectbox("F3", options=player_names, key="pp1_f3")
    
# ... The rest of your app code ...