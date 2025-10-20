import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.colors
import matplotlib.cm
import json

# --- Main Application Imports ---
from src.data_processing import (
    load_simulation_results, save_simulation_results,
    structure_dashboard_data_for_sim, load_baseline_results
)
from utils.db_queries import (
    get_teams,
    load_dashboard_state, save_dashboard_state, get_schedule,
    get_player_shooting_actuals, get_player_possession_actuals,
    get_player_transition_actuals, get_player_defense_actuals,
    get_player_special_teams_actuals
)
from src.ui_components import render_team_ui, load_team_data, _apply_saved_state
from src.cloud_engine import run_cloud_simulations
from src.calculations import calculate_betting_odds, calculate_player_props
from src.simulation_engine import _finalize_player_stats

# --- UPDATED: Import the ResultAdjuster ---
from src.results_adjuster import ResultAdjuster


# ==============================================================================
# --- HELPER & RENDER FUNCTIONS (Unchanged) ---
# ==============================================================================
def style_diff_by_percent(row):
    PERCENT_CAP = 0.30
    green_cmap = matplotlib.cm.get_cmap('Greens')
    red_cmap = matplotlib.cm.get_cmap('Reds')
    styles = [''] * len(row)
    for i, col_name in enumerate(row.index):
        if col_name.endswith('_Diff'):
            actual_col_name = col_name.replace('_Diff', '_Actual')
            diff_val = row[col_name]
            actual_val = row.get(actual_col_name)
            if pd.isna(actual_val) or actual_val == 0:
                continue
            percent_diff = diff_val / actual_val
            invert_color = any(x in col_name for x in ['CA/60', 'GvA/60', 'Pen/60'])
            if (percent_diff > 0 and not invert_color) or (percent_diff < 0 and invert_color):
                norm_val = min(abs(percent_diff), PERCENT_CAP) / PERCENT_CAP
                color_map_val = 0.3 + (0.7 * norm_val)
                rgba_color = green_cmap(color_map_val)
            elif (percent_diff < 0 and not invert_color) or (percent_diff > 0 and invert_color):
                norm_val = min(abs(percent_diff), PERCENT_CAP) / PERCENT_CAP
                color_map_val = 0.3 + (0.7 * norm_val)
                rgba_color = red_cmap(color_map_val)
            else:
                continue
            hex_color = matplotlib.colors.to_hex(rgba_color)
            styles[i] = f'background-color: {hex_color}'
    return styles

def _prepare_display_df(df: pd.DataFrame, state: str, per_60: bool = False):
    df = pd.DataFrame(df)
    if df.empty: return pd.DataFrame()
    final_stat_cols = ['TOI', 'Goals', 'Assists', 'Shots', 'Shot Attempts', 'Blocks', '+/-', 'Penalty Minutes']
    if state == "Total": source_cols = [f"{col}_Total" for col in final_stat_cols]
    else: source_cols = [f"{col}_{state}" for col in final_stat_cols]
    display_cols_map = {source: dest for source, dest in zip(source_cols, final_stat_cols) if source in df.columns}
    base_cols = ['Player', 'player_id']
    cols_to_select = [col for col in base_cols + list(display_cols_map.keys()) if col in df.columns]
    if not cols_to_select: return pd.DataFrame()
    final_df = df[cols_to_select].copy()
    final_df.rename(columns=display_cols_map, inplace=True)
    if 'TOI' in final_df.columns and final_df['TOI'].sum() > 0:
        if per_60:
            rate_stats = [col for col in final_stat_cols if col not in ['TOI', '+/-'] and col in final_df.columns]
            mask = final_df['TOI'] > 0
            for stat in rate_stats:
                if stat in final_df.columns:
                    final_df[stat] = np.where(mask, (final_df[stat] / final_df['TOI']) * 3600, 0)
        final_df['TOI'] = final_df['TOI'] / 60
    return final_df.round(2)

def _display_stats_for_tab(results, state_key, per_60=False):
    if not results:
        st.info("Run a simulation to see the output here.")
        return
    
    raw_results = results.get('simulation_outputs', {}).get('raw_data', {})
    if not raw_results:
        st.warning("Raw simulation data not found in the payload.")
        return

    home_name = st.session_state.dashboard_data['home'].get('team_name', 'Home')
    away_name = st.session_state.dashboard_data['away'].get('team_name', 'Away')
    per_60_label = " (per 60)" if per_60 else ""
    state_label_map = {"ES": " (5v5)", "PP": " (PP)", "PK": " (PK)", "Total": ""}
    state_label = state_label_map.get(state_key, "")

    st.subheader(f"{home_name}{state_label}{per_60_label}")
    st.dataframe(pd.DataFrame(raw_results.get('home_total', [])), use_container_width=True, hide_index=True)
    st.dataframe(_prepare_display_df(raw_results.get('home_players', []), state_key, per_60), use_container_width=True, hide_index=True)
    st.divider()
    st.subheader(f"{away_name}{state_label}{per_60_label}")
    st.dataframe(pd.DataFrame(raw_results.get('away_total', [])), use_container_width=True, hide_index=True)
    st.dataframe(_prepare_display_df(raw_results.get('away_players', []), state_key, per_60), use_container_width=True, hide_index=True)

