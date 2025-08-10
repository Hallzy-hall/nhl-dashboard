import streamlit as st
import pandas as pd

# --- PAGE CONFIGURATION ---
# Use st.set_page_config() as the first Streamlit command in your script.
st.set_page_config(
    page_title="NHL Lineup Simulation Tool",
    page_icon="🏒",
    layout="wide" # "wide" or "centered"
)

# --- MOCK DATA (Replace with your Supabase calls) ---
# For now, we'll use simple lists. Later, you'll fetch this from Supabase.
mock_players = ["Connor McDavid", "Auston Matthews", "Nathan MacKinnon", "Cale Makar", "Igor Shesterkin", "Sidney Crosby"]
mock_teams = ["Edmonton Oilers", "Toronto Maple Leafs"]

# --- SIDEBAR ---
# A sidebar is a great place for global controls
with st.sidebar:
    st.header("Game Setup")
    home_team = st.selectbox("Home Team", options=mock_teams)
    away_team = st.selectbox("Away Team", options=mock_teams, index=1)
    
    st.divider()
    
    st.header("Player Editor")
    player_to_edit = st.selectbox("Select Player", options=mock_players)
    if st.button(f"Edit {player_to_edit}'s Ratings"):
        # Placeholder for the modal/pop-up functionality
        st.info(f"Pop-up for editing {player_to_edit} would appear here.")
        
# --- MAIN PAGE ---
st.title("Lineup Builder")
st.write(f"Building lines for **{home_team}** vs. **{away_team}**")

# Create a two-column layout for Even Strength and Special Teams
col_ev, col_pp = st.columns(2)

with col_ev:
    st.subheader("Even Strength")
    
    # Example for Line 1
    st.markdown("**Line 1**")
    line1_cols = st.columns(3)
    line1_cols[0].selectbox("LW", options=mock_players, key="l1_lw", help="Select the Left Wing for Line 1")
    line1_cols[1].selectbox("C", options=mock_players, key="l1_c", help="Select the Center for Line 1")
    line1_cols[2].selectbox("RW", options=mock_players, key="l1_rw", help="Select the Right Wing for Line 1")
    
    # Add more lines as needed...
    st.markdown("**Line 2**") # ...etc

with col_pp:
    st.subheader("Special Teams")
    
    # Example for PP1
    st.markdown("**Power Play 1**")
    pp1_cols = st.columns(3)
    pp1_cols[0].selectbox("F1", options=mock_players, key="pp1_f1")
    pp1_cols[1].selectbox("F2", options=mock_players, key="pp1_f2")
    pp1_cols[2].selectbox("F3", options=mock_players, key="pp1_f3")
    # Add defensemen...
    
# --- SIMULATION ---
st.divider()
st.header("Simulation Control")

if st.button("▶️ Run Game Simulation", type="primary", use_container_width=True):
    with st.spinner("Running simulation... please wait."):
        # This is where you will call your Python simulation model
        # For now, we'll just show some mock results.
        import time
        time.sleep(3) # Simulate a long calculation
        
        st.success("Simulation Complete!")
        
        # Display results
        res_cols = st.columns(3)
        res_cols[0].metric(label=f"{home_team} Win Probability", value="58.3%")
        res_cols[1].metric(label=f"{away_team} Win Probability", value="41.7%")
        res_cols[2].metric(label="Predicted Score", value="4-2")