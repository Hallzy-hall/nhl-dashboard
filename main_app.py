# main_app.py

import streamlit as st
from streamlit_option_menu import option_menu
import pandas as pd


# Import page rendering functions and queries
from app_pages import dashboard_page, lineup_builder_page
from utils.db_queries import get_schedule, get_teams
from src.ui_components import load_team_data

st.set_page_config(page_title="NHL Simulator", page_icon="🏒", layout="wide")

# Initialize session state for fixture selection
if 'selected_game_id' not in st.session_state:
    st.session_state.selected_game_id = None

# TOP BAR NAVIGATION
selected_page = option_menu(
    menu_title=None,
    options=["Dashboard", "Lineup Builder"],
    icons=["clipboard-data", "people"],
    menu_icon="cast", default_index=0, orientation="horizontal",
    styles={
        "container": {"padding": "0!important", "background-color": "#0E1117"},
        "icon": {"color": "white", "font-size": "18px"},
        "nav-link": {"font-size": "18px", "text-align": "left", "margin": "0px", "--hover-color": "#31333F"},
        "nav-link-selected": {"background-color": "#02ab21"},
    },
)

# FIXTURE SELECTION LOGIC
if selected_page == "Dashboard":
    schedule_df = get_schedule()
    teams_df = get_teams()

    # --- MODIFIED LOGIC: Pre-format options and create a lookup dictionary ---
    if not schedule_df.empty:
        # Create a dictionary to map the display name back to the game_id
        display_to_id = pd.Series(schedule_df.game_id.values, index=schedule_df.display_name).to_dict()
        # Create a simple list of strings for the options
        fixture_options = list(display_to_id.keys())

        def on_fixture_select():
            """Callback to load teams when a fixture is selected."""
            # The selected value is now the display name string
            selected_display_name = st.session_state.get('fixture_selector')
            if not selected_display_name:
                return

            # Use the dictionary to look up the corresponding game_id
            selected_id = display_to_id.get(selected_display_name)
            st.session_state.selected_game_id = selected_id
            
            selected_game = schedule_df[schedule_df['game_id'] == selected_id].iloc[0]
            home_id = selected_game['home_team_id']
            away_id = selected_game['away_team_id']

            load_team_data(home_id, 'home', teams_df)
            load_team_data(away_id, 'away', teams_df)

        # --- Simplified st.selectbox call ---
        st.selectbox(
            label="Select a Fixture",
            options=fixture_options, # Use our simple list of strings
            index=None,
            placeholder="Select a fixture to load...",
            key='fixture_selector',
            on_change=on_fixture_select
        )

# PAGE RENDERING
if selected_page == "Dashboard":
    dashboard_page.main()
elif selected_page == "Lineup Builder":
    lineup_builder_page.main()