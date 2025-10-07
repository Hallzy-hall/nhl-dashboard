import streamlit as st
import pandas as pd
import numpy as np
# Add new imports for custom styling
import matplotlib.colors
import matplotlib.cm
# --- MODIFIED: Import from data_processing instead of db_queries ---
from src.data_processing import (
    load_simulation_results, save_simulation_results,
    structure_dashboard_data_for_sim
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
# --- MODIFIED: Import both odds calculation functions ---
from src.calculations import calculate_betting_odds, calculate_player_props

# --- HELPER FUNCTIONS ---

def style_diff_by_percent(row):
    PERCENT_CAP = 0.30
    green_cmap = matplotlib.cm.get_cmap('Greens')
    red_cmap = matplotlib.cm.get_cmap('Reds')
    styles = [''] * len(row)
    for i, col_name in enumerate(row.index):
        if col_name.endswith('_Diff'):
            actual_col_name = col_name.replace('_Diff', '_Actual')
            diff_val = row[col_name]
            actual_val = row.get(actual_col_name) # Use .get() for safety
            if pd.isna(actual_val) or actual_val == 0:
                continue
            percent_diff = diff_val / actual_val

            # Invert colors for defensive stats where lower is better
            invert_color = any(x in col_name for x in ['CA/60', 'GvA/60', 'Pen/60'])

            if (percent_diff > 0 and not invert_color) or (percent_diff < 0 and invert_color): # Sim is higher (green)
                norm_val = min(abs(percent_diff), PERCENT_CAP) / PERCENT_CAP
                color_map_val = 0.3 + (0.7 * norm_val)
                rgba_color = green_cmap(color_map_val)
            elif (percent_diff < 0 and not invert_color) or (percent_diff > 0 and invert_color): # Sim is lower (red)
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

    if 'TOI' in final_df.columns:
        if per_60:
            rate_stats = [col for col in stat_cols if col not in ['TOI', '+/-'] and col in final_df.columns]
            mask = final_df['TOI'] > 0
            for stat in rate_stats:
                final_df[stat] = np.where(mask, (final_df[stat] / final_df['TOI']) * 3600, 0)

        final_df['TOI'] = final_df['TOI'] / 60

    return final_df.round(2)

def _display_stats_for_tab(results, state_key, per_60=False):
    if not results:
        st.info("Run a simulation to see the output here.")
        return
        
    raw_results = results.get('raw_data', {})
    if not raw_results:
        st.warning("Raw simulation data not found.")
        return

    home_name = st.session_state.dashboard_data['home'].get('team_name', 'Home')
    away_name = st.session_state.dashboard_data['away'].get('team_name', 'Away')
    per_60_label = " (per 60)" if per_60 else ""
    state_label_map = {"ES": " (5v5)", "PP": " (PP)", "PK": " (PK)", "Total": ""}
    state_label = state_label_map.get(state_key, "")

    # Display Home Team Stats
    st.subheader(f"{home_name}{state_label}{per_60_label}")
    st.dataframe(raw_results['home_total'], use_container_width=True, hide_index=True)
    st.dataframe(_prepare_display_df(raw_results['home_players'], state_key, per_60), use_container_width=True, hide_index=True)
    st.divider()

    # Display Away Team Stats - CORRECTED SECTION
    st.subheader(f"{away_name}{state_label}{per_60_label}")
    st.dataframe(raw_results['away_total'], use_container_width=True, hide_index=True)
    st.dataframe(_prepare_display_df(raw_results['away_players'], state_key, per_60), use_container_width=True, hide_index=True)

def render_shooting_validation_tab(results):
    if not results:
        st.info("Run a simulation to see the shooting validation data here.")
        return

    raw_results = results.get('raw_data')
    if not raw_results:
        st.warning("Simulation results are present, but raw data is missing.")
        return
        
    st.header("Shooting Performance (5v5): SvA Per 60 Mins")
    
    # --- FIX: Convert lists to DataFrames ---
    home_sim_df = pd.DataFrame(raw_results['home_players'])
    away_sim_df = pd.DataFrame(raw_results['away_players'])

    all_player_ids = pd.concat([home_sim_df['player_id'], away_sim_df['player_id']]).unique().tolist()
    actuals_df = get_player_shooting_actuals(all_player_ids)
    if actuals_df.empty:
        st.warning("Could not retrieve actual shooting stats for the players in this game.")
        return
    METRIC_MAP = [ ('Sim_Shot Attempts_per_60_ES', 'actual_sa_per_60', 'SA/60'), ('Sim_Shots_per_60_ES', 'actual_sog_per_60', 'SOG/60'), ('Sim_ShotAccuracy_Pct', 'actual_shot_accuracy_pct', 'Shot Acc %'), ('Sim_iHDCF_per_60_ES', 'actual_hdcf_per_60', 'HDCF/60'), ('Sim_iMDCF_per_60_ES', 'actual_mdcf_per_60', 'MDCF/60'), ('Sim_iLDCF_per_60_ES', 'actual_ldcf_per_60', 'LDCF/60'), ('Sim_Goals_per_60_ES', 'actual_g_per_60', 'G/60'), ('Sim_Shooting_Pct', 'actual_shooting_pct', 'Sht %'), ('Sim_ReboundsCreated_per_60_ES', 'actual_rebounds_per_60', 'Reb/60'), ]

    def process_comparison_data(sim_df, actuals_df):
        if 'TOI_ES' in sim_df.columns and sim_df['TOI_ES'].sum() > 0:
            for stat in ['Shot Attempts', 'Shots', 'Goals']:
                sim_df[f'Sim_{stat}_per_60_ES'] = np.where(sim_df['TOI_ES'] > 0, (sim_df[f'{stat}_ES'] / sim_df['TOI_ES']) * 3600, 0)
        sim_df['player_id'] = pd.to_numeric(sim_df['player_id'])
        actuals_df['player_id'] = pd.to_numeric(actuals_df['player_id'])
        merged_df = pd.merge(sim_df, actuals_df, on='player_id', how='left').fillna(0)
        final_cols = ['Player', 'TOI_Total']
        diff_cols = []
        numeric_cols_for_formatting = ['TOI_Total']
        for sim_col, actual_col, display_name in METRIC_MAP:
            if sim_col in merged_df.columns and actual_col in merged_df.columns:
                sim_display = f"{display_name}_Sim"
                actual_display = f"{display_name}_Actual"
                diff_display = f"{display_name}_Diff"
                merged_df[sim_display] = merged_df[sim_col]
                merged_df[actual_display] = merged_df[actual_col]
                merged_df[diff_display] = merged_df[sim_display] - merged_df[actual_display]
                final_cols.extend([sim_display, actual_display, diff_display])
                diff_cols.append(diff_display)
                numeric_cols_for_formatting.extend([sim_display, actual_display, diff_display])
        if 'TOI_Total' in merged_df.columns:
            merged_df['TOI_Total'] = merged_df['TOI_Total'] / 60
        return merged_df[final_cols], diff_cols, numeric_cols_for_formatting

    home_comparison_df, home_diff_cols, home_numeric_cols = process_comparison_data(home_sim_df, actuals_df)
    away_comparison_df, away_diff_cols, away_numeric_cols = process_comparison_data(away_sim_df, actuals_df)
    
    st.subheader("Aggregate Model Bias")
    combined_df = pd.concat([home_comparison_df, away_comparison_df])
    if home_diff_cols:
        bias_df = combined_df[home_diff_cols].mean().reset_index()
        bias_df.columns = ['Metric', 'Average Difference']
        bias_df['Metric'] = bias_df['Metric'].str.replace('_Diff', '')
        cols = st.columns(len(bias_df))
        for i, row in bias_df.iterrows():
            cols[i].metric(label=row['Metric'], value=f"{row['Average Difference']:.2f}")

    home_formatter = {col: "{:.2f}" for col in home_numeric_cols}
    away_formatter = {col: "{:.2f}" for col in away_numeric_cols}

    st.divider()
    st.subheader(f"{st.session_state.dashboard_data['home'].get('team_name', 'Home')} - Player Comparison")
    st.dataframe(
        home_comparison_df.style.apply(style_diff_by_percent, axis=1).format(formatter=home_formatter),
        use_container_width=True, hide_index=True
    )

    st.divider()
    st.subheader(f"{st.session_state.dashboard_data['away'].get('team_name', 'Away')} - Player Comparison")
    st.dataframe(
        away_comparison_df.style.apply(style_diff_by_percent, axis=1).format(formatter=away_formatter),
        use_container_width=True, hide_index=True
    )

def render_possession_validation_tab(results):
    if not results:
        st.info("Run a simulation to see the possession and playmaking validation data here.")
        return

    raw_results = results.get('raw_data')
    if not raw_results:
        st.warning("Simulation results are present, but raw data is missing.")
        return

    st.header("Possession & Playmaking (5v5): SvA Per 60 Mins")
    
    # --- FIX: Convert lists to DataFrames ---
    home_sim_df = pd.DataFrame(raw_results['home_players'])
    away_sim_df = pd.DataFrame(raw_results['away_players'])
    
    all_player_ids = pd.concat([home_sim_df['player_id'], away_sim_df['player_id']]).unique().tolist()
    actuals_df = get_player_possession_actuals(all_player_ids)
    
    if actuals_df.empty:
        st.warning("Could not retrieve actual possession/playmaking stats for the players in this game.")
        return
    
    METRIC_MAP = [
        ('Sim_Assists_per_60_ES', 'actual_a1_per_60', 'A1/60'),
        ('Sim_Takeaways_per_60_ES', 'actual_takeaways_per_60', 'TkA/60'),
        ('Sim_Giveaways_per_60_ES', 'actual_giveaways_per_60', 'GvA/60'),
        ('Sim_Shots_Off_Cycle_per_60_ES', 'actual_shots_off_cycle_per_60', 'Cycle Shots/60'),
        ('Sim_Assists_Off_Cycle_per_60_ES', 'actual_assists_off_cycle_per_60', 'Cycle Assists/60'),
        ('Sim_PenaltiesDrawn_per_60_ES', 'actual_penalties_drawn_per_60', 'Pens Drawn/60'),
        ('Sim_Faceoff_Pct', 'actual_faceoff_pct', 'FO%'),
    ]

    def process_possession_data(sim_df, actuals_df):
        if sim_df.empty: return pd.DataFrame(), [], []

        sim_df['player_id'] = pd.to_numeric(sim_df['player_id'])
        actuals_df['player_id'] = pd.to_numeric(actuals_df['player_id'])
        merged_df = pd.merge(sim_df, actuals_df, on='player_id', how='left').fillna(0)
        
        final_cols = ['Player', 'TOI_Total']
        diff_cols = []
        numeric_cols_for_formatting = ['TOI_Total']

        for sim_col, actual_col, display_name in METRIC_MAP:
            if sim_col in merged_df.columns and actual_col in merged_df.columns:
                sim_display, actual_display, diff_display = f"{display_name}_Sim", f"{display_name}_Actual", f"{display_name}_Diff"
                merged_df[sim_display] = merged_df[sim_col]
                merged_df[actual_display] = merged_df[actual_col]
                
                merged_df[diff_display] = merged_df[sim_display] - merged_df[actual_display]
                
                final_cols.extend([sim_display, actual_display, diff_display])
                diff_cols.append(diff_display)
                numeric_cols_for_formatting.extend([sim_display, actual_display, diff_display])
        
        if 'TOI_Total' in merged_df.columns:
            merged_df['TOI_Total'] = merged_df['TOI_Total'] / 60

        for col_prefix in ['FO%_Sim', 'FO%_Actual', 'FO%_Diff']:
            if col_prefix in merged_df.columns:
                merged_df.loc[merged_df['Faceoffs_Taken_Total'] == 0, col_prefix] = np.nan

        return merged_df[final_cols], diff_cols, numeric_cols_for_formatting

    home_comparison_df, home_diff_cols, home_numeric_cols = process_possession_data(home_sim_df, actuals_df)
    away_comparison_df, away_diff_cols, away_numeric_cols = process_possession_data(away_sim_df, actuals_df)

    st.subheader("Aggregate Model Bias")
    combined_df = pd.concat([home_comparison_df, away_comparison_df])
    if home_diff_cols:
        bias_df = combined_df[home_diff_cols].mean().reset_index()
        bias_df.columns = ['Metric', 'Average Difference']
        bias_df['Metric'] = bias_df['Metric'].str.replace('_Diff', '')
        cols = st.columns(len(bias_df))
        for i, row in bias_df.iterrows():
            cols[i].metric(label=row['Metric'], value=f"{row['Average Difference']:.2f}")

    home_formatter = {col: "{:.2f}" for col in home_numeric_cols}
    away_formatter = {col: "{:.2f}" for col in away_numeric_cols}

    st.divider()
    st.subheader(f"{st.session_state.dashboard_data['home'].get('team_name', 'Home')} - Player Comparison")
    st.dataframe(
        home_comparison_df.style.apply(style_diff_by_percent, axis=1).format(formatter=home_formatter, na_rep='N/A'),
        use_container_width=True, hide_index=True
    )

    st.divider()
    st.subheader(f"{st.session_state.dashboard_data['away'].get('team_name', 'Away')} - Player Comparison")
    st.dataframe(
        away_comparison_df.style.apply(style_diff_by_percent, axis=1).format(formatter=away_formatter, na_rep='N/A'),
        use_container_width=True, hide_index=True
    )

def render_transition_validation_tab(results):
    if not results:
        st.info("Run a simulation to see the transition validation data here.")
        return

    raw_results = results.get('raw_data')
    if not raw_results:
        st.warning("Simulation results are present, but raw data is missing.")
        return

    st.header("Transition (5v5): SvA Per 60 Mins")
    
    # --- FIX: Convert lists to DataFrames ---
    home_sim_df = pd.DataFrame(raw_results['home_players'])
    away_sim_df = pd.DataFrame(raw_results['away_players'])
    
    all_player_ids = pd.concat([home_sim_df['player_id'], away_sim_df['player_id']]).unique().tolist()
    actuals_df = get_player_transition_actuals(all_player_ids)
    
    if actuals_df.empty:
        st.warning("Could not retrieve actual transition stats for the players in this game.")
        return
        
    METRIC_MAP = [
        ('Sim_ControlledEntries_per_60_ES', 'actual_controlled_entries_per_60', 'Entries/60'),
        ('Sim_ControlledExits_per_60_ES', 'actual_controlled_exits_per_60', 'Exits/60'),
        ('Sim_ForecheckBreakups_per_60_ES', 'actual_forecheck_breakups_per_60', 'Forechecks/60'),
        # --- MODIFIED: Use new stats for Entry Denials ---
        ('Sim_EntryDenials_per_60_ES', 'actual_entry_denials_per_60', 'Entry Denials/60'),
        ('Sim_FailedEntries_per_60_ES', 'actual_failed_entries_per_60', 'Failed Entries/60')
    ]

    def process_transition_data(sim_df, actuals_df):
        if sim_df.empty: return pd.DataFrame(), [], []

        sim_df['player_id'] = pd.to_numeric(sim_df['player_id'])
        actuals_df['player_id'] = pd.to_numeric(actuals_df['player_id'])
        merged_df = pd.merge(sim_df, actuals_df, on='player_id', how='left').fillna(0)
        
        final_cols = ['Player', 'TOI_Total']
        diff_cols = []
        numeric_cols_for_formatting = ['TOI_Total']

        for sim_col, actual_col, display_name in METRIC_MAP:
            if sim_col in merged_df.columns and actual_col in merged_df.columns:
                sim_display, actual_display, diff_display = f"{display_name}_Sim", f"{display_name}_Actual", f"{display_name}_Diff"
                merged_df[sim_display] = merged_df[sim_col]
                merged_df[actual_display] = merged_df[actual_col]
                merged_df[diff_display] = merged_df[sim_display] - merged_df[actual_display]
                final_cols.extend([sim_display, actual_display, diff_display])
                diff_cols.append(diff_display)
                numeric_cols_for_formatting.extend([sim_display, actual_display, diff_display])
        
        if 'TOI_Total' in merged_df.columns:
            merged_df['TOI_Total'] = merged_df['TOI_Total'] / 60

        return merged_df[final_cols], diff_cols, numeric_cols_for_formatting

    home_comparison_df, home_diff_cols, home_numeric_cols = process_transition_data(home_sim_df, actuals_df)
    away_comparison_df, away_diff_cols, away_numeric_cols = process_transition_data(away_sim_df, actuals_df)

    st.subheader("Aggregate Model Bias")
    combined_df = pd.concat([home_comparison_df, away_comparison_df])
    if home_diff_cols:
        bias_df = combined_df[home_diff_cols].mean().reset_index()
        bias_df.columns = ['Metric', 'Average Difference']
        bias_df['Metric'] = bias_df['Metric'].str.replace('_Diff', '')
        cols = st.columns(len(bias_df))
        for i, row in bias_df.iterrows():
            cols[i].metric(label=row['Metric'], value=f"{row['Average Difference']:.2f}")

    home_formatter = {col: "{:.2f}" for col in home_numeric_cols}
    away_formatter = {col: "{:.2f}" for col in away_numeric_cols}

    st.divider()
    st.subheader(f"{st.session_state.dashboard_data['home'].get('team_name', 'Home')} - Player Comparison")
    st.dataframe(
        home_comparison_df.style.apply(style_diff_by_percent, axis=1).format(formatter=home_formatter, na_rep='N/A'),
        use_container_width=True, hide_index=True
    )

    st.divider()
    st.subheader(f"{st.session_state.dashboard_data['away'].get('team_name', 'Away')} - Player Comparison")
    st.dataframe(
        away_comparison_df.style.apply(style_diff_by_percent, axis=1).format(formatter=away_formatter, na_rep='N/A'),
        use_container_width=True, hide_index=True
    )

def render_defense_validation_tab(results):
    if not results:
        st.info("Run a simulation to see the defense validation data here.")
        return

    raw_results = results.get('raw_data')
    if not raw_results:
        st.warning("Simulation results are present, but raw data is missing.")
        return

    st.header("Defensive Performance (5v5): SvA Per 60 Mins")
    
    # --- FIX: Convert lists to DataFrames ---
    home_sim_df = pd.DataFrame(raw_results['home_players'])
    away_sim_df = pd.DataFrame(raw_results['away_players'])
    
    all_player_ids = pd.concat([home_sim_df['player_id'], away_sim_df['player_id']]).unique().tolist()
    actuals_df = get_player_defense_actuals(all_player_ids)
    
    if actuals_df.empty:
        st.warning("Could not retrieve actual defensive stats for the players in this game.")
        return
        
    METRIC_MAP = [
        ('Sim_OnIce_HDCA_per_60_ES', 'actual_hdca_per_60', 'HDCA/60'),
        ('Sim_OnIce_MDCA_per_60_ES', 'actual_mdca_per_60', 'MDCA/60'),
        ('Sim_OnIce_LDCA_per_60_ES', 'actual_ldca_per_60', 'LDCA/60'),
        ('Sim_Blocks_per_60_ES', 'actual_blocks_per_60', 'Blocks/60'),
        ('Sim_MinorPenaltiesTaken_per_60_ES', 'actual_minor_penalties_per_60', 'Minor Pen/60'),
        ('Sim_MajorPenaltiesTaken_per_60_ES', 'actual_major_penalties_per_60', 'Major Pen/60'),
    ]

    def process_defense_data(sim_df, actuals_df):
        if sim_df.empty: return pd.DataFrame(), [], []

        sim_df['player_id'] = pd.to_numeric(sim_df['player_id'])
        actuals_df['player_id'] = pd.to_numeric(actuals_df['player_id'])
        merged_df = pd.merge(sim_df, actuals_df, on='player_id', how='left').fillna(0)
        
        final_cols = ['Player', 'TOI_Total']
        diff_cols = []
        numeric_cols_for_formatting = ['TOI_Total']

        for sim_col, actual_col, display_name in METRIC_MAP:
            if sim_col in merged_df.columns and actual_col in merged_df.columns:
                sim_display, actual_display, diff_display = f"{display_name}_Sim", f"{display_name}_Actual", f"{display_name}_Diff"
                merged_df[sim_display] = merged_df[sim_col]
                merged_df[actual_display] = merged_df[actual_col]
                merged_df[diff_display] = merged_df[sim_display] - merged_df[actual_display]
                final_cols.extend([sim_display, actual_display, diff_display])
                diff_cols.append(diff_display)
                numeric_cols_for_formatting.extend([sim_display, actual_display, diff_display])
        
        if 'TOI_Total' in merged_df.columns:
            merged_df['TOI_Total'] = merged_df['TOI_Total'] / 60

        return merged_df[final_cols], diff_cols, numeric_cols_for_formatting

    home_comparison_df, home_diff_cols, home_numeric_cols = process_defense_data(home_sim_df, actuals_df)
    away_comparison_df, away_diff_cols, away_numeric_cols = process_defense_data(away_sim_df, actuals_df)

    st.subheader("Aggregate Model Bias")
    combined_df = pd.concat([home_comparison_df, away_comparison_df])
    if home_diff_cols:
        bias_df = combined_df[home_diff_cols].mean().reset_index()
        bias_df.columns = ['Metric', 'Average Difference']
        bias_df['Metric'] = bias_df['Metric'].str.replace('_Diff', '')
        cols = st.columns(len(bias_df))
        for i, row in bias_df.iterrows():
            cols[i].metric(label=row['Metric'], value=f"{row['Average Difference']:.2f}")

    home_formatter = {col: "{:.2f}" for col in home_numeric_cols}
    away_formatter = {col: "{:.2f}" for col in away_numeric_cols}

    st.divider()
    st.subheader(f"{st.session_state.dashboard_data['home'].get('team_name', 'Home')} - Player Comparison")
    st.dataframe(
        home_comparison_df.style.apply(style_diff_by_percent, axis=1).format(formatter=home_formatter, na_rep='N/A'),
        use_container_width=True, hide_index=True
    )

    st.divider()
    st.subheader(f"{st.session_state.dashboard_data['away'].get('team_name', 'Away')} - Player Comparison")
    st.dataframe(
        away_comparison_df.style.apply(style_diff_by_percent, axis=1).format(formatter=away_formatter, na_rep='N/A'),
        use_container_width=True, hide_index=True
    )

def render_special_teams_validation_tab(results):
    if not results:
        st.info("Run a simulation to see the specialty teams validation data here.")
        return

    raw_results = results.get('raw_data')
    if not raw_results:
        st.warning("Simulation results are present, but raw data is missing.")
        return

    st.header("Specialty Teams Performance: SvA Per 60 Mins")
    
    # --- FIX: Convert lists to DataFrames ---
    home_sim_df = pd.DataFrame(raw_results['home_players'])
    away_sim_df = pd.DataFrame(raw_results['away_players'])
    
    all_player_ids = pd.concat([home_sim_df['player_id'], away_sim_df['player_id']]).unique().tolist()
    actuals_df = get_player_special_teams_actuals(all_player_ids)
    
    if actuals_df.empty:
        st.warning("Could not retrieve actual specialty teams stats for the players in this game.")
        return
        
    METRIC_MAP = [
        ('Sim_PP_iCF_per_60', 'actual_pp_icf_per_60', 'PP iCF/60'),
        ('Sim_OnIce_CF_per_60_PP', 'actual_pp_on_ice_cf_per_60', 'PP On-Ice CF/60'),
        ('Sim_GoalsAboveExpected_PP', 'actual_pp_gsax_per_60', 'PP GSAx/60'),
        ('Sim_PK_Clears_per_60_PK', 'actual_pk_clears_per_60', 'PK Clears/60'),
        ('Sim_PK_CA_per_60', 'actual_pk_ca_per_60', 'PK CA/60'),
        ('Sim_Blocks_per_60_PK', 'actual_pk_blocks_per_60', 'PK Blocks/60'),
    ]

    def process_special_teams_data(sim_df, actuals_df):
        if sim_df.empty: return pd.DataFrame(), [], []

        # Calculate composite sim stats
        sim_df['Sim_PP_iCF_per_60'] = sim_df.get('Sim_iHDCF_per_60_PP', 0) + sim_df.get('Sim_iMDCF_per_60_PP', 0) + sim_df.get('Sim_iLDCF_per_60_PP', 0)
        sim_df['Sim_PK_CA_per_60'] = sim_df.get('Sim_OnIce_HDCA_per_60_PK', 0) + sim_df.get('Sim_OnIce_MDCA_per_60_PK', 0) + sim_df.get('Sim_OnIce_LDCA_per_60_PK', 0)

        sim_df['player_id'] = pd.to_numeric(sim_df['player_id'])
        actuals_df['player_id'] = pd.to_numeric(actuals_df['player_id'])
        merged_df = pd.merge(sim_df, actuals_df, on='player_id', how='left').fillna(0)
        
        final_cols = ['Player', 'TOI_PP', 'TOI_PK']
        diff_cols = []
        numeric_cols_for_formatting = ['TOI_PP', 'TOI_PK']

        for sim_col, actual_col, display_name in METRIC_MAP:
            if sim_col in merged_df.columns and actual_col in merged_df.columns:
                sim_display, actual_display, diff_display = f"{display_name}_Sim", f"{display_name}_Actual", f"{display_name}_Diff"
                merged_df[sim_display] = merged_df[sim_col]
                merged_df[actual_display] = merged_df[actual_col]
                merged_df[diff_display] = merged_df[sim_display] - merged_df[actual_display]
                final_cols.extend([sim_display, actual_display, diff_display])
                diff_cols.append(diff_display)
                numeric_cols_for_formatting.extend([sim_display, actual_display, diff_display])
        
        if 'TOI_PP_Total' in merged_df.columns:
            merged_df['TOI_PP'] = merged_df['TOI_PP_Total'] / 60
        if 'TOI_PK_Total' in merged_df.columns:
            merged_df['TOI_PK'] = merged_df['TOI_PK_Total'] / 60

        return merged_df[final_cols], diff_cols, numeric_cols_for_formatting

    home_comparison_df, home_diff_cols, home_numeric_cols = process_special_teams_data(home_sim_df, actuals_df)
    away_comparison_df, away_diff_cols, away_numeric_cols = process_special_teams_data(away_sim_df, actuals_df)

    st.subheader("Aggregate Model Bias")
    combined_df = pd.concat([home_comparison_df, away_comparison_df])
    if home_diff_cols:
        bias_df = combined_df[home_diff_cols].mean().reset_index()
        bias_df.columns = ['Metric', 'Average Difference']
        bias_df['Metric'] = bias_df['Metric'].str.replace('_Diff', '')
        cols = st.columns(len(bias_df))
        for i, row in bias_df.iterrows():
            cols[i].metric(label=row['Metric'], value=f"{row['Average Difference']:.2f}")

    home_formatter = {col: "{:.2f}" for col in home_numeric_cols}
    away_formatter = {col: "{:.2f}" for col in away_numeric_cols}

    st.divider()
    st.subheader(f"{st.session_state.dashboard_data['home'].get('team_name', 'Home')} - Player Comparison")
    st.dataframe(
        home_comparison_df.style.apply(style_diff_by_percent, axis=1).format(formatter=home_formatter, na_rep='N/A'),
        use_container_width=True, hide_index=True
    )

    st.divider()
    st.subheader(f"{st.session_state.dashboard_data['away'].get('team_name', 'Away')} - Player Comparison")
    st.dataframe(
        away_comparison_df.style.apply(style_diff_by_percent, axis=1).format(formatter=away_formatter, na_rep='N/A'),
        use_container_width=True, hide_index=True
    )

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
                        home_coach = st.session_state.dashboard_data['home'].get('coach_data')
                        away_coach = st.session_state.dashboard_data['away'].get('coach_data')
                        home_goalie = st.session_state.dashboard_data['home'].get('starting_goalie')
                        away_goalie = st.session_state.dashboard_data['away'].get('starting_goalie')
                        if home_goalie is None or away_goalie is None:
                            st.error("A starting goalie was not found for one or both teams.")
                        else:
                            save_dashboard_state(current_game_id, 'home', st.session_state.dashboard_data['home'])
                            save_dashboard_state(current_game_id, 'away', st.session_state.dashboard_data['away'])
                            home_sim_data = {'lineup': pd.DataFrame(home_lineup_data), 'coach': home_coach, 'goalie': home_goalie}
                            away_sim_data = {'lineup': pd.DataFrame(away_lineup_data), 'coach': away_coach, 'goalie': away_goalie}
                            with st.spinner("Running simulations..."):
                                raw_results = run_cloud_simulations(1000, home_sim_data, away_sim_data)
                                
                                main_odds = calculate_betting_odds(raw_results['all_game_scores'])
                                
                                teams_df = get_teams()
                                home_team_id = st.session_state.dashboard_data['home']['team_id']
                                away_team_id = st.session_state.dashboard_data['away']['team_id']
                                home_info = teams_df[teams_df['team_id'] == home_team_id].iloc[0].to_dict()
                                away_info = teams_df[teams_df['team_id'] == away_team_id].iloc[0].to_dict()

                                home_players_df = pd.DataFrame(raw_results['home_players'])
                                away_players_df = pd.DataFrame(raw_results['away_players'])
                                home_players_df['team_name'] = home_info.get('team_full_name')
                                away_players_df['team_name'] = away_info.get('team_full_name')
                                all_players_df = pd.concat([home_players_df, away_players_df])
                                
                                player_props = calculate_player_props(all_players_df, home_info, away_info)

                                final_results_to_save = {
                                    "raw_data": raw_results,
                                    "main_markets": main_odds,
                                    "player_props": player_props
                                }

                                st.session_state.all_sim_results[current_game_id] = final_results_to_save
                                save_simulation_results(current_game_id, final_results_to_save)
                            
                            st.success("Simulations Complete and Configuration Saved!")
                            st.rerun()
        with odds_col:
            if results_for_current_game and 'main_markets' in results_for_current_game:
                betting_odds = results_for_current_game['main_markets']
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
            raw_results = results_for_current_game.get('raw_data', {})
            if raw_results:
                validation_stats_options = [
                    'Sim_iHDCF_per_60_ES', 'Sim_iMDCF_per_60_ES', 'Sim_iLDCF_per_60_ES',
                    'Sim_OnIce_HDCA_per_60_ES', 'Sim_OnIce_MDCA_per_60_ES', 'Sim_OnIce_LDCA_per_60_ES',
                    'Sim_xG_for_per_60_ES', 'Sim_ReboundsCreated_per_60_ES',
                    'Sim_Assists_per_60_ES', 'Sim_Giveaways_per_60_ES', 'Sim_Takeaways_per_60_ES',
                    'Sim_Shots_Off_Cycle_per_60_ES', 'Sim_Assists_Off_Cycle_per_60_ES',
                    'Sim_Faceoffs_Won_per_60_ES', 'Sim_Faceoffs_Taken_per_60_ES', 'Sim_Faceoff_Pct',
                    'Sim_PenaltiesDrawn_per_60_ES', 'Sim_ControlledEntries_per_60_ES',
                    'Sim_ControlledExits_per_60_ES', 'Sim_ForecheckBreakups_per_60_ES',
                    'Sim_OnIce_EntryAttempts_Against_per_60_ES', 'Sim_OnIce_ControlledEntries_Against_per_60_ES',
                    'Sim_Blocks_per_60_ES', 'Sim_MinorPenaltiesTaken_per_60_ES', 'Sim_MajorPenaltiesTaken_per_60_ES',
                    'Sim_iHDCF_per_60_PP', 'Sim_iMDCF_per_60_PP', 'Sim_iLDCF_per_60_PP',
                    'Sim_OnIce_CF_per_60_PP', 'Sim_xG_for_per_60_PP', 'Sim_ReboundsCreated_per_60_PP',
                    'Sim_PenaltiesDrawn_per_60_PP', 'Sim_ControlledEntries_per_60_PP',
                    'Sim_OnIce_HDCA_per_60_PK', 'Sim_OnIce_MDCA_per_60_PK', 'Sim_OnIce_LDCA_per_60_PK',
                    'Sim_PK_Clears_per_60_PK', 'Sim_Blocks_per_60_PK'
                ]
                default_selection = [
                    'Sim_iHDCF_per_60_ES', 'Sim_xG_for_per_60_ES', 'Sim_OnIce_HDCA_per_60_ES',
                    'Sim_OnIce_CF_per_60_PP', 'Sim_OnIce_HDCA_per_60_PK'
                ]
                selected_stats = st.multiselect(
                    "Select validation stats to display:",
                    options=sorted(validation_stats_options),
                    default=default_selection
                )
                base_cols = ['Player', 'TOI_Total']
                
                # --- FIX: Convert lists to DataFrames ---
                home_df = pd.DataFrame(raw_results['home_players'])
                away_df = pd.DataFrame(raw_results['away_players'])
                
                st.subheader(st.session_state.dashboard_data['home'].get('team_name', 'Home'))
                st.dataframe(home_df[base_cols + selected_stats], use_container_width=True, hide_index=True)
                
                st.divider()
                st.subheader(st.session_state.dashboard_data['away'].get('team_name', 'Away'))
                st.dataframe(away_df[base_cols + selected_stats], use_container_width=True, hide_index=True)
            else:
                st.info("Run a simulation to see the Player Level validation data here.")

    with tab5:
        render_shooting_validation_tab(results_for_current_game)

    with tab6:
        render_possession_validation_tab(results_for_current_game)
        
    with tab7:
        render_transition_validation_tab(results_for_current_game)
        
    with tab8:
        render_defense_validation_tab(results_for_current_game)

    with tab9:
        render_special_teams_validation_tab(results_for_current_game)