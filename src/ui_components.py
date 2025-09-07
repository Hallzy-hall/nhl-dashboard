# src/ui_components.py

import streamlit as st
import pandas as pd
import json
from io import StringIO # IMPORT THIS
from src.definitions import all_definitions
from src.calculations import calculate_line_score

# This import list contains all necessary functions from your db_queries
from utils.db_queries import (
    get_coach_by_team_id, get_default_lineup, get_default_pp_lineup, get_default_pk_lineup,
    get_manual_ratings_for_players, save_manual_rating, delete_manual_rating, log_rating_change,
    get_team_roster, get_player_ratings, get_manual_goalie_ratings,
    save_manual_goalie_rating, delete_manual_goalie_rating, get_starting_goalie_id,
    get_full_goalie_data, save_coach_ratings, get_simulation_roster
)


def select_player(team_type: str, player_id: str, player_name: str):
    """
    Handles the logic for selecting a player in the UI and toggling the editor's visibility.
    """
    if str(st.session_state.dashboard_data[team_type].get('selected_player_id')) == str(player_id):
        st.session_state.dashboard_data[team_type]['selected_player_id'] = None
        st.session_state.dashboard_data[team_type]['selected_player_name'] = None
        st.session_state.dashboard_data[team_type]['show_edit_modal'] = False
    else:
        st.session_state.dashboard_data[team_type]['selected_player_id'] = player_id
        st.session_state.dashboard_data[team_type]['selected_player_name'] = player_name
        st.session_state.dashboard_data[team_type]['show_edit_modal'] = True

    other_team = 'away' if team_type == 'home' else 'home'
    st.session_state.dashboard_data[other_team]['selected_player_id'] = None
    st.session_state.dashboard_data[other_team]['selected_player_name'] = None
    st.session_state.dashboard_data[other_team]['show_edit_modal'] = False


def load_team_data(team_id: int, team_type: str, teams_df: pd.DataFrame):
    """
    Loads all data for a given team_id into the session state using a single,
    efficient database call for skaters.
    """
    selected_team_row = teams_df[teams_df['team_id'] == team_id]
    if selected_team_row.empty: return

    team_name = selected_team_row['team_full_name'].iloc[0]

    # --- MODIFIED SECTION ---
    # 1. Get ALL skater data (roster + all ratings) in one call
    full_skater_data = get_simulation_roster(team_id)
    if full_skater_data.empty: return

    # The 'base_ratings' DataFrame now contains ALL columns from base, pp, and pk tables
    base_ratings = full_skater_data.copy()
    
    # Derive the simple roster from the full data
    skater_roster = full_skater_data[['player_id', 'full_name', 'position']].copy()
    skater_ids = skater_roster['player_id'].tolist()
    manual_ratings = get_manual_ratings_for_players(skater_ids)
    # --- END MODIFICATION ---

    # 3. Process goalies (this logic remains the same)
    goalie_roster_df = get_full_goalie_data(team_id)
    if not goalie_roster_df.empty:
        goalie_ids = goalie_roster_df['player_id'].tolist()
        manual_goalie_ratings = get_manual_goalie_ratings(goalie_ids)
    else:
        manual_goalie_ratings = {}

    # 4. Determine starting goalie (remains the same)
    starting_goalie = None
    if not goalie_roster_df.empty:
        g1_goalie_id = get_starting_goalie_id(team_id)
        if g1_goalie_id:
            starter_row = goalie_roster_df[goalie_roster_df['player_id'] == g1_goalie_id]
            if not starter_row.empty:
                starting_goalie = starter_row.iloc[0].to_dict()
        if starting_goalie is None and not goalie_roster_df.empty:
            starting_goalie = goalie_roster_df.iloc[0].to_dict()

    # 5. Update session state with the new, complete data
    st.session_state.dashboard_data[team_type].update({
        'team_id': team_id, 'team_name': team_name,
        'lineup': get_default_lineup(team_id), 'pp_lineup': get_default_pp_lineup(team_id),
        'pk_lineup': get_default_pk_lineup(team_id),
        'roster': skater_roster,           # Use the derived roster
        'base_ratings': base_ratings,       # Use the COMPLETE ratings dataframe
        'manual_ratings': manual_ratings,
        'coach_data': get_coach_by_team_id(team_id),
        'goalie_roster': goalie_roster_df,
        'starting_goalie': starting_goalie,
        'manual_goalie_ratings': manual_goalie_ratings,
        'selected_player_id': None, 'selected_player_name': None, 'show_edit_modal': False,
    })

