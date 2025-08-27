# All rates are in "events per 60 minutes" of the relevant state.
BASE_HAZARD_RATES = {
    # Puck Possession & Transition
    # MODIFIED: Replaced shot_rush and shot_cycle with danger-zone specific rates
    'shot_high_danger': 80.0,
    'shot_medium_danger': 150.0,
    'shot_low_danger': 180.0,
    'pass_attempt': 1125.0,
    'turnover': 110.0,
    'controlled_exit': 650.0,
    'dump_out_exit': 550.0,

    # Stoppages
    'goalie_freeze': 325.0,
    'puck_out_of_play': 40.0,

    # Penalties
    'minor_penalty': 5.5,
    'major_penalty': 0.1,
    'line_change': 100.0,
}


# Global parameters for simulation logic and tuning
SIMULATION_PARAMETERS = {
    'ratings': {
        'std_dev': 250,
        'impact_factor': 0.20,
    },
    'even_strength_logic': {
        'zone_entry_hazard': 150.0,
    },
    'pp_logic': {
        'zone_entry_hazard': 450.0,
        'shot_multiplier': 2.5,
        'pass_multiplier': 2.0,
        'turnover_multiplier': 0.5,
        'five_on_three_shot_multiplier': 4.0,
        'five_on_three_pass_multiplier': 3.0,
        'regroup_pass_hazard': 100.0,
        'regroup_turnover_multiplier': 0.25,
    },
    'pk_logic': {
        'clear_attempt_multiplier': 2.0,
        'turnover_multiplier': 1.5,
        'neutral_zone_clear_hazard': 300.0,
        'successful_clear_prob': 0.85,
    },
    'shot_resolution': {
        'base_block_prob': 0.15,
        'base_miss_prob': 0.25,
        # MODIFIED: Removed base_xg values, as they are now handled by the goalie model
        'pp_goal_prob_bonus': 1.1, # This can be repurposed or removed later
        'base_rebound_prob': 0.3,
        'primary_assist_prob': 0.9,
        'secondary_assist_prob_es': 0.55,
        'secondary_assist_prob_pp': 0.70,
        'secondary_assist_prob_5v3': 0.80,
    },
    'goalie_logic': {
        'lg_avg_ld_sv_pct': 0.978, 
        'lg_avg_md_sv_pct': 0.915,
        'lg_avg_hd_sv_pct': 0.820,
        'sv_pct_swing_factor': 0.05
    },
    'general_logic': {
        'faceoff_rating_divisor': 1000,
        'shift_fatigue_seconds': 45.0,
    }
}