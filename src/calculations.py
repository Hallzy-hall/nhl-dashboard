import streamlit as st
import numpy as np
import pandas as pd
import math

def calculate_toi_distribution(coach_profile, game_roster, pim_for, pim_against):
    """
    Calculates a realistic TOI distribution for a given roster and penalty scenario.
    This revised function correctly accounts for total skater-minutes available.
    """
    player_toi = {p['name']: {'PP': 0, 'PK': 0, 'ES': 0} for p in game_roster}

    # Step 1: Allocate Special Teams TOI (Unchanged)
    pp_shares = coach_profile.get('pp_unit_shares', {})
    pk_shares = coach_profile.get('pk_unit_shares', {})

    for p in game_roster:
        for role in p.get('st_roles', []):
            if role == 'PP1': player_toi[p['name']]['PP'] = pim_against * pp_shares.get('PP1', 0.60)
            elif role == 'PP2': player_toi[p['name']]['PP'] = pim_against * pp_shares.get('PP2', 0.40)
            elif role == 'PK1': player_toi[p['name']]['PK'] = pim_for * pk_shares.get('PK1', 0.55)
            elif role == 'PK2': player_toi[p['name']]['PK'] = pim_for * pk_shares.get('PK2', 0.45)

    total_skater_minutes = 300
    pp_skater_minutes_used = pim_against * 5 # Power plays use 5 skaters
    pk_skater_minutes_used = pim_for * 4     # Penalty kills use 4 skaters
    total_es_skater_minutes = total_skater_minutes - pp_skater_minutes_used - pk_skater_minutes_used

    T_ES_Forwards_Total = total_es_skater_minutes * 0.6
    T_ES_Defense_Total = total_es_skater_minutes * 0.4

    es_players = [p for p in game_roster if p.get('line') and p.get('line').startswith(('F', 'D'))]
    forward_players = [p for p in es_players if p['position'] in ['L', 'C', 'R']]
    defense_players = [p for p in es_players if p['position'] == 'D']
    es_profile = coach_profile.get('toi_profile', {})

    if forward_players:
        total_fwd_score = sum(es_profile.get('forwards', {}).get(p['line'], 0) * (p.get('toi_individual_rating', 1000) / 1000.0) for p in forward_players)
        if total_fwd_score > 0:
            for p in forward_players:
                score = es_profile.get('forwards', {}).get(p['line'], 0) * (p.get('toi_individual_rating', 1000) / 1000.0)
                player_toi[p['name']]['ES'] = (score / total_fwd_score) * T_ES_Forwards_Total

    if defense_players:
        total_def_score = sum(es_profile.get('defense', {}).get(p['line'], 0) * (p.get('toi_individual_rating', 1000) / 1000.0) for p in defense_players)
        if total_def_score > 0:
            for p in defense_players:
                score = es_profile.get('defense', {}).get(p['line'], 0) * (p.get('toi_individual_rating', 1000) / 1000.0)
                player_toi[p['name']]['ES'] = (score / total_def_score) * T_ES_Defense_Total

    final_results = {}
    for name, toi_parts in player_toi.items():
        if any(p['name'] == name for p in game_roster):
            toi_parts['Total'] = toi_parts['PP'] + toi_parts['PK'] + toi_parts['ES']
            final_results[name] = toi_parts

    return final_results


def calculate_line_score(player_ids: list):
    # This function depends on Streamlit's session state
    if 'player_ratings' not in st.session_state: return 0
    all_ratings_df = st.session_state.player_ratings
    if all_ratings_df.empty or not player_ids: return 0
    line_ratings_df = all_ratings_df[all_ratings_df['player_id'].isin(player_ids)]
    if line_ratings_df.empty or 'por' not in line_ratings_df.columns: return 0
    return line_ratings_df['por'].sum()


def calculate_expected_pim(home_lineup_df, away_lineup_df):
    # This function depends on Streamlit's session state
    if 'dashboard_data' not in st.session_state: return {}
    # ... (rest of the function is unchanged)
    pass

def calculate_per_60_stats(player_df: pd.DataFrame):
    # ... (this function is unchanged)
    pass

# --- NEW FUNCTIONS FOR BETTING ODDS ---

def _probability_to_american_odds(prob: float):
    """Converts a probability (0.0 to 1.0) into American odds format."""
    if prob <= 0 or prob >= 1:
        return 0 # Return a default/neutral value for display
    
    if prob < 0.5:
        return int(round(((1 - prob) / prob) * 100, 0))
    else:
        return int(round(-1 * (prob / (1 - prob)) * 100, 0))

def calculate_betting_odds(all_game_scores: list):
    """
    Calculates Moneyline, Total, and Puckline odds from a list of simulated game scores.
    Each score in the list is a tuple: (home_goals, away_goals).
    """
    if not all_game_scores:
        return {}

    num_sims = len(all_game_scores)
    VIG_PERCENTAGE = 0.045 # Standard ~4.5% vig
    
    # --- 1. Moneyline Calculation ---
    home_wins = sum(1 for h, a in all_game_scores if h > a)
    away_wins = sum(1 for h, a in all_game_scores if a > h)
    
    total_decisions = home_wins + away_wins
    if total_decisions == 0: return {} # Avoid division by zero if all games are ties
    
    home_win_prob = home_wins / total_decisions
    away_win_prob = away_wins / total_decisions

    # Apply vig by slightly increasing each probability before converting
    vig_adjustment = VIG_PERCENTAGE / 2
    vigged_home_prob = home_win_prob + vig_adjustment if home_win_prob > away_win_prob else home_win_prob - vig_adjustment
    vigged_away_prob = away_win_prob + vig_adjustment if away_win_prob > home_win_prob else away_win_prob - vig_adjustment
    
    home_ml_odds = _probability_to_american_odds(vigged_home_prob)
    away_ml_odds = _probability_to_american_odds(vigged_away_prob)
    
    # --- 2. Game Total Calculation ---
    game_totals = [h + a for h, a in all_game_scores]
    median_total = np.median(game_totals)
    main_line = round(median_total * 2) / 2
    
    # --- 3. Puckline Calculation ---
    home_is_favorite = home_win_prob >= 0.5
    
    if home_is_favorite:
        home_spread, away_spread = -1.5, +1.5
        home_covers = sum(1 for h, a in all_game_scores if (h - a) > 1.5)
        home_cover_prob = home_covers / num_sims
        away_cover_prob = 1.0 - home_cover_prob
    else:
        home_spread, away_spread = +1.5, -1.5
        away_covers = sum(1 for h, a in all_game_scores if (a - h) > 1.5)
        away_cover_prob = away_covers / num_sims
        home_cover_prob = 1.0 - away_cover_prob

    # Apply vig to puckline probabilities
    vigged_home_pl_prob = home_cover_prob + vig_adjustment if home_cover_prob > away_cover_prob else home_cover_prob - vig_adjustment
    vigged_away_pl_prob = away_cover_prob + vig_adjustment if away_cover_prob > home_cover_prob else away_cover_prob - vig_adjustment

    home_pl_odds = _probability_to_american_odds(vigged_home_pl_prob)
    away_pl_odds = _probability_to_american_odds(vigged_away_pl_prob)

    return {
        'moneyline': {'home': home_ml_odds, 'away': away_ml_odds},
        'total': {'line': main_line, 'over': -110, 'under': -110},
        'puckline': {
            'home_spread': home_spread, 'home_odds': home_pl_odds,
            'away_spread': away_spread, 'away_odds': away_pl_odds
        }
    }