def on_team_select(team_type: str, teams_df: pd.DataFrame):
    """Callback function for the original manual team selectbox."""
    team_selector_key = f"{team_type}_team_selector"
    selected_team_name = st.session_state.get(team_selector_key)
    if not selected_team_name: return

    selected_team_row = teams_df[teams_df['team_full_name'] == selected_team_name]
    if not selected_team_row.empty:
        team_id = int(selected_team_row['team_id'].iloc[0])
        load_team_data(team_id, team_type, teams_df)

def _apply_saved_state(team_type: str, saved_state: dict):
    """Overwrites default data in session_state with saved state data if it exists."""
    if not saved_state:
        return

    # A helper to safely read json that might be a DataFrame
    def read_df_from_json(json_string):
        try:
            # UPDATED LINE TO FIX WARNING
            return pd.read_json(StringIO(json_string), orient='split')
        except (ValueError, TypeError):
            return pd.DataFrame() # Return empty df if there's an issue

    # --- CORRECTED LOGIC USING THE HELPER ---
    lineup_key = f'{team_type}_lineup'
    if saved_state.get(lineup_key):
        st.session_state.dashboard_data[team_type]['lineup'] = read_df_from_json(saved_state[lineup_key])

    pp_lineup_key = f'{team_type}_pp_lineup'
    if saved_state.get(pp_lineup_key):
        st.session_state.dashboard_data[team_type]['pp_lineup'] = read_df_from_json(saved_state[pp_lineup_key])

    pk_lineup_key = f'{team_type}_pk_lineup'
    if saved_state.get(pk_lineup_key):
        st.session_state.dashboard_data[team_type]['pk_lineup'] = read_df_from_json(saved_state[pk_lineup_key])
        
    goalie_key = f'{team_type}_starting_goalie'
    if saved_state.get(goalie_key) and saved_state[goalie_key] is not None:
        st.session_state.dashboard_data[team_type]['starting_goalie'] = json.loads(saved_state[goalie_key])

