# main_app.py

import streamlit as st
from streamlit_option_menu import option_menu
import pandas as pd

# Import page rendering functions and queries
from app_pages import dashboard_page, lineup_builder_page, betting_lines_page, database_page
from utils.db_queries import get_schedule, get_teams
from src.ui_components import load_team_data, _apply_saved_state # Add _apply_saved_state
from utils.db_queries import load_dashboard_state, load_simulation_results # Add new imports

st.set_page_config(page_title="NHL Simulator", page_icon="🏒", layout="wide")

# --- INITIALIZE SESSION STATE ---
# These keys are essential for the app to function correctly across pages
if 'selected_game_id' not in st.session_state:
    st.session_state.selected_game_id = None
if 'dashboard_data' not in st.session_state:
    st.session_state['dashboard_data'] = {'home': {}, 'away': {}}
if 'all_sim_results' not in st.session_state:
    st.session_state['all_sim_results'] = {}
if 'loaded_game_id' not in st.session_state:
    st.session_state['loaded_game_id'] = None

# --- TOP BAR NAVIGATION ---
selected_page = option_menu(
    menu_title=None,
    options=["Dashboard", "Market", "Database", "Lineup Builder"],
    icons=["clipboard-data", "cash-coin", "server", "people"], # Updated icons
    menu_icon="cast", default_index=0, orientation="horizontal",
    styles={
        "container": {"padding": "0!important", "background-color": "#0E1117"},
        "icon": {"color": "white", "font-size": "18px"},
        "nav-link": {"font-size": "18px", "text-align": "left", "margin": "0px", "--hover-color": "#31333F"},
        "nav-link-selected": {"background-color": "#02ab21"},
    },
)

# --- GLOBAL FIXTURE SELECTION (MOVED FROM DASHBOARD_PAGE) ---
# This selector now controls the state for both Dashboard and Betting Lines
if selected_page in ["Dashboard", "Market"]:
    schedule_df = get_schedule()
    teams_df = get_teams()

    if not schedule_df.empty:
        display_to_id = pd.Series(schedule_df.game_id.values, index=schedule_df.display_name).to_dict()
        fixture_options = list(display_to_id.keys())

        # Determine the index of the currently selected game for the selectbox
        current_index = None
        if st.session_state.selected_game_id:
            id_to_display = {v: k for k, v in display_to_id.items()}
            display_name = id_to_display.get(st.session_state.selected_game_id)
            if display_name in fixture_options:
                current_index = fixture_options.index(display_name)

        def on_fixture_select():
            """Callback to load all data when a new fixture is selected."""
            selected_display_name = st.session_state.get('fixture_selector')
            if not selected_display_name: return

            selected_id = display_to_id.get(selected_display_name)
            
            # Prevent reloading if the same game is selected
            if selected_id == st.session_state.get('loaded_game_id'):
                return

            st.session_state.selected_game_id = selected_id
            st.session_state['all_sim_results'] = {} # Clear old results

            with st.spinner("Loading fixture data..."):
                game_row = schedule_df[schedule_df['game_id'] == selected_id]
                if not game_row.empty:
                    home_id = game_row['home_team_id'].iloc[0]
                    away_id = game_row['away_team_id'].iloc[0]
                    
                    load_team_data(home_id, 'home', teams_df)
                    load_team_data(away_id, 'away', teams_df)
                    
                    # Try to load saved lineups and results
                    saved_state = load_dashboard_state(selected_id)
                    if saved_state:
                        _apply_saved_state('home', saved_state)
                        _apply_saved_state('away', saved_state)
                        st.toast("Loaded saved lineup configuration!", icon="📝")
                    
                    saved_results = load_simulation_results(selected_id)
                    if saved_results:
                        st.session_state.all_sim_results[selected_id] = saved_results
                        st.toast("Loaded previously saved simulation results!", icon="💾")
                    
                    st.session_state.loaded_game_id = selected_id

        st.selectbox(
            label="Select a Fixture",
            options=fixture_options,
            index=current_index,
            placeholder="Select a fixture to load...",
            key='fixture_selector',
            on_change=on_fixture_select
        )

# --- PAGE RENDERING LOGIC ---
if selected_page == "Dashboard":
    dashboard_page.main()
elif selected_page == "Market":
    betting_lines_page.main()
elif selected_page == "Database":
    database_page.main()
elif selected_page == "Lineup Builder":
    lineup_builder_page.main()