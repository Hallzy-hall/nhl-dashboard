# app_pages/dashboard_page.py

import streamlit as st
import pandas as pd
import numpy as np
from utils.db_queries import (
    get_teams, load_simulation_results, save_simulation_results,
    load_dashboard_state, save_dashboard_state, get_schedule
)
from src.ui_components import render_team_ui, load_team_data, _apply_saved_state
from src.data_processing import structure_dashboard_data_for_sim
from src.simulation_engine import run_multiple_simulations
from src.calculations import calculate_betting_odds


# --- HELPER FUNCTIONS ---

def _prepare_display_df(df: pd.DataFrame, state: str, per_60: bool = False):
    """
    Helper function to select and rename columns for a specific game state display.
    """
    if df.empty:
        return pd.DataFrame()

    base_cols = ['Player', 'player_id']
    stat_cols = ['TOI', 'Goals', 'Assists', 'Shots', 'Shot Attempts', 'Blocks', '+/-', 'Penalty Minutes']

    source_cols = [f"{col}_Total" for col in stat_cols]
    if state != "Total":
        source_cols = [f"{col}_{state}" for col in stat_cols]

    display_cols_map = {source: dest for source, dest in zip(source_cols, stat_cols) if source in df.columns}
    if not display_cols_map:
        return pd.DataFrame(columns=base_cols + stat_cols)

    final_df = df[base_cols + list(display_cols_map.keys())].copy()
    final_df.rename(columns=display_cols_map, inplace=True)

    if per_60:
        toi_col = 'TOI'
        if toi_col in final_df.columns and final_df[toi_col].sum() > 0:
            rate_stats = [col for col in stat_cols if col not in ['TOI', '+/-'] and col in final_df.columns]
            mask = final_df[toi_col] > 0
            for stat in rate_stats:
                final_df[stat] = np.where(mask, (final_df[stat] / final_df[toi_col]) * 60, 0)
            final_df = final_df.round(2)
    return final_df

def _display_stats_for_tab(results, state_key, per_60=False):
    """Renders the team totals and player stats for a given game state."""
    home_name = st.session_state.dashboard_data['home'].get('team_name', 'Home')
    away_name = st.session_state.dashboard_data['away'].get('team_name', 'Away')

    per_60_label = " (per 60)" if per_60 else ""
    state_label_map = {"ES": " (5v5)", "PP": " (PP)", "PK": " (PK)", "Total": ""}
    state_label = state_label_map.get(state_key, "")

    st.subheader(f"{home_name}{state_label}{per_60_label}")
    st.dataframe(results['home_total'], use_container_width=True, hide_index=True)
    st.dataframe(_prepare_display_df(results['home_players'], state_key, per_60), use_container_width=True, hide_index=True)
    st.divider()
    st.subheader(f"{away_name}{state_label}{per_60_label}")
    st.dataframe(results['away_total'], use_container_width=True, hide_index=True)
    st.dataframe(_prepare_display_df(results['away_players'], state_key, per_60), use_container_width=True, hide_index=True)