def _render_ratings_editor(team_type: str, team_data: dict):
    """Renders the ratings editor expander for the currently selected player or goalie."""
    player_id = str(team_data.get('selected_player_id'))
    player_name = team_data.get('selected_player_name')

    goalie_roster = team_data.get('goalie_roster', pd.DataFrame())
    is_goalie = not goalie_roster.empty and (goalie_roster['player_id'].astype(str) == player_id).any()

    # --- MODIFIED SECTION: Define the complete, organized lists of ratings ---
    SKATER_RATINGS_TO_EDIT = [
        # General & TOI
        "toi_individual_rating", "faceoff_rating",
        # 5v5 Offensive
        "shooting_volume", "shooting_accuracy", "hdshot_creation", "mshot_creation", "ofinishing",
        "orebound_creation", "oprime_playmaking", "osecond_playmaking", "ozone_entry",
        "opuck_possession", "ocycle_play", "o_forechecking_pressure",
        # 5v5 Defensive
        "d_breakout_ability", "d_entry_denial", "d_cycle_defense", "d_shot_blocking",
        # Danger Zone Specific
        "o_hd_shot_creation_rating", "o_md_shot_creation_rating", "o_ld_shot_creation_rating",
        "d_hd_shot_suppression_rating", "d_md_shot_suppression_rating", "d_ld_shot_suppression_rating",
        # Penalties
        "openalty_drawn", "min_penalty", "maj_penalty",
        # Power Play
        "pp_shot_volume", "pp_shot_on_net", "pp_chance_creation", "pp_playmaking",
        "pp_zone_entry", "pp_finishing", "pp_rebound_creation",
        # Penalty Kill
        "pk_shot_suppression", "pk_clearing_ability", "pk_shot_blocking"
    ]

    GOALIE_RATINGS_TO_EDIT = [
        # New Base Stats
        "goalie_save_adj", "rebound_control_adj", "g_ld_save_5v5", "g_ld_save_4v5",
        "g_md_save_5v5", "g_md_save_4v5", "g_hd_save_5v5", "g_hd_save_4v5",
        # Existing Sim Ratings
        "g_low_danger_sv_rating", "g_medium_danger_sv_rating", "g_high_danger_sv_rating",
        "g_rebound_control_rating", "g_freeze_puck_rating"
    ]
    # --- END OF MODIFICATION ---

    if is_goalie:
        RATINGS_TO_EDIT = GOALIE_RATINGS_TO_EDIT
        base_ratings_df = goalie_roster
        original_manual_ratings = team_data.get('manual_goalie_ratings', {}).get(player_id, {})
        save_func = save_manual_goalie_rating
        delete_func = delete_manual_goalie_rating
    else:
        RATINGS_TO_EDIT = SKATER_RATINGS_TO_EDIT
        base_ratings_df = team_data.get('base_ratings', pd.DataFrame())
        original_manual_ratings = team_data.get('manual_ratings', {}).get(player_id, {})
        save_func = save_manual_rating
        delete_func = delete_manual_rating

    with st.expander(f"✏️ Editing Ratings for: **{player_name}**", expanded=True):
        if not base_ratings_df.empty:
            base_ratings_df['player_id'] = base_ratings_df['player_id'].astype(str)
            player_ratings = base_ratings_df[base_ratings_df['player_id'] == player_id]
            new_manual_ratings = {}

            # --- Add header row for clarity in the UI ---
            h_col1, h_col2, h_col3, h_col4 = st.columns([2.5, 1, 1, 2])
            h_col1.markdown("**Rating**")
            h_col2.markdown("**Base**")
            h_col3.markdown("**Manual**")
            h_col4.markdown("**Manual Weight**")


            for rating_name in RATINGS_TO_EDIT:
                base_value = 1000
                if not player_ratings.empty and rating_name in player_ratings.columns:
                    rating_val = player_ratings[rating_name].iloc[0]
                    if pd.notna(rating_val):
                        base_value = rating_val

                existing_manual = original_manual_ratings.get(rating_name, {})
                manual_value = existing_manual.get('manual_value', float(base_value))
                weight_value = existing_manual.get('weight', 0)

                r_col1, r_col2, r_col3, r_col4 = st.columns([2.5, 1, 1, 2])
                r_col1.text_input("Rating", value=rating_name.replace('_', ' ').title(), disabled=True, key=f"{team_type}_{player_id}_{rating_name}_name", label_visibility="collapsed")
                r_col2.text_input("Base", value=f"{base_value:.0f}", key=f"{team_type}_{player_id}_{rating_name}_base", disabled=True, label_visibility="collapsed")
                new_manual_value = r_col3.number_input("Manual", value=float(manual_value), key=f"{team_type}_{player_id}_{rating_name}_manual", step=1.0, format="%.0f", label_visibility="collapsed")
                new_weight_value = r_col4.slider("Weight %", min_value=0, max_value=100, value=weight_value, key=f"{team_type}_{player_id}_{rating_name}_weight", label_visibility="collapsed")

                new_manual_ratings[rating_name] = {"manual_value": new_manual_value, "weight": new_weight_value, "base_value": base_value}

            save_col, cancel_col = st.columns(2)
            with save_col:
                if st.button("Save Ratings", key=f"save_expander_{team_type}_{player_id}", use_container_width=True, type="primary"):
                    updated_manual_ratings = {}
                    for rating_name, new_values in new_manual_ratings.items():
                        new_weight, new_value, base_value = new_values['weight'], new_values['manual_value'], new_values['base_value']
                        original_rating = original_manual_ratings.get(rating_name, {'manual_value': None, 'weight': 0})
                        old_weight, old_value = original_rating['weight'], original_rating.get('manual_value') or base_value

                        if new_value != old_value or new_weight != old_weight:
                            log_rating_change(player_id, player_name, rating_name, old_value, new_value, old_weight, new_weight)

                        if new_weight == 0:
                            delete_func(player_id=player_id, rating_name=rating_name)
                        else:
                            save_func(player_id, player_name, rating_name, new_value, new_weight)
                        if new_weight > 0:
                            updated_manual_ratings[rating_name] = {"manual_value": new_value, "weight": new_weight}

                    if is_goalie:
                        st.session_state.dashboard_data[team_type]['manual_goalie_ratings'][player_id] = updated_manual_ratings
                    else:
                        st.session_state.dashboard_data[team_type]['manual_ratings'][player_id] = updated_manual_ratings

                    st.success(f"Ratings for {player_name} saved!")
                    st.session_state.dashboard_data[team_type]['show_edit_modal'] = False
                    st.session_state.dashboard_data[team_type]['selected_player_id'] = None
                    st.rerun()

            with cancel_col:
                if st.button("Cancel", key=f"cancel_expander_{team_type}_{player_id}", use_container_width=True):
                    st.session_state.dashboard_data[team_type]['show_edit_modal'] = False
                    st.session_state.dashboard_data[team_type]['selected_player_id'] = None
                    st.rerun()


