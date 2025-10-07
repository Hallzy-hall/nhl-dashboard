# All rates are in "events per 60 minutes" of the relevant state.
BASE_HAZARD_RATES = {
    # Puck Possession & Transition
    'shot_high_danger': 45.0,
    'shot_medium_danger': 71,
    'shot_low_danger': 125,
    'pass_attempt': 1100.0,
    'turnover': 0.3,
    'controlled_exit': 800.0,
    'dump_out_exit': 400.0,
    'zone_entry_attempt': 350.0,

    # Stoppages
    'goalie_freeze': 325.0,
    'puck_out_of_play': 40.0,

    # Penalties
    'minor_penalty': 5.75,
    'major_penalty': 0.1,
    'line_change': 100.0,
}

# Global parameters for simulation logic and tuning
SIMULATION_PARAMETERS = {
    'ratings': {
        'std_dev': 200,
        'impact_factor': 0.275,
    },
    'even_strength_logic': {
        'zone_entry_hazard': 20.0,
        'base_entry_success_prob': 0.80,
        'dump_in_hazard': 100,},
        

    'pp_logic': {
        'zone_entry_hazard': 450.0,
        'shot_multiplier': 1.85,
        'pass_multiplier': 2.0,
        'turnover_multiplier': 0.3,
        'five_on_three_shot_multiplier': 4.0,
        'five_on_three_pass_multiplier': 3.0,
        'regroup_pass_hazard': 100.0,
        'regroup_turnover_multiplier': 0.2,
    },
    'pk_logic': {
        'clear_attempt_multiplier': 2.0,
        'turnover_multiplier': 1.1,
        'neutral_zone_clear_hazard': 300.0,
        'successful_clear_prob': 0.85,
    },
    'shot_resolution': {
        'base_block_prob': 0.15,
        'base_miss_prob': 0.46,
        'pp_goal_prob_bonus': 1.2,
        'base_rebound_prob': 0.3,
        'primary_assist_prob': 0.85,
        'secondary_assist_prob_es': 0.50,
        'secondary_assist_prob_pp': 0.70,
        'secondary_assist_prob_5v3': 0.80,
    },
    'goalie_logic': {
        'lg_avg_ld_sv_pct': 0.961, 
        'lg_avg_md_sv_pct': 0.890,
        'lg_avg_hd_sv_pct': 0.800,
        'sv_pct_swing_factor': 0.05
    },
    'general_logic': {
        'faceoff_rating_divisor': 1000,
        'shift_fatigue_seconds': 45.0,
    }
}