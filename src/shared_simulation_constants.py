from dataclasses import dataclass, field
from typing import List, Optional

# --- Shared Data Structures ---
@dataclass
class PlayerProfile:
    player_id: int
    position: str
    line: str
    st_roles: List[str]
    name: Optional[str] = None
    full_name: Optional[str] = None
    team: Optional[str] = None

    # All rating fields remain the same
    toi_individual_rating: int = 1000
    faceoff_rating: float = 50.0
    opuck_possession: float = 50.0
    d_breakout_ability: float = 50.0
    entry_volume: float = 50.0
    ozone_entry: float = 50.0
    d_entry_denial: float = 50.0
    ocycle_play: float = 50.0
    d_cycle_defense: float = 50.0
    oprime_playmaking: float = 50.0
    osecond_playmaking: float = 50.0
    dprime_playmaking_denial: float = 50.0
    shooting_volume: float = 50.0
    ofinishing: float = 50.0
    shooting_accuracy: float = 50.0
    orebound_creation: float = 50.0
    hdshot_creation: float = 50.0
    mshot_creation: float = 50.0
    o_hd_shot_creation_rating: float = 50.0
    d_hd_shot_suppression_rating: float = 50.0
    o_md_shot_creation_rating: float = 50.0
    d_md_shot_suppression_rating: float = 50.0
    o_ld_shot_creation_rating: float = 50.0
    d_ld_shot_suppression_rating: float = 50.0
    d_shot_blocking: float = 50.0
    o_forechecking_pressure: float = 50.0
    openalty_drawn: float = 50.0
    min_penalty: float = 50.0
    maj_penalty: float = 50.0
    # PP and PK specific ratings
    pp_shot_volume: float = 50.0
    pp_shot_on_net: float = 50.0
    pp_chance_creation: float = 50.0
    pp_playmaking: float = 50.0
    pp_zone_entry: float = 50.0
    pp_finishing: float = 50.0
    pp_rebound_creation: float = 50.0
    pk_shot_suppression: float = 50.0
    pk_clearing_ability: float = 50.0
    pk_shot_blocking: float = 50.0

@dataclass
class GoalieProfile:
    player_id: int
    team: str
    name: Optional[str] = None
    full_name: Optional[str] = None
    position: Optional[str] = 'G'
    g_low_danger_sv_rating: float = 97.0
    g_medium_danger_sv_rating: float = 92.0
    g_high_danger_sv_rating: float = 85.0
    g_rebound_control_rating: float = 50.0
    g_freeze_puck_rating: float = 50.0
    goalie_save_adj: float = 50.0
    rebound_control_adj: float = 50.0
    g_ld_save_5v5: float = 50.0
    g_ld_save_4v5: float = 50.0
    g_md_save_5v5: float = 50.0
    g_md_save_4v5: float = 50.0
    g_hd_save_5v5: float = 50.0
    g_hd_save_4v5: float = 50.0


# --- Shared Simulation Constants ---
# These dictionaries remain unchanged
SIMULATION_PARAMETERS = {
    'ratings': {'std_dev': 200, 'impact_factor': 0.275},
    'even_strength_logic': {'base_entry_success_prob': 0.80, 'dump_in_hazard': 100.0},
    'pp_logic': {'shot_multiplier': 1.65, 'pass_multiplier': 2.0, 'turnover_multiplier': 0.3},
    'pk_logic': {'clear_attempt_multiplier': 2.0, 'successful_clear_prob': 0.85},
    'shot_resolution': {'base_block_prob': 0.15, 'base_miss_prob': 0.46, 'base_rebound_prob': 0.3, 'primary_assist_prob': 0.85, 'secondary_assist_prob_es': 0.50, 'secondary_assist_prob_pp': 0.70},
    'goalie_logic': {'lg_avg_ld_sv_pct': 0.961, 'lg_avg_md_sv_pct': 0.890, 'lg_avg_hd_sv_pct': 0.800, 'sv_pct_swing_factor': 0.05},
    'general_logic': {'faceoff_rating_divisor': 1000, 'shift_fatigue_seconds': 45.0} # Added fatigue for safety
}
BASE_HAZARD_RATES = {
    'shot_high_danger': 35.0, 'shot_medium_danger': 46.0, 'shot_low_danger': 105.0,
    'pass_attempt': 1100.0, 'turnover': 0.3, 'controlled_exit': 800.0,
    'dump_out_exit': 400.0, 'zone_entry_attempt': 350.0, 'minor_penalty': 5.75,
    'line_change': 50.0 # Added for safety
}