def _render_lineup_rows(team_type, line_name, positions, team_data, player_names, toi_component: str = 'Total'):
    """Renders the player selectors for a single line with dynamic ID updates."""
    def update_player_in_lineup(pos_lookup_val):
        widget_key = f"{team_type}_{line_name}_{pos_lookup_val}_name"
        selected_player_name = st.session_state.get(widget_key)
        if "PP" in line_name:
            lineup_df_key, pos_col = 'pp_lineup', 'pp_position'
        elif "PK" in line_name:
            lineup_df_key, pos_col = 'pk_lineup', 'pk_position'
        else:
            lineup_df_key, pos_col = 'lineup', 'position_slot'
        lineup_df = team_data[lineup_df_key]
        roster_df = team_data['roster']
        row_index = lineup_df.index[lineup_df[pos_col] == pos_lookup_val].tolist()
        if selected_player_name:
            new_player_info = roster_df[roster_df['full_name'] == selected_player_name]
            if not new_player_info.empty:
                new_player_id = new_player_info['player_id'].iloc[0]
                new_player_pos = new_player_info['position'].iloc[0]
                if row_index:
                    idx = row_index[0]
                    st.session_state.dashboard_data[team_type][lineup_df_key].loc[idx, 'full_name'] = selected_player_name
                    st.session_state.dashboard_data[team_type][lineup_df_key].loc[idx, 'player_id'] = new_player_id
                    st.session_state.dashboard_data[team_type][lineup_df_key].loc[idx, 'position'] = new_player_pos
                else:
                    new_row = pd.DataFrame([{'full_name': selected_player_name, 'player_id': new_player_id, 'position': new_player_pos, pos_col: pos_lookup_val}])
                    st.session_state.dashboard_data[team_type][lineup_df_key] = pd.concat([lineup_df, new_row], ignore_index=True)
        elif row_index:
            idx = row_index[0]
            st.session_state.dashboard_data[team_type][lineup_df_key].loc[idx, ['full_name', 'player_id', 'position']] = [None, None, None]
    
    if "PP" in line_name:
        lineup_df, pos_col = team_data.get('pp_lineup', pd.DataFrame()), 'pp_position'
    elif "PK" in line_name:
        lineup_df, pos_col = team_data.get('pk_lineup', pd.DataFrame()), 'pk_position'
    else:
        lineup_df, pos_col = team_data.get('lineup', pd.DataFrame()), 'position_slot'
    
    def render_player(pos_lookup_val):
        default_player_name, default_player_id, default_index = None, "N/A", 0
        roster_options = [""] + player_names
        if not lineup_df.empty and pos_col in lineup_df.columns:
            player_row = lineup_df[lineup_df[pos_col] == pos_lookup_val]
            if not player_row.empty and pd.notna(player_row['full_name'].iloc[0]):
                default_player_name = player_row['full_name'].iloc[0]
                default_player_id = player_row['player_id'].iloc[0]
                if default_player_name in roster_options:
                    default_index = roster_options.index(default_player_name)
        id_col, name_col = st.columns([1, 3])
        with id_col:
            is_selected = str(default_player_id) == str(team_data.get('selected_player_id'))
            st.button(
                label=str(default_player_id),
                key=f"{team_type}_{default_player_id}_{pos_lookup_val}_select",
                on_click=select_player, args=(team_type, str(default_player_id), default_player_name),
                disabled=(str(default_player_id) == "N/A"),
                use_container_width=True,
                type=("primary" if is_selected else "secondary")
            )
        with name_col:
            st.selectbox(
                label=''.join(c for c in pos_lookup_val if c.isalpha()), options=roster_options, index=default_index,
                key=f"{team_type}_{line_name}_{pos_lookup_val}_name",
                label_visibility="collapsed",
                on_change=update_player_in_lineup, args=(pos_lookup_val,)
            )

    if "PP" in line_name:
        top_row, bottom_row = st.columns(3), st.columns(2)
        for i, pos in enumerate(positions[:3]):
            with top_row[i]: render_player(pos)
        for i, pos in enumerate(positions[3:]):
            with bottom_row[i]: render_player(pos)
    elif "PK" in line_name:
        top_row, bottom_row = st.columns(2), st.columns(2)
        for i, pos in enumerate(positions[:2]):
            with top_row[i]: render_player(pos)
        for i, pos in enumerate(positions[2:]):
            with bottom_row[i]: render_player(pos)
    else:
        cols = st.columns(len(positions))
        for i, pos in enumerate(positions):
            with cols[i]: render_player(pos)


