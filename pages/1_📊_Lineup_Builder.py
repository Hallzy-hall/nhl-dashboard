import streamlit as st
import pandas as pd
# Import the new function
from utils.db_queries import get_teams, get_default_lineup, get_team_roster, get_player_ratings

# --- PAGE CONFIGURATION ---
st.set_page_config(page_title="Lineup Builder", page_icon="📊", layout="wide")

st.title("Lineup Builder")

# --- INITIALIZE SESSION STATE ---
if 'selected_team_id' not in st.session_state:
    st.session_state.selected_team_id = None
    st.session_state.current_lineup = pd.DataFrame()
    st.session_state.current_roster = pd.DataFrame()
    st.session_state.player_ratings = pd.DataFrame() # To store ratings for the whole team

# --- DATA LOADING & CALLBACKS ---
teams_df = get_teams()
team_names = teams_df['team_full_name'].tolist() if not teams_df.empty else []

def on_team_select():
    """This runs when the user selects a new team."""
    if st.session_state.team_selector:
        selected_team_row = teams_df[teams_df['team_full_name'] == st.session_state.team_selector]
        if not selected_team_row.empty:
            team_id = selected_team_row['team_id'].iloc[0]
            team_abbr = selected_team_row['nhl_team_abbr'].iloc[0]

            st.session_state.selected_team_id = team_id
            st.session_state.current_lineup = get_default_lineup(team_id)
            roster = get_team_roster(team_abbr)
            st.session_state.current_roster = roster
            
            # Fetch ratings for the entire roster at once for efficiency
            if not roster.empty:
                roster_player_ids = roster['player_id'].tolist()
                st.session_state.player_ratings = get_player_ratings(roster_player_ids)

# --- UI RENDERING ---
st.header("1. Select a Team")
st.selectbox(
    "Choose a team to view their default lineup:",
    options=team_names,
    index=None,
    placeholder="Select a team...",
    on_change=on_team_select,
    key='team_selector'
)

def calculate_lss(player_ids: list):
    """Calculates the Line Synergy Score by summing the 'por' ratings."""
    all_ratings_df = st.session_state.player_ratings
    if all_ratings_df.empty or not player_ids:
        return 0

    # Filter for the players currently in the line
    line_ratings_df = all_ratings_df[all_ratings_df['player_id'].isin(player_ids)]
    
    if line_ratings_df.empty:
        return 0
        
    # Sum their 'por' ratings and return the total
    return line_ratings_df['por'].sum()

def render_lineup_ui():
    """Draws the entire lineup editor UI based on data in session_state."""
    st.header("2. Adjust Lines")

    lineup_df = st.session_state.current_lineup
    roster_df = st.session_state.current_roster
    
    if lineup_df.empty or roster_df.empty:
        st.error("No lineup or roster data found for this team.")
        return

    roster_names = roster_df['full_name'].tolist()
    
    line_definitions = { "Line 1": ["LW1", "C1", "RW1"], "Line 2": ["LW2", "C2", "RW2"], "Line 3": ["LW3", "C3", "RW3"], "Line 4": ["LW4", "C4", "RW4"], "Pair 1": ["LD1", "RD1"], "Pair 2": ["LD2", "RD2"], "Pair 3": ["LD3", "RD3"]}

    st.subheader("Even Strength")
    for line_name, positions in line_definitions.items():
        st.markdown(f"**{line_name}**")
        col_widths = [3] * len(positions) + [1.5]
        line_cols = st.columns(col_widths)
        
        current_line_player_ids = []
        for i, pos in enumerate(positions):
            default_player = lineup_df[lineup_df['position_slot'] == pos]
            if not default_player.empty:
                default_name = default_player['full_name'].iloc[0]
                current_line_player_ids.append(default_player['player_id'].iloc[0])
                try:
                    default_index = roster_names.index(default_name)
                except ValueError:
                    default_index = None
            else:
                default_index = None

            # The selectbox no longer needs an on_change callback. Streamlit's natural
            # execution flow will handle re-rendering and recalculating the LSS.
            selected_player = line_cols[i].selectbox(pos, options=roster_names, index=default_index, key=pos)
            
            # Find the ID of the *currently selected* player for the LSS calculation
            if selected_player:
                player_id = roster_df[roster_df['full_name'] == selected_player]['player_id'].iloc[0]
                current_line_player_ids.append(player_id)

        # Calculate and display the LSS for the line
        lss_score = calculate_lss(list(set(current_line_player_ids))) # Use set to remove duplicates
        with line_cols[-1]:
            st.metric("Line Score", f"{lss_score:.2f}", delta_color="off")

if st.session_state.selected_team_id is not None:
    render_lineup_ui()
else:
    st.warning("Please select a team to continue.")
