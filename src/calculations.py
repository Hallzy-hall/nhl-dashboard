import streamlit as st
import numpy as np
import pandas as pd
import math
from scipy.stats import poisson

# ==============================================================================
# --- CONFIGURATIONS ---
# ==============================================================================

# Defines the vig (margin) percentage for each market type.
MARKET_MARGINS = {
    "moneyline": 0.00,
    "puckline": 0.00,
    "total": 0.00,
    "player_props": 0.04 # 4% vig on player props
}


# ==============================================================================
# --- HELPER & TOI FUNCTIONS ---
# ==============================================================================

def calculate_toi_distribution(coach_profile, game_roster, pim_for, pim_against):
    """
    Calculates a realistic TOI distribution for a given roster and penalty scenario.
    """
    player_toi = {p['name']: {'PP': 0, 'PK': 0, 'ES': 0} for p in game_roster}

    pp_shares = coach_profile.get('pp_unit_shares', {})
    pk_shares = coach_profile.get('pk_unit_shares', {})

    for p in game_roster:
        for role in p.get('st_roles', []):
            if role == 'PP1': player_toi[p['name']]['PP'] = pim_against * pp_shares.get('PP1', 0.60)
            elif role == 'PP2': player_toi[p['name']]['PP'] = pim_against * pp_shares.get('PP2', 0.40)
            elif role == 'PK1': player_toi[p['name']]['PK'] = pim_for * pk_shares.get('PK1', 0.55)
            elif role == 'PK2': player_toi[p['name']]['PK'] = pim_for * pk_shares.get('PK2', 0.45)

    total_skater_minutes = 300
    pp_skater_minutes_used = pim_against * 5
    pk_skater_minutes_used = pim_for * 4
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
    """ Placeholder function to prevent import errors. """
    st.warning("`calculate_line_score` is deprecated and should be removed.", icon="⚠️")
    return 0


# ==============================================================================
# --- CORE ODDS CONVERSION FUNCTIONS ---
# ==============================================================================

def _probability_to_american_odds(prob: float) -> int:
    """Converts a probability to American odds."""
    if prob <= 0: return 99999
    if prob >= 1: return -99999
    if prob >= 0.5:
        return round(-1 * (prob / (1 - prob)) * 100)
    else:
        return round(((1 - prob) / prob) * 100)

def _probability_to_decimal_odds(prob: float) -> float:
    """Converts a probability to Decimal odds."""
    if prob <= 0: return 999.0
    return round(1 / prob, 2)

def _poisson_pmf(k, lam):
    """Calculates the probability mass function for a Poisson distribution."""
    return poisson.pmf(k, lam)


# ==============================================================================
# --- MAIN CALCULATION ENGINES ---
# ==============================================================================