def _render_goalie_ui(team_type: str, team_data: dict):
    """Renders the UI for selecting the starting goalie."""
    st.markdown("---")
    st.markdown("##### Starting Goalie")
    goalie_roster = team_data.get('goalie_roster', pd.DataFrame())
    if goalie_roster.empty:
        st.warning("No goalies found for this team.")
        return
    goalie_names = goalie_roster['full_name'].tolist()
    current_goalie = team_data.get('starting_goalie')
    try:
        current_index = goalie_names.index(current_goalie['full_name']) if current_goalie else 0
    except (ValueError, TypeError, KeyError):
        current_index = 0
    
    def on_goalie_change():
        selected_name = st.session_state[f"{team_type}_goalie_selector"]
        selected_goalie_row = goalie_roster[goalie_roster['full_name'] == selected_name]
        if not selected_goalie_row.empty:
            st.session_state.dashboard_data[team_type]['starting_goalie'] = selected_goalie_row.iloc[0].to_dict()
    
    id_col, name_col = st.columns([1, 3])
    with id_col:
        goalie_id = current_goalie.get('player_id', 'N/A') if current_goalie else 'N/A'
        is_selected = str(goalie_id) == str(team_data.get('selected_player_id'))
        st.button(
            label=str(goalie_id),
            key=f"{team_type}_{goalie_id}_goalie_select",
            on_click=select_player, 
            args=(team_type, str(goalie_id), current_goalie['full_name'] if current_goalie else "N/A"),
            disabled=(str(goalie_id) == "N/A"),
            use_container_width=True,
            type=("primary" if is_selected else "secondary")
        )
    with name_col:
        st.selectbox(
            label="GoalieSelect", options=goalie_names, index=current_index,
            key=f"{team_type}_goalie_selector", on_change=on_goalie_change,
            label_visibility="collapsed"
        )


