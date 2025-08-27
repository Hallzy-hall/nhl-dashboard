# /app_pages/2_📊_Lineup_Builder.py

import streamlit as st
import pandas as pd
from src.definitions import all_definitions
from utils.db_queries import get_teams, get_default_lineup, get_team_roster, get_player_ratings, get_coach_by_team_id, get_default_pp_lineup, get_default_pk_lineup
from src.ui_components import render_lineup_ui
from src.data_processing import run_toi_calculation
from src.calculations import calculate_line_score

def main():
    st.title("Lineup Builder & TOI Simulator")

    # --- SESSION STATE INITIALIZATION ---
    if 'selected_team_id' not in st.session_state:
        st.session_state.selected_team_id = None
        st.session_state.current_lineup = pd.DataFrame()
        st.session_state.pp_lineup = pd.DataFrame()
        st.session_state.pk_lineup = pd.DataFrame()
        st.session_state.current_roster = pd.DataFrame()
        st.session_state.player_ratings = pd.DataFrame()
        st.session_state.coach_data = None
        st.session_state.toi_results = {}

    # --- DATA LOADING ---
    teams_df = get_teams()
    team_names = teams_df['team_full_name'].tolist() if not teams_df.empty else []

    def on_team_select():
        st.session_state.toi_results = {}
        for line_name, positions in all_definitions.items():
            widget_key_prefix = line_name.replace(' ', '_')
            for pos in positions:
                widget_key = f"{widget_key_prefix}_{pos.replace(' ', '_')}"
                if widget_key in st.session_state:
                    del st.session_state[widget_key]

        if st.session_state.team_selector:
            selected_team_row = teams_df[teams_df['team_full_name'] == st.session_state.team_selector]
            if not selected_team_row.empty:
                team_id = int(selected_team_row['team_id'].iloc[0])
                team_abbr = selected_team_row['nhl_team_abbr'].iloc[0]
                st.session_state.selected_team_id = team_id
                st.session_state.current_lineup = get_default_lineup(team_id)
                st.session_state.pp_lineup = get_default_pp_lineup(team_id)
                st.session_state.pk_lineup = get_default_pk_lineup(team_id)
                roster = get_team_roster(team_abbr)
                st.session_state.current_roster = roster
                st.session_state.coach_data = get_coach_by_team_id(team_id)

                if not roster.empty:
                    roster_player_ids = roster['player_id'].tolist()
                    st.session_state.player_ratings = get_player_ratings(roster_player_ids)
                    run_toi_calculation(pim_for=8, pim_against=6)

    # --- MAIN EXECUTION BLOCK ---
    st.header("1. Select Team")
    st.selectbox(
        "Choose a team to build their lineup:",
        options=team_names, index=None, placeholder="Select a team...",
        on_change=on_team_select, key='team_selector'
    )

    if st.session_state.selected_team_id is not None:
        if st.session_state.get('coach_data'):
            coach_name = st.session_state.coach_data.get('coach', 'N/A')
            team_color = "#888888"
            selected_team_name = st.session_state.get('team_selector')
            if selected_team_name:
                team_row = teams_df[teams_df['team_full_name'] == selected_team_name]
                if not team_row.empty and 'team_color_primary' in team_row.columns and pd.notna(team_row['team_color_primary'].iloc[0]):
                    team_color = team_row['team_color_primary'].iloc[0]
                faded_color = f"{team_color}40"
                st.markdown(f'''<style>.coach-box {{ background-color: {faded_color}; border: 1px solid {team_color}; border-radius: 0.5rem; padding: 0.5rem 1rem; margin-bottom: 1rem; }}</style>''', unsafe_allow_html=True)
                st.markdown(f'<div class="coach-box"><strong>Coach:</strong> {coach_name}</div>', unsafe_allow_html=True)

        render_lineup_ui()

        st.header("3. Simulation Inputs")
        col1, col2 = st.columns(2)

        sim_pim_for = col1.number_input("Team Penalty Minutes (PIM)", min_value=0, value=8, step=2, key='sim_pim_for')
        sim_pim_against = col2.number_input("Opponent Penalty Minutes (PIM)", min_value=0, value=6, step=2, key='sim_pim_against')

        if st.button("Update TOI Projections"):
            run_toi_calculation(pim_for=sim_pim_for, pim_against=sim_pim_against)
            st.rerun()
    else:
        st.info("Please select a team to continue.")