def render_shooting_validation_tab(results):
    pass
def render_possession_validation_tab(results):
    pass
def render_transition_validation_tab(results):
    pass
def render_defense_validation_tab(results):
    pass
def render_special_teams_validation_tab(results):
    pass


# ==============================================================================
# --- MAIN APPLICATION LOGIC ---
# ==============================================================================

def main():
    if 'dashboard_data' not in st.session_state:
        st.session_state['dashboard_data'] = {'home': {}, 'away': {}}
    if 'all_sim_results' not in st.session_state:
        st.session_state['all_sim_results'] = {}
    if 'loaded_game_id' not in st.session_state:
        st.session_state['loaded_game_id'] = None
    if 'schedule' not in st.session_state:
        st.session_state.schedule = get_schedule()
    
    schedule_df = st.session_state.schedule
    current_game_id = st.session_state.get('selected_game_id')

    if current_game_id and current_game_id != st.session_state.get('loaded_game_id'):
        with st.spinner("Loading fixture data..."):
            game_row = schedule_df[schedule_df['game_id'] == current_game_id]
            if not game_row.empty:
                home_team_id = game_row['home_team_id'].iloc[0]
                away_team_id = game_row['away_team_id'].iloc[0]
                teams_df = get_teams()
                load_team_data(home_team_id, 'home', teams_df)
                load_team_data(away_team_id, 'away', teams_df)
                saved_state = load_dashboard_state(current_game_id)
                if saved_state:
                    _apply_saved_state('home', saved_state)
                    _apply_saved_state('away', saved_state)
                    st.toast("Loaded saved lineup configuration!", icon="📝")
                
                saved_results = load_simulation_results(current_game_id)
                if saved_results:
                    st.session_state.all_sim_results[current_game_id] = saved_results
                    st.toast("Loaded previously saved simulation results!", icon="💾")
                st.session_state.loaded_game_id = current_game_id
            else:
                st.warning("Selected game not found in schedule.")
    
    results_for_current_game = st.session_state.all_sim_results.get(current_game_id)
   
    tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8, tab9 = st.tabs(["Lineups", "Output", "per/60", "Player Level", "Shooting", "Possession", "Transition", "Defense", "Specialty Teams"])
    
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
                        home_sim_data = {
                            'lineup': pd.DataFrame(home_lineup_data), 
                            'coach': st.session_state.dashboard_data['home'].get('coach_data'), 
                            'goalie': st.session_state.dashboard_data['home'].get('starting_goalie'),
                            'lines': st.session_state.dashboard_data['home'].get('lines', {}),
                            'id': st.session_state.dashboard_data['home'].get('team_id')
                        }
                        away_sim_data = {
                            'lineup': pd.DataFrame(away_lineup_data), 
                            'coach': st.session_state.dashboard_data['away'].get('coach_data'), 
                            'goalie': st.session_state.dashboard_data['away'].get('starting_goalie'),
                            'lines': st.session_state.dashboard_data['away'].get('lines', {}),
                            'id': st.session_state.dashboard_data['away'].get('team_id')
                        }
                        sim_input_data = {'home': home_sim_data, 'away': away_sim_data}

                        save_dashboard_state(current_game_id, 'home', st.session_state.dashboard_data['home'])
                        save_dashboard_state(current_game_id, 'away', st.session_state.dashboard_data['away'])
                        
                        is_initial_sim = st.session_state.sim_mode_toggle
                        final_results_payload = None

                        with st.spinner("Running simulations..."):
                            if is_initial_sim:
                                raw_results = run_cloud_simulations(1000, home_sim_data, away_sim_data)
                                main_odds = calculate_betting_odds(raw_results.get('all_game_scores', []))
                                all_players_df = pd.concat([pd.DataFrame(raw_results['home_players']), pd.DataFrame(raw_results['away_players'])])
                                player_props = calculate_player_props(all_players_df, {}, {})
                                final_results_payload = {"raw_data": raw_results, "main_markets": main_odds, "player_props": player_props}
                                save_simulation_results(current_game_id, final_results_payload, sim_input_data, is_baseline=True)
                            
                            else: # --- NEW, FAST SIM LOGIC ---
                                baseline_payload = load_baseline_results(current_game_id)
                                
                                if not baseline_payload:
                                    st.error("No baseline simulation found. Please run an 'Initial Sim' first before using the fast adjuster.")
                                    return
                                
                                # The baseline payload contains everything needed
                                baseline_sim_inputs = baseline_payload['simulation_inputs']
                                baseline_raw_results = baseline_payload['simulation_outputs']['raw_data']
                                
                                # Convert DataFrames from JSON strings back to DataFrames
                                baseline_sim_inputs['home']['lineup'] = pd.DataFrame(baseline_sim_inputs['home']['lineup'])
                                baseline_sim_inputs['away']['lineup'] = pd.DataFrame(baseline_sim_inputs['away']['lineup'])
                                baseline_raw_results['home_players'] = pd.DataFrame(baseline_raw_results['home_players'])
                                baseline_raw_results['away_players'] = pd.DataFrame(baseline_raw_results['away_players'])
                                baseline_raw_results['home_goalie'] = pd.DataFrame(baseline_raw_results['home_goalie'])
                                baseline_raw_results['away_goalie'] = pd.DataFrame(baseline_raw_results['away_goalie'])

                                # Initialize the adjuster with the full baseline payload and the new tweaked inputs
                                adjuster = ResultAdjuster(baseline_payload=baseline_payload, new_sim_data=home_sim_data)
                                
                                # This is a near-instant calculation
                                final_raw_results = adjuster.run()

                                # Recalculate odds and props based on the newly adjusted results
                                main_odds = calculate_betting_odds(final_raw_results.get('all_game_scores', baseline_raw_results.get('all_game_scores', [])))
                                all_players_df = pd.concat([final_raw_results['home_players'], final_raw_results['away_players']])
                                player_props = calculate_player_props(all_players_df, {}, {})
                                final_results_payload = {"raw_data": final_raw_results, "main_markets": main_odds, "player_props": player_props}
                                save_simulation_results(current_game_id, final_results_payload, sim_input_data, is_baseline=False)

                        if final_results_payload:
                            st.session_state.all_sim_results[current_game_id] = {'simulation_outputs': final_results_payload}
                            st.success("Simulations Complete and Results Saved!")
                            st.rerun()

            st.toggle("Initial Sim", key="sim_mode_toggle", value=True, help="ON: Run the full, foundational Poisson simulation. OFF: Run the fast, iterative result adjuster.")

        with odds_col:
            if results_for_current_game and 'simulation_outputs' in results_for_current_game:
                betting_odds = results_for_current_game['simulation_outputs'].get('main_markets')
                if betting_odds:
                    home_name = st.session_state.dashboard_data['home'].get('team_name', 'Home').split()[-1]
                    away_name = st.session_state.dashboard_data['away'].get('team_name', 'Away').split()[-1]
                    c1, c2, c3 = st.columns(3)
                    with c1: st.markdown(f"**Moneyline**"); st.markdown(f"{home_name}: `{betting_odds['moneyline']['home']:+}`"); st.markdown(f"{away_name}: `{betting_odds['moneyline']['away']:+}`")
                    with c2: pl = betting_odds['puckline']; st.markdown(f"**Puckline**"); st.markdown(f"{home_name}: `{pl['home_spread']:+.1f}` `{pl['home_odds']:+}`"); st.markdown(f"{away_name}: `{pl['away_spread']:+.1f}` `{pl['away_odds']:+}`")
                    with c3: total = betting_odds['total']; st.markdown(f"**Total**"); st.markdown(f"Over {total['line']:.1f}: `{total['over']:+}`"); st.markdown(f"Under {total['line']:.1f}: `{total['under']:+}`")
        
        st.divider()
        teams_df = get_teams()
        render_team_ui('home', teams_df)
        st.divider()
        render_team_ui('away', teams_df)
    
    with tab2: _display_stats_for_tab(results_for_current_game, "Total")
    with tab3: _display_stats_for_tab(results_for_current_game, "ES")
    with tab4: _display_stats_for_tab(results_for_current_game, "PP")
    with tab5: _display_stats_for_tab(results_for_current_game, "PK")
    with tab6: render_shooting_validation_tab(results_for_current_game)
    with tab7: render_possession_validation_tab(results_for_current_game)
    with tab8: render_transition_validation_tab(results_for_current_game)
    with tab9: render_defense_validation_tab(results_for_current_game)

if __name__ == "__main__":
    main()