def _render_coach_editor(team_type: str, team_data: dict):
    """Renders the ratings editor expander for the currently selected coach."""
    coach_data = team_data.get('coach_data', {})
    coach_name = coach_data.get('coach', 'N/A')
    team_id = team_data.get('team_id')

    with st.expander(f"⚙️ Editing Ratings for Coach: **{coach_name}**", expanded=True):
        st.markdown("##### Power Play Unit Shares")
        
        # --- PP Slider ---
        pp_shares = coach_data.get('pp_unit_shares', {'PP1': 0.60, 'PP2': 0.40})
        pp1_share_percent = int(pp_shares.get('PP1', 0.60) * 100)
        
        new_pp1_percent = st.slider(
            "PP1 Share (%)", min_value=0, max_value=100, value=pp1_share_percent,
            key=f"{team_type}_pp_share_slider"
        )
        pp2_share_percent = 100 - new_pp1_percent
        st.text(f"PP2 Share: {pp2_share_percent}%")

        st.divider()
        st.markdown("##### Penalty Kill Unit Shares")
        
        # --- PK Slider ---
        pk_shares = coach_data.get('pk_unit_shares', {'PK1': 0.55, 'PK2': 0.45})
        pk1_share_percent = int(pk_shares.get('PK1', 0.55) * 100)

        new_pk1_percent = st.slider(
            "PK1 Share (%)", min_value=0, max_value=100, value=pk1_share_percent,
            key=f"{team_type}_pk_share_slider"
        )
        pk2_share_percent = 100 - new_pk1_percent
        st.text(f"PK2 Share: {pk2_share_percent}%")
        
        # --- Save/Cancel Buttons ---
        save_col, cancel_col = st.columns(2)
        with save_col:
            if st.button("Save Coach Ratings", key=f"save_coach_{team_type}", use_container_width=True, type="primary"):
                # Reconstruct the dictionaries
                new_pp_unit_shares = {
                    "PP1": new_pp1_percent / 100.0,
                    "PP2": pp2_share_percent / 100.0
                }
                new_pk_unit_shares = {
                    "PK1": new_pk1_percent / 100.0,
                    "PK2": pk2_share_percent / 100.0
                }
                
                # Create payload and save to DB
                payload = {
                    'pp_unit_shares': new_pp_unit_shares,
                    'pk_unit_shares': new_pk_unit_shares
                }
                save_coach_ratings(team_id, payload)
                
                # Update session state and close editor
                st.session_state.dashboard_data[team_type]['coach_data'].update(payload)
                st.session_state.dashboard_data[team_type]['show_coach_edit_modal'] = False
                st.success(f"Coach ratings for {coach_name} saved!")
                st.rerun()

        with cancel_col:
            if st.button("Cancel", key=f"cancel_coach_{team_type}", use_container_width=True):
                st.session_state.dashboard_data[team_type]['show_coach_edit_modal'] = False
                st.rerun()


def render_team_ui(team_type: str, teams_df: pd.DataFrame):
    """Renders the entire UI for one team (Home or Away) on the dashboard."""
    team_data = st.session_state.dashboard_data[team_type]
    is_team_selected = team_data.get('team_id') is not None
    st.markdown(f'<div class="team-container-{team_type}">', unsafe_allow_html=True)
    if is_team_selected:
        team_name = team_data.get('team_name', f"{team_type.capitalize()} Team")
        team_row = teams_df[teams_df['team_id'] == team_data['team_id']]
        team_color = team_row['team_color_primary'].iloc[0] if not team_row.empty and pd.notna(team_row['team_color_primary'].iloc[0]) else "#888888"
        secondary_color = team_row['team_color_secondary'].iloc[0] if not team_row.empty and pd.notna(team_row['team_color_secondary'].iloc[0]) else "#FFFFFF"
        st.markdown(f'<div style="background-color:{team_color};color:{secondary_color};padding:10px;border-radius:5px;margin-bottom:1rem;text-align:center;"><h3>{team_name}</h3></div>', unsafe_allow_html=True)
        roster_df = team_data.get('roster', pd.DataFrame())
        player_names = roster_df['full_name'].tolist() if not roster_df.empty else []
        coach_info = team_data.get('coach_data', {})
        
        if coach_info:
            def toggle_coach_editor(team_type: str):
                st.session_state.dashboard_data[team_type]['show_coach_edit_modal'] = not st.session_state.dashboard_data[team_type].get('show_coach_edit_modal', False)

            id_col, name_col = st.columns([1, 4])
            with id_col:
                # This is now a button that opens the editor
                st.button(
                    label=str(coach_info.get('coach_id', 'N/A')),
                    key=f"edit_coach_{team_type}",
                    on_click=toggle_coach_editor,
                    args=(team_type,),
                    use_container_width=True
                )
            with name_col:
                st.text_input(
                    "Coach", value=coach_info.get('coach', 'N/A'), disabled=True,
                    key=f"{team_type}_coach_name", label_visibility="collapsed"
                )

            # Call the editor if its state is true
            if team_data.get('show_coach_edit_modal'):
                _render_coach_editor(team_type, team_data)
            
        es_tab, pp_tab, pk_tab = st.tabs(["Even Strength", "Power Play", "Penalty Kill"])
        with es_tab:
            for name, pos in all_definitions.items():
                if "Line" in name or "Pair" in name: _render_lineup_rows(team_type, name, pos, team_data, player_names)
        with pp_tab:
            for name, pos in all_definitions.items():
                if "PP" in name: _render_lineup_rows(team_type, name, pos, team_data, player_names, 'PP')
        with pk_tab:
            for name, pos in all_definitions.items():
                if "PK" in name: _render_lineup_rows(team_type, name, pos, team_data, player_names, 'PK')
        
        _render_goalie_ui(team_type, team_data)

        if team_data.get('show_edit_modal') and team_data.get('selected_player_id'):
            _render_ratings_editor(team_type, team_data)
    st.markdown('</div>', unsafe_allow_html=True)