# --- MAIN PAGE FUNCTION ---
def main():
    """Renders the main dashboard page with lineup and output tabs."""
    if 'dashboard_data' not in st.session_state:
        st.session_state['dashboard_data'] = {
            'home': {},
            'away': {}
        }
    if 'all_sim_results' not in st.session_state:
        st.session_state['all_sim_results'] = {}
    if 'loaded_game_id' not in st.session_state:
        st.session_state['loaded_game_id'] = None
    
    # --- FIX: Ensure schedule is loaded to look up team IDs ---
    if 'schedule' not in st.session_state:
        st.session_state.schedule = get_schedule()
    schedule_df = st.session_state.schedule

    # --- REVISED UNIFIED FIXTURE LOADING LOGIC ---
    current_game_id = st.session_state.get('selected_game_id')
    if current_game_id and current_game_id != st.session_state.get('loaded_game_id'):
        with st.spinner("Loading fixture data..."):
            
            game_row = schedule_df[schedule_df['game_id'] == current_game_id]
            
            # --- FIX: Look up team IDs from the schedule DataFrame ---
            if not game_row.empty:
                home_team_id = game_row['home_team_id'].iloc[0]
                away_team_id = game_row['away_team_id'].iloc[0]
                teams_df = get_teams()

                # 1. Load default data for both teams
                load_team_data(home_team_id, 'home', teams_df)
                load_team_data(away_team_id, 'away', teams_df)

                # 2. Check for and apply saved lineup configurations
                saved_state = load_dashboard_state(current_game_id)
                if saved_state:
                    _apply_saved_state('home', saved_state)
                    _apply_saved_state('away', saved_state)
                    st.toast("Loaded saved lineup configuration!", icon="📝")

                # 3. Check for and apply saved simulation results
                saved_results = load_simulation_results(current_game_id)
                if saved_results:
                    st.session_state.all_sim_results[current_game_id] = saved_results
                    st.toast("Loaded previously saved simulation results!", icon="💾")

                # 4. Mark this game as loaded for the current session
                st.session_state.loaded_game_id = current_game_id
            else:
                st.warning("Selected game not found in schedule.")

    # Get the results for the currently selected game
    results_for_current_game = st.session_state.all_sim_results.get(current_game_id)

    tab1, tab2, tab3, tab4 = st.tabs(["Lineups", "Output", "per/60", "Player Level"])

    with tab1:
        action_col, odds_col = st.columns([1, 3])

        with action_col:
            if st.button("▶️ Run Simulation", use_container_width=True, type="primary"):
                if not current_game_id:
                    st.warning("Please select a fixture before running a simulation.")
                else:
                    home_lineup_data = structure_dashboard_data_for_sim('home')
                    away_lineup_data = structure_dashboard_data_for_sim('away')
                    if not home_lineup_data or not away_lineup_data:
                        st.error("Lineups are incomplete.")
                    else:
                        home_coach = st.session_state.dashboard_data['home'].get('coach_data')
                        away_coach = st.session_state.dashboard_data['away'].get('coach_data')
                        home_goalie = st.session_state.dashboard_data['home'].get('starting_goalie')
                        away_goalie = st.session_state.dashboard_data['away'].get('starting_goalie')

                        if home_goalie is None or away_goalie is None:
                            st.error("A starting goalie was not found for one or both teams.")
                        else:
                            # Save dashboard state before simulating
                            save_dashboard_state(current_game_id, 'home', st.session_state.dashboard_data['home'])
                            save_dashboard_state(current_game_id, 'away', st.session_state.dashboard_data['away'])

                            home_sim_data = {'lineup': pd.DataFrame(home_lineup_data), 'coach': home_coach, 'goalie': home_goalie}
                            away_sim_data = {'lineup': pd.DataFrame(away_lineup_data), 'coach': away_coach, 'goalie': away_goalie}

                            with st.spinner("Running simulations..."):
                                results = run_multiple_simulations(100, home_sim_data, away_sim_data)
                                st.session_state.all_sim_results[current_game_id] = results
                                save_simulation_results(current_game_id, results)
                                st.success("Simulations Complete and Configuration Saved!")
                                st.rerun()

        with odds_col:
            if results_for_current_game and 'all_game_scores' in results_for_current_game:
                betting_odds = calculate_betting_odds(results_for_current_game['all_game_scores'])

                if betting_odds:
                    home_name = st.session_state.dashboard_data['home'].get('team_name', 'Home').split()[-1]
                    away_name = st.session_state.dashboard_data['away'].get('team_name', 'Away').split()[-1]

                    c1, c2, c3 = st.columns(3)

                    with c1:
                        st.markdown(f"**Moneyline**")
                        st.markdown(f"{home_name}: `{betting_odds['moneyline']['home']:+}`")
                        st.markdown(f"{away_name}: `{betting_odds['moneyline']['away']:+}`")
                    with c2:
                        pl = betting_odds['puckline']
                        st.markdown(f"**Puckline**")
                        st.markdown(f"{home_name}: `{pl['home_spread']:+.1f}` `{pl['home_odds']:+}`")
                        st.markdown(f"{away_name}: `{pl['away_spread']:+.1f}` `{pl['away_odds']:+}`")
                    with c3:
                        total = betting_odds['total']
                        st.markdown(f"**Total**")
                        st.markdown(f"Over {total['line']:.1f}: `{total['over']}`")
                        st.markdown(f"Under {total['line']:.1f}: `{total['under']}`")

        st.divider()
        teams_df = get_teams()
        render_team_ui('home', teams_df)
        st.divider()
        render_team_ui('away', teams_df)

    with tab2:
        st.header("Raw Count Outputs")
        if results_for_current_game:
            total_tab, es_tab, pp_tab, pk_tab = st.tabs(["Total", "Even Strength", "Power Play", "Penalty Kill"])
            with total_tab: _display_stats_for_tab(results_for_current_game, "Total")
            with es_tab: _display_stats_for_tab(results_for_current_game, "ES")
            with pp_tab: _display_stats_for_tab(results_for_current_game, "PP")
            with pk_tab: _display_stats_for_tab(results_for_current_game, "PK")
        else:
            st.info("Run a simulation to see the output here.")

    with tab3:
        st.header("Per/60 Minute Outputs")
        if results_for_current_game:
            total_tab, es_tab, pp_tab, pk_tab = st.tabs(["Total", "Even Strength", "Power Play", "Penalty Kill"])
            with total_tab: _display_stats_for_tab(results_for_current_game, "Total", per_60=True)
            with es_tab: _display_stats_for_tab(results_for_current_game, "ES", per_60=True)
            with pp_tab: _display_stats_for_tab(results_for_current_game, "PP", per_60=True)
            with pk_tab: _display_stats_for_tab(results_for_current_game, "PK", per_60=True)
        else:
            st.info("Run a simulation to see the per/60 output here.")

    with tab4:
        st.header("Player Level Validation Stats (Simulated per 60 min)")
        if results_for_current_game:
            validation_stats_options = [
                'Sim_iHDCF_per_60_ES', 'Sim_iMDCF_per_60_ES', 'Sim_iLDCF_per_60_ES', 'Sim_OnIce_HDCA_per_60_ES',
                'Sim_OnIce_MDCA_per_60_ES', 'Sim_OnIce_LDCA_per_60_ES', 'Sim_xG_for_per_60_ES',
                'Sim_ReboundsCreated_per_60_ES', 'Sim_PenaltiesDrawn_per_60_ES', 'Sim_ControlledEntries_per_60_ES',
                'Sim_ControlledExits_per_60_ES', 'Sim_iHDCF_per_60_PP', 'Sim_iMDCF_per_60_PP', 'Sim_iLDCF_per_60_PP',
                'Sim_xG_for_per_60_PP', 'Sim_ReboundsCreated_per_60_PP', 'Sim_PenaltiesDrawn_per_60_PP',
                'Sim_ControlledEntries_per_60_PP', 'Sim_OnIce_HDCA_per_60_PK', 'Sim_OnIce_MDCA_per_60_PK',
                'Sim_OnIce_LDCA_per_60_PK', 'Sim_PK_Clears_per_60_PK'
            ]

            default_selection = [
                'Sim_iHDCF_per_60_ES', 'Sim_xG_for_per_60_ES',
                'Sim_OnIce_HDCA_per_60_PK', 'Sim_ControlledEntries_per_60_ES'
            ]
            selected_stats = st.multiselect(
                "Select validation stats to display:",
                options=sorted(validation_stats_options),
                default=default_selection
            )

            base_cols = ['Player', 'TOI_Total']
            home_df = results_for_current_game['home_players']
            away_df = results_for_current_game['away_players']

            st.subheader(st.session_state.dashboard_data['home'].get('team_name', 'Home'))
            st.dataframe(home_df[base_cols + selected_stats], use_container_width=True, hide_index=True)

            st.divider()

            st.subheader(st.session_state.dashboard_data['away'].get('team_name', 'Away'))
            st.dataframe(away_df[base_cols + selected_stats], use_container_width=True, hide_index=True)
        else:
            st.info("Run a simulation to see the Player Level validation data here.")