def calculate_betting_odds(all_game_scores: list):
    """
    Calculates moneyline, puckline, and total odds from raw simulation scores.
    """
    if not all_game_scores:
        return {}
    
    scores_df = pd.DataFrame(all_game_scores, columns=['home_score', 'away_score'])
    
    odds = {}
    
    # --- Moneyline Calculation (FIXED) ---
    home_wins = (scores_df['home_score'] > scores_df['away_score']).sum()
    away_wins = (scores_df['away_score'] > scores_df['home_score']).sum()
    total_decisions = home_wins + away_wins
    
    if total_decisions == 0:
        home_win_prob, away_win_prob = 0.5, 0.5
    else:
        home_win_prob = home_wins / total_decisions
        away_win_prob = away_wins / total_decisions

    margin = MARKET_MARGINS.get("moneyline", 0)
    denominator_ml = home_win_prob + away_win_prob + margin
    home_win_prob_vig = home_win_prob / denominator_ml if denominator_ml > 0 else 0
    away_win_prob_vig = away_win_prob / denominator_ml if denominator_ml > 0 else 0

    home_american_ml = _probability_to_american_odds(home_win_prob_vig)
    away_american_ml = _probability_to_american_odds(away_win_prob_vig)

    odds['moneyline'] = {
        'home': home_american_ml,
        'away': away_american_ml,
        'home_american': home_american_ml,
        'away_american': away_american_ml,
        'home_decimal': _probability_to_decimal_odds(home_win_prob_vig),
        'away_decimal': _probability_to_decimal_odds(away_win_prob_vig),
    }

    # --- Puckline Calculation ---
    home_puckline_spread = -1.5
    away_puckline_spread = +1.5
    
    home_covers_prob = (scores_df['home_score'] + home_puckline_spread > scores_df['away_score']).mean()
    away_covers_prob = 1 - home_covers_prob
    
    margin_pl = MARKET_MARGINS.get("puckline", 0)
    denominator_pl = home_covers_prob + away_covers_prob + margin_pl
    home_covers_prob_vig = home_covers_prob / denominator_pl if denominator_pl > 0 else 0
    away_covers_prob_vig = away_covers_prob / denominator_pl if denominator_pl > 0 else 0

    home_american_pl = _probability_to_american_odds(home_covers_prob_vig)
    away_american_pl = _probability_to_american_odds(away_covers_prob_vig)
    
    odds['puckline'] = {
        'home_spread': home_puckline_spread, 'away_spread': away_puckline_spread,
        'home_odds': home_american_pl, 'away_odds': away_american_pl,
        'home_american': home_american_pl, 'away_american': away_american_pl,
        'home_decimal': _probability_to_decimal_odds(home_covers_prob_vig),
        'away_decimal': _probability_to_decimal_odds(away_covers_prob_vig),
    }
    
    # --- Total Calculation ---
    total_goals = scores_df['home_score'] + scores_df['away_score']
    median_total = total_goals.median()
    total_line = round(median_total * 2) / 2
    
    over_prob = (total_goals > total_line).mean()
    under_prob = (total_goals < total_line).mean()
    
    margin_total = MARKET_MARGINS.get("total", 0)
    denominator_total = over_prob + under_prob + margin_total
    over_prob_vig = over_prob / denominator_total if denominator_total > 0 else 0
    under_prob_vig = under_prob / denominator_total if denominator_total > 0 else 0

    over_american_total = _probability_to_american_odds(over_prob_vig)
    under_american_total = _probability_to_american_odds(under_prob_vig)
    
    odds['total'] = {
        'line': total_line,
        'over': over_american_total, 'under': under_american_total,
        'over_american': over_american_total, 'under_american': under_american_total,
        'over_decimal': _probability_to_decimal_odds(over_prob_vig),
        'under_decimal': _probability_to_decimal_odds(under_prob_vig),
    }

    return odds

def calculate_player_props(player_stats_df: pd.DataFrame, home_team_info: dict, away_team_info: dict):
    """
    Calculates player prop odds, now including team color information.
    """
    if player_stats_df.empty:
        return {}
        
    props_data = {'goals': [], 'assists': [], 'points': [], 'shots': [], 'blocks': []}
    margin = MARKET_MARGINS.get("player_props", 0.0)

    expected_stat_cols = {
        'goals': 'Goals_Total', 'assists': 'Assists_Total',
        'shots': 'Shots_Total', 'blocks': 'Blocks_Total'
    }

    player_stats_df['Points_Total'] = player_stats_df[expected_stat_cols['goals']] + player_stats_df[expected_stat_cols['assists']]
    expected_stat_cols['points'] = 'Points_Total'

    for _, player_row in player_stats_df.iterrows():
        team_name = player_row.get('team_name')
        if team_name == home_team_info.get('team_full_name'):
            team_color = home_team_info.get('team_color_primary', None)
        elif team_name == away_team_info.get('team_full_name'):
            team_color = away_team_info.get('team_color_primary', None)
        else:
            team_color = None

        for prop_market, stat_col in expected_stat_cols.items():
            expected_value = player_row.get(stat_col, 0)
            if expected_value <= 0: continue

            if prop_market in ['goals', 'assists', 'points']:
                line = 0.5
                prob_under = _poisson_pmf(0, expected_value)
            elif prop_market in ['shots', 'blocks']:
                line = round(expected_value * 2) / 2
                if line == 0: line = 0.5
                k_values_under = np.arange(0, int(line) if line.is_integer() else int(line) + 1)
                prob_under = sum(_poisson_pmf(k, expected_value) for k in k_values_under)
            else:
                continue
            
            prob_over = 1 - prob_under
            
            denominator = prob_over + prob_under + margin
            prob_over_vig = prob_over / denominator if denominator > 0 else 0
            prob_under_vig = prob_under / denominator if denominator > 0 else 0

            props_data[prop_market].append({
                'player': player_row['Player'],
                'line': line,
                'team_color': team_color,
                'over_american': _probability_to_american_odds(prob_over_vig),
                'under_american': _probability_to_american_odds(prob_under_vig),
                'over_decimal': _probability_to_decimal_odds(prob_over_vig),
                'under_decimal': _probability_to_decimal_odds(prob_under_vig)
            })

    return props_data