def render_unit(line_name, positions, lineup_df, roster_df, roster_names, toi_component: str = 'Total'):
    """Renders a single line/unit for the Lineup Builder page."""
    if "PP" in line_name: position_col_name = 'pp_position'
    elif "PK" in line_name: position_col_name = 'pk_position'
    else: position_col_name = 'position_slot'
    st.markdown(f"**{line_name}**")
    line_cols = st.columns([3] * len(positions) + [1.5])
    current_line_player_ids = []
    for i, pos in enumerate(positions):
        with line_cols[i]:
            widget_key = f"{line_name.replace(' ', '_')}_{pos.replace(' ', '_')}"
            default_index = None
            if not lineup_df.empty and position_col_name in lineup_df.columns:
                default_player = lineup_df[lineup_df[position_col_name] == pos]
                if not default_player.empty and pd.notna(default_player['full_name'].iloc[0]):
                    default_name = default_player['full_name'].iloc[0]
                    try:
                        default_index = roster_names.index(default_name)
                    except (ValueError, TypeError):
                        default_index = None
            selected_player_name = st.selectbox(
                label=pos, options=roster_names, index=default_index,
                placeholder="Select Player...", key=widget_key
            )
            if selected_player_name:
                player_id = roster_df[roster_df['full_name'] == selected_player_name]['player_id'].iloc[0]
                current_line_player_ids.append(player_id)
                if st.session_state.toi_results and selected_player_name in st.session_state.toi_results:
                    toi_value = st.session_state.toi_results[selected_player_name].get(toi_component, 0)
                    toi_min, toi_sec = divmod(toi_value * 60, 60)
                    st.caption(f"TOI: **{int(toi_min)}:{int(toi_sec):02d}**")
    line_score = calculate_line_score(current_line_player_ids)
    with line_cols[-1]:
        st.metric("Unit Score", f"{line_score:.2f}")


def render_lineup_ui():
    """Renders the main UI for the Lineup Builder page."""
    st.header("2. Build Lines")
    es_lineup_df = st.session_state.current_lineup
    pp_lineup_df = st.session_state.pp_lineup
    pk_lineup_df = st.session_state.pk_lineup
    roster_df = st.session_state.current_roster
    if roster_df.empty:
        st.error("No roster data found. Please select a team.")
        return
    roster_names = roster_df['full_name'].tolist()
    tab_es, tab_pp, tab_pk = st.tabs(["Even Strength", "PP", "PK"])
    with tab_es:
        st.subheader("Forward Lines")
        for line_name, positions in list(all_definitions.items())[:4]:
            if "Line" in line_name: render_unit(line_name, positions, es_lineup_df, roster_df, roster_names)
        st.subheader("Defense Pairs")
        for line_name, positions in list(all_definitions.items())[4:]:
            if "Pair" in line_name: render_unit(line_name, positions, es_lineup_df, roster_df, roster_names)
    with tab_pp:
        st.subheader("Power Play Units")
        for line_name, positions in all_definitions.items():
            if "PP" in line_name: render_unit(line_name, positions, pp_lineup_df, roster_df, roster_names, toi_component='PP')
    with tab_pk:
        st.subheader("Penalty Kill Units")
        for line_name, positions in all_definitions.items():
            if "PK" in line_name: render_unit(line_name, positions, pk_lineup_df, roster_df, roster_names, toi_component='PK')