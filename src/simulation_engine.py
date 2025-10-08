# src/simulation_engine.py (Final Corrected and Unredacted Version)
import numpy as np
import pandas as pd
import random
import multiprocessing
import dataclasses
import json
from dataclasses import dataclass
from src.simulation_constants import BASE_HAZARD_RATES, SIMULATION_PARAMETERS

# --- Load the schema once when the module is imported ---
try:
    with open('schemas/dataframe_schema.json', 'r') as f:
        DATAFRAME_SCHEMA = json.load(f)
except FileNotFoundError:
    print("FATAL ERROR: schemas/dataframe_schema.json not found.")
    print("Please run the create_schema.py script locally before deploying.")
    DATAFRAME_SCHEMA = None
# ---

@dataclass
class PlayerProfile:
    # This dataclass is complete and correct
    player_id: int; name: str; position: str; line: str; st_roles: list
    toi_individual_rating: int = 1000; shooting_volume: int = 1000; shooting_accuracy: int = 1000
    hdshot_creation: int = 1000; mshot_creation: int = 1000; ofinishing: int = 1000
    orebound_creation: int = 1000; oprime_playmaking: int = 1000; osecond_playmaking: int = 1000
    faceoff_rating: int = 1000; ozone_entry: int = 1000; opuck_possession: int = 1000
    ocycle_play: int = 1000; openalty_drawn: int = 1000; d_breakout_ability: int = 1000
    d_entry_denial: int = 1000; o_forechecking_pressure: int = 1000; d_cycle_defense: int = 1000
    d_shot_blocking: int = 1000; min_penalty: int = 1000; maj_penalty: int = 1000
    o_hd_shot_creation_rating: int = 1000; o_md_shot_creation_rating: int = 1000; o_ld_shot_creation_rating: int = 1000
    d_hd_shot_suppression_rating: int = 1000; d_md_shot_suppression_rating: int = 1000; d_ld_shot_suppression_rating: int = 1000
    pp_shot_volume: int = 1000; pp_shot_on_net: int = 1000; pp_chance_creation: int = 1000
    pp_playmaking: int = 1000; pp_zone_entry: int = 1000; pp_finishing: int = 1000
    pp_rebound_creation: int = 1000; pk_shot_suppression: int = 1000; pk_clearing_ability: int = 1000
    pk_shot_blocking: int = 1000
    entry_volume: int = 1000

class GameSimulator:
    # This entire class is now complete and correct
    def __init__(self, home_team_data, away_team_data):
        self.home_team = home_team_data
        self.away_team = away_team_data
        
        profile_fields = {f.name for f in dataclasses.fields(PlayerProfile)}

        def create_player_dict(team_df):
            player_dict = {}
            for _, player_row in team_df.iterrows():
                player_data = player_row.to_dict()
                if not isinstance(player_data.get('st_roles'), (list, tuple)):
                    player_data['st_roles'] = []
                filtered_data = {k: v for k, v in player_data.items() if k in profile_fields}
                player_profile = PlayerProfile(**filtered_data)
                player_dict[player_profile.player_id] = player_profile
            return player_dict

        self.home_players_dict = create_player_dict(home_team_data['lineup'])
        self.away_players_dict = create_player_dict(away_team_data['lineup'])

        self.home_on_ice, self.away_on_ice = {}, {}
        self.home_on_ice_avg, self.away_on_ice_avg = {}, {}
        self.game_clock_seconds = 3600
        self.period, self.possession, self.zone = 1, None, 'neutral'
        self.offensive_zone_state, self.time_in_offensive_zone = None, 0.0
        self.home_skaters, self.away_skaters = 5, 5
        self.penalty_box = []
        self.puck_carrier_id = None
        self.home_shift_time, self.away_shift_time = 0.0, 0.0
        self.params = SIMULATION_PARAMETERS
        self.home_goalie = home_team_data['goalie']
        self.away_goalie = away_team_data['goalie']
        self._initialize_lines()
        self.game_log = []
        self._initialize_stat_trackers()

    def _initialize_lines(self):
        self.home_lines = { 'F1': [p.player_id for p in self.home_players_dict.values() if p.line == 'F1'], 'F2': [p.player_id for p in self.home_players_dict.values() if p.line == 'F2'], 'F3': [p.player_id for p in self.home_players_dict.values() if p.line == 'F3'], 'F4': [p.player_id for p in self.home_players_dict.values() if p.line == 'F4'], 'D1': [p.player_id for p in self.home_players_dict.values() if p.line == 'D1'], 'D2': [p.player_id for p in self.home_players_dict.values() if p.line == 'D2'], 'D3': [p.player_id for p in self.home_players_dict.values() if p.line == 'D3'], 'PP1': [p.player_id for p in self.home_players_dict.values() if 'PP1' in p.st_roles], 'PP2': [p.player_id for p in self.home_players_dict.values() if 'PP2' in p.st_roles], 'PK1': [p.player_id for p in self.home_players_dict.values() if 'PK1' in p.st_roles], 'PK2': [p.player_id for p in self.home_players_dict.values() if 'PK2' in p.st_roles], }
        self.away_lines = { 'F1': [p.player_id for p in self.away_players_dict.values() if p.line == 'F1'], 'F2': [p.player_id for p in self.away_players_dict.values() if p.line == 'F2'], 'F3': [p.player_id for p in self.away_players_dict.values() if p.line == 'F3'], 'F4': [p.player_id for p in self.away_players_dict.values() if p.line == 'F4'], 'D1': [p.player_id for p in self.away_players_dict.values() if p.line == 'D1'], 'D2': [p.player_id for p in self.away_players_dict.values() if p.line == 'D2'], 'D3': [p.player_id for p in self.away_players_dict.values() if p.line == 'D3'], 'PP1': [p.player_id for p in self.away_players_dict.values() if 'PP1' in p.st_roles], 'PP2': [p.player_id for p in self.away_players_dict.values() if 'PP2' in p.st_roles], 'PK1': [p.player_id for p in self.away_players_dict.values() if 'PK1' in p.st_roles], 'PK2': [p.player_id for p in self.away_players_dict.values() if 'PK2' in p.st_roles], }
        self._change_lines('home', 'F1', 'D1')
        self._change_lines('away', 'F1', 'D1')

    def _initialize_stat_trackers(self):
        stat_template = lambda: { 'TOI': 0.0, 'Goals': 0, 'Assists': 0, 'Shots': 0, 'Shot Attempts': 0, 'Blocks': 0, '+/-': 0, 'Penalty Minutes': 0, 'iHDCF': 0, 'iMDCF': 0, 'iLDCF': 0, 'OnIce_CF': 0, 'OnIce_HDCF': 0, 'OnIce_MDCF': 0, 'OnIce_LDCF': 0, 'OnIce_HDCA': 0, 'OnIce_MDCA': 0, 'OnIce_LDCA': 0, 'xG_for': 0.0, 'ReboundsCreated': 0, 'PenaltiesDrawn': 0, 'ControlledEntries': 0, 'ControlledExits': 0, 'OnIce_EntryAttempts_Against': 0, 'OnIce_ControlledEntries_Against': 0, 'ForecheckBreakups': 0, 'PK_Clears': 0, 'xG_against': 0.0, 'Goals_against': 0, 'HD_shots_against': 0, 'HD_goals_against': 0, 'HD_xG_against': 0.0, 'MD_shots_against': 0, 'MD_goals_against': 0, 'MD_xG_against': 0.0, 'LD_shots_against': 0, 'LD_goals_against': 0, 'LD_xG_against': 0.0, 'Saves': 0, 'ReboundsAllowed': 0, 'Freezes': 0, 'Giveaways': 0, 'Takeaways': 0, 'Shots_Off_Cycle': 0, 'Assists_Off_Cycle': 0, 'Faceoffs_Won': 0, 'Faceoffs_Taken': 0, 'MinorPenaltiesTaken': 0, 'MajorPenaltiesTaken': 0, 'EntryDenials': 0, 'FailedEntries': 0 }
        self.home_player_stats = { p.player_id: { 'Player': p.name, 'Total': stat_template(), 'ES': stat_template(), 'PP': stat_template(), 'PK': stat_template() } for p in self.home_players_dict.values() }
        self.away_player_stats = { p.player_id: { 'Player': p.name, 'Total': stat_template(), 'ES': stat_template(), 'PP': stat_template(), 'PK': stat_template() } for p in self.away_players_dict.values() }
        self.home_goalie_stats = stat_template()
        self.home_goalie_stats['Player'] = self.home_goalie['full_name']
        self.away_goalie_stats = stat_template()
        self.away_goalie_stats['Player'] = self.away_goalie['full_name']

    def _get_game_state(self, for_team):
        if self.home_skaters == self.away_skaters: return 'ES'
        if for_team == 'home': return 'PP' if self.home_skaters > self.away_skaters else 'PK'
        if for_team == 'away': return 'PP' if self.away_skaters > self.home_skaters else 'PK'
        return 'ES'

    def _get_player_rating(self, player_id, base_rating_name):
        team_type = 'home' if player_id in self.home_players_dict else 'away'; game_state = self._get_game_state(team_type); player = self.home_players_dict[player_id] if team_type == 'home' else self.away_players_dict[player_id]; RATING_MAP = { 'shooting_volume': {'PP': 'pp_shot_volume'}, 'shooting_accuracy': {'PP': 'pp_shot_on_net'}, 'ofinishing': {'PP': 'pp_finishing'}, 'orebound_creation': {'PP': 'pp_rebound_creation'}, 'oprime_playmaking': {'PP': 'pp_playmaking'}, 'ozone_entry': {'PP': 'pp_zone_entry'}, 'd_shot_blocking': {'PK': 'pk_shot_blocking'}, 'd_hd_shot_suppression_rating': {'PK': 'pk_shot_suppression'}, 'd_md_shot_suppression_rating': {'PK': 'pk_shot_suppression'}, 'd_ld_shot_suppression_rating': {'PK': 'pk_shot_suppression'}, 'd_breakout_ability': {'PK': 'pk_clearing_ability'} }
        if game_state in ['PP', 'PK'] and base_rating_name in RATING_MAP:
            special_state_map = RATING_MAP[base_rating_name]
            if game_state in special_state_map:
                special_rating_name = special_state_map[game_state]
                return getattr(player, special_rating_name, getattr(player, base_rating_name, 1000))
        return getattr(player, base_rating_name, 1000)

    def _increment_stat(self, player_stats, player_id, stat, value, game_state):
        if player_id in player_stats: player_stats[player_id][game_state][stat] += value; player_stats[player_id]['Total'][stat] += value

    def _convert_rating_to_modifier(self, rating, is_defensive=False):
        std_dev = self.params['ratings']['std_dev']; impact_factor = self.params['ratings']['impact_factor']; z_score = (rating - 1000) / std_dev; modifier = 1 + (z_score * impact_factor)
        if is_defensive: modifier = 1 - (z_score * impact_factor)
        return max(0.1, modifier)

    def _change_lines(self, team_type, f_line_name, d_pair_name):
        if team_type == 'home':
            line_ids = self.home_lines.get(f_line_name, []) + self.home_lines.get(d_pair_name, [])
            self.home_on_ice = {pid: self.home_players_dict[pid] for pid in line_ids if pid in self.home_players_dict}
            self.home_shift_time = 0.0
            if self.home_on_ice:
                ratings_df = pd.DataFrame([p.__dict__ for p in self.home_on_ice.values()])
                self.home_on_ice_avg = ratings_df.mean(numeric_only=True).to_dict()
        else:
            line_ids = self.away_lines.get(f_line_name, []) + self.away_lines.get(d_pair_name, [])
            self.away_on_ice = {pid: self.away_players_dict[pid] for pid in line_ids if pid in self.away_players_dict}
            self.away_shift_time = 0.0
            if self.away_on_ice:
                ratings_df = pd.DataFrame([p.__dict__ for p in self.away_on_ice.values()])
                self.away_on_ice_avg = ratings_df.mean(numeric_only=True).to_dict()

    def _get_next_line(self, team_type, position_type):
        coach = self.home_team['coach'] if team_type == 'home' else self.away_team['coach']
        if position_type == 'F':
            lines = ['F1', 'F2', 'F3', 'F4']
            weights = coach.get('toi_profile', {}).get('forwards', {})
            probs = [weights.get(l, 0.25) for l in lines]
        else:
            lines = ['D1', 'D2', 'D3']
            weights = coach.get('toi_profile', {}).get('defense', {})
            probs = [weights.get(l, 0.33) for l in lines]
        prob_sum = sum(probs)
        if prob_sum == 0: return random.choice(lines)
        return random.choices(lines, weights=probs, k=1)[0]

    def _get_next_st_unit(self, team_type, unit_type):
        coach = self.home_team['coach'] if team_type == 'home' else self.away_team['coach']
        if unit_type == 'PP':
            units = ['PP1', 'PP2']
            shares = coach.get('pp_unit_shares', {'PP1': 0.60, 'PP2': 0.40})
        else:
            units = ['PK1', 'PK2']
            shares = coach.get('pk_unit_shares', {'PK1': 0.55, 'PK2': 0.45})
        probs = [shares.get(u, 0.0) for u in units]
        prob_sum = sum(probs)
        if prob_sum == 0: return random.choice(units)
        return random.choices(units, weights=probs, k=1)[0]
    
    def _resolve_faceoff(self):
        if self.home_skaters == self.away_skaters:
            self._change_lines('home', self._get_next_line('home', 'F'), self._get_next_line('home', 'D'))
            self._change_lines('away', self._get_next_line('away', 'F'), self._get_next_line('away', 'D'))
        else:
            home_unit_type, away_unit_type = ('PP', 'PK') if self.home_skaters > self.away_skaters else ('PK', 'PP')
            home_unit_name = self._get_next_st_unit('home', home_unit_type)
            away_unit_name = self._get_next_st_unit('away', away_unit_type)
            home_line_ids = self.home_lines.get(home_unit_name, [])
            away_line_ids = self.away_lines.get(away_unit_name, [])
            self.home_on_ice = {pid: self.home_players_dict[pid] for pid in home_line_ids if pid in self.home_players_dict}
            self.away_on_ice = {pid: self.away_players_dict[pid] for pid in away_line_ids if pid in self.away_players_dict}
            if not self.home_on_ice: self._change_lines('home', 'F1', 'D1')
            if not self.away_on_ice: self._change_lines('away', 'F1', 'D1')
        self.home_shift_time, self.away_shift_time = 0.0, 0.0
        if not self.home_on_ice or not self.away_on_ice:
            self.possession, self.puck_carrier_id = None, None; return
        home_centers = [p for p in self.home_on_ice.values() if p.position == 'C']
        away_centers = [p for p in self.away_on_ice.values() if p.position == 'C']
        home_c = home_centers[0] if home_centers else random.choice(list(self.home_on_ice.values()))
        away_c = away_centers[0] if away_centers else random.choice(list(self.away_on_ice.values()))
        prob_home_wins = 0.5 + ((self._get_player_rating(home_c.player_id, 'faceoff_rating') - self._get_player_rating(away_c.player_id, 'faceoff_rating')) / self.params['general_logic']['faceoff_rating_divisor'])
        home_state = self._get_game_state('home')
        away_state = self._get_game_state('away')
        self._increment_stat(self.home_player_stats, home_c.player_id, 'Faceoffs_Taken', 1, home_state)
        self._increment_stat(self.away_player_stats, away_c.player_id, 'Faceoffs_Taken', 1, away_state)
        if random.random() < prob_home_wins:
            self.possession = 'home'
            self._increment_stat(self.home_player_stats, home_c.player_id, 'Faceoffs_Won', 1, home_state)
        else:
            self.possession = 'away'
            self._increment_stat(self.away_player_stats, away_c.player_id, 'Faceoffs_Won', 1, away_state)
        self.puck_carrier_id = self._resolve_neutral_zone_puck_distribution(self.possession)
        self.zone, self.offensive_zone_state = 'neutral', None
    
    def _resolve_neutral_zone_puck_distribution(self, team_type):
        on_ice_players = self.home_on_ice if team_type == 'home' else self.away_on_ice
        if not on_ice_players:
            return None
        players_with_entry_rating = [p for p in on_ice_players.values() if hasattr(p, 'entry_volume')]
        if not players_with_entry_rating:
            return random.choice(list(on_ice_players.keys()))
        weights = [self._get_player_rating(p.player_id, 'entry_volume') for p in players_with_entry_rating]
        chosen_player = random.choices(players_with_entry_rating, weights=weights, k=1)[0]
        return chosen_player.player_id

    def _calculate_hazards(self):
        hazards = {}
        off_players = self.home_on_ice if self.possession == 'home' else self.away_on_ice
        def_on_ice_avg = self.away_on_ice_avg if self.possession == 'home' else self.home_on_ice_avg
        if not off_players or not self.puck_carrier_id or self.puck_carrier_id not in off_players:
            self._handle_turnover(); return {}
        carrier_id = self.puck_carrier_id
        hazards['line_change'] = BASE_HAZARD_RATES['line_change'] * (1 + (self.home_shift_time / self.params['general_logic']['shift_fatigue_seconds']))
        penalty_drawn_mod = self._convert_rating_to_modifier(self._get_player_rating(carrier_id, 'openalty_drawn'))
        penalty_taken_mod = self._convert_rating_to_modifier(def_on_ice_avg.get('min_penalty', 1000), is_defensive=True)
        hazards['minor_penalty'] = BASE_HAZARD_RATES['minor_penalty'] * penalty_drawn_mod * (1 / penalty_taken_mod)
        game_state_off = self._get_game_state(self.possession)
        if game_state_off == 'PP':
            if self.zone in ['offensive', 'pp_setup']:
                shot_mult, pass_mult, turnover_mult = self.params['pp_logic']['shot_multiplier'], self.params['pp_logic']['pass_multiplier'], self.params['pp_logic']['turnover_multiplier']
                pk_suppress_rating = np.mean([self._get_player_rating(p.player_id, 'd_hd_shot_suppression_rating') for p in (self.away_on_ice.values() if self.possession == 'home' else self.home_on_ice.values())])
                pk_suppress = self._convert_rating_to_modifier(pk_suppress_rating, is_defensive=True)
                pp_vol = self._convert_rating_to_modifier(self._get_player_rating(carrier_id, 'shooting_volume'))
                chance_creation_mod = self._convert_rating_to_modifier(self._get_player_rating(carrier_id, 'pp_chance_creation'))
                hazards['shot_high_danger'] = BASE_HAZARD_RATES['shot_high_danger'] * shot_mult * self._convert_rating_to_modifier(self._get_player_rating(carrier_id, 'o_hd_shot_creation_rating')) * pp_vol * pk_suppress * chance_creation_mod
                hazards['shot_medium_danger'] = BASE_HAZARD_RATES['shot_medium_danger'] * shot_mult * self._convert_rating_to_modifier(self._get_player_rating(carrier_id, 'o_md_shot_creation_rating')) * pp_vol * pk_suppress * chance_creation_mod
                hazards['shot_low_danger'] = BASE_HAZARD_RATES['shot_low_danger'] * shot_mult * self._convert_rating_to_modifier(self._get_player_rating(carrier_id, 'o_ld_shot_creation_rating')) * pp_vol * pk_suppress * chance_creation_mod
                pp_playmake = self._convert_rating_to_modifier(self._get_player_rating(carrier_id, 'oprime_playmaking'))
                hazards['pass_attempt'] = BASE_HAZARD_RATES['pass_attempt'] * pass_mult * pp_playmake
                hazards['turnover'] = BASE_HAZARD_RATES['turnover'] * turnover_mult / pp_playmake
            elif self.zone == 'neutral':
                hazards['pass_attempt_neutral_zone'] = self.params['pp_logic']['regroup_pass_hazard']
                hazards['zone_entry_attempt'] = self.params['pp_logic']['zone_entry_hazard'] * self._convert_rating_to_modifier(self._get_player_rating(carrier_id, 'ozone_entry'))
                hazards['turnover'] = BASE_HAZARD_RATES['turnover'] * self.params['pp_logic']['turnover_multiplier']
            else:
                hazards['pass_attempt'] = self.params['pp_logic']['regroup_pass_hazard']
                hazards['turnover'] = BASE_HAZARD_RATES['turnover'] * self.params['pp_logic']['regroup_turnover_multiplier']
        elif game_state_off == 'PK':
            if self.zone == 'defensive':
                pk_clear = self._convert_rating_to_modifier(self._get_player_rating(carrier_id, 'd_breakout_ability'))
                pp_pressure_rating = np.mean([self._get_player_rating(p.player_id, 'oprime_playmaking') for p in (self.away_on_ice.values() if self.possession == 'home' else self.home_on_ice.values())])
                pp_pressure = self._convert_rating_to_modifier(pp_pressure_rating, is_defensive=True)
                hazards['pk_clear_attempt'] = BASE_HAZARD_RATES['dump_out_exit'] * self.params['pk_logic']['clear_attempt_multiplier'] * pk_clear * pp_pressure
                hazards['turnover'] = BASE_HAZARD_RATES['turnover'] * self.params['pk_logic']['turnover_multiplier'] / pk_clear
            else:
                hazards['pk_clear_attempt'] = self.params['pk_logic']['neutral_zone_clear_hazard']
                hazards['turnover'] = BASE_HAZARD_RATES['turnover'] * self.params['pk_logic']['turnover_multiplier']
        else: # Even Strength
            if self.zone == 'defensive':
                hazards['controlled_exit'] = BASE_HAZARD_RATES['controlled_exit'] * self._convert_rating_to_modifier(self._get_player_rating(carrier_id, 'd_breakout_ability'))
                hazards['dump_out_exit'] = BASE_HAZARD_RATES['dump_out_exit']
                hazards['turnover'] = BASE_HAZARD_RATES['turnover'] / self._convert_rating_to_modifier(self._get_player_rating(carrier_id, 'opuck_possession')) / self._convert_rating_to_modifier(def_on_ice_avg.get('o_forechecking_pressure', 1000), is_defensive=True)
            elif self.zone == 'neutral':
                hazards['pass_attempt_neutral_zone'] = BASE_HAZARD_RATES['pass_attempt'] * self._convert_rating_to_modifier(self._get_player_rating(carrier_id, 'oprime_playmaking'))
                hazards['zone_entry_attempt'] = BASE_HAZARD_RATES['zone_entry_attempt'] * self._convert_rating_to_modifier(self._get_player_rating(carrier_id, 'entry_volume'))
                hazards['turnover'] = BASE_HAZARD_RATES['turnover'] / self._convert_rating_to_modifier(self._get_player_rating(carrier_id, 'opuck_possession'))
                hazards['dump_in'] = self.params['even_strength_logic']['dump_in_hazard'] * self._convert_rating_to_modifier(def_on_ice_avg.get('d_entry_denial', 1000))
            else: # Offensive Zone
                shot_vol_mod = self._convert_rating_to_modifier(self._get_player_rating(carrier_id, 'shooting_volume'))
                hd_mod = self._convert_rating_to_modifier(self._get_player_rating(carrier_id, 'o_hd_shot_creation_rating')) * self._convert_rating_to_modifier(def_on_ice_avg.get('d_hd_shot_suppression_rating', 1000), is_defensive=True)
                md_mod = self._convert_rating_to_modifier(self._get_player_rating(carrier_id, 'o_md_shot_creation_rating')) * self._convert_rating_to_modifier(def_on_ice_avg.get('d_md_shot_suppression_rating', 1000), is_defensive=True)
                ld_mod = self._convert_rating_to_modifier(self._get_player_rating(carrier_id, 'o_ld_shot_creation_rating')) * self._convert_rating_to_modifier(def_on_ice_avg.get('d_ld_shot_suppression_rating', 1000), is_defensive=True)
                hazards['shot_high_danger'] = BASE_HAZARD_RATES['shot_high_danger'] * hd_mod * shot_vol_mod
                hazards['shot_medium_danger'] = BASE_HAZARD_RATES['shot_medium_danger'] * md_mod * shot_vol_mod
                hazards['shot_low_danger'] = BASE_HAZARD_RATES['shot_low_danger'] * ld_mod * shot_vol_mod
                cycle_mod = self._convert_rating_to_modifier(self._get_player_rating(carrier_id, 'ocycle_play'))
                hazards['pass_attempt'] = BASE_HAZARD_RATES['pass_attempt'] * cycle_mod
                hazards['turnover'] = BASE_HAZARD_RATES['turnover'] / cycle_mod
        return hazards

    def _resolve_shot_attempt(self, danger_level):
        off_players = self.home_on_ice if self.possession == 'home' else self.away_on_ice
        def_players = self.away_on_ice if self.possession == 'home' else self.home_on_ice
        if not off_players or not self.puck_carrier_id or self.puck_carrier_id not in off_players:
            self.possession, self.puck_carrier_id = None, None; return
        shooter_id = self.puck_carrier_id
        possessing_team_state = self._get_game_state(self.possession)
        defending_team_state = self._get_game_state('away' if self.possession == 'home' else 'home')
        off_stats, def_stats = (self.home_player_stats, self.away_player_stats) if self.possession == 'home' else (self.away_player_stats, self.home_player_stats)
        def_goalie_stats, defending_goalie = (self.away_goalie_stats, self.away_goalie) if self.possession == 'home' else (self.home_goalie_stats, self.home_goalie)
        danger_prefix = {'high': 'HD', 'medium': 'MD', 'low': 'LD'}.get(danger_level)
        self._increment_stat(off_stats, shooter_id, f"i{danger_prefix}CF", 1, possessing_team_state)
        for p_id in def_players: self._increment_stat(def_stats, p_id, f"OnIce_{danger_prefix}CA", 1, defending_team_state)
        self._increment_stat(off_stats, shooter_id, 'Shot Attempts', 1, possessing_team_state)
        for p_id in off_players:
            self._increment_stat(off_stats, p_id, 'OnIce_CF', 1, possessing_team_state)
            self._increment_stat(off_stats, p_id, f"OnIce_{danger_prefix}CF", 1, possessing_team_state)
        avg_block_rating = np.mean([self._get_player_rating(p.player_id, 'd_shot_blocking') for p in def_players.values()])
        if random.random() < self.params['shot_resolution']['base_block_prob'] * self._convert_rating_to_modifier(avg_block_rating, is_defensive=True):
            blocker = random.choice(list(def_players.values()))
            self._increment_stat(def_stats, blocker.player_id, 'Blocks', 1, defending_team_state)
            self.possession = 'away' if self.possession == 'home' else 'home'
            self.puck_carrier_id = self._resolve_neutral_zone_puck_distribution(self.possession)
            return
        if random.random() < self.params['shot_resolution']['base_miss_prob'] / self._convert_rating_to_modifier(self._get_player_rating(shooter_id, 'shooting_accuracy')):
            self.possession = 'away' if self.possession == 'home' else 'home'
            self.puck_carrier_id = self._resolve_neutral_zone_puck_distribution(self.possession)
            return
        self._increment_stat(off_stats, shooter_id, 'Shots', 1, possessing_team_state)
        if self.time_in_offensive_zone > 10.0:
            self._increment_stat(off_stats, shooter_id, 'Shots_Off_Cycle', 1, possessing_team_state)
        other_on_ice = {pid: p for pid, p in off_players.items() if pid != shooter_id}
        sv_map = {'high': ('g_high_danger_sv_rating', 'lg_avg_hd_sv_pct'), 'medium': ('g_medium_danger_sv_rating', 'lg_avg_md_sv_pct'), 'low': ('g_low_danger_sv_rating', 'lg_avg_ld_sv_pct')}
        g_rating_name, lg_sv_name = sv_map[danger_level]
        goalie_sv_rating = defending_goalie.get(g_rating_name, 1000)
        league_avg_sv = self.params['goalie_logic'][lg_sv_name]
        goalie_z = (goalie_sv_rating - 1000) / self.params['ratings']['std_dev']
        goalie_true_sv = league_avg_sv + (goalie_z * self.params['goalie_logic']['sv_pct_swing_factor'])
        finishing_mod = self._convert_rating_to_modifier(self._get_player_rating(shooter_id, 'ofinishing'))
        final_sv_pct = np.clip(goalie_true_sv / finishing_mod, 0.0, 1.0)
        shot_xg = 1.0 - final_sv_pct
        self._increment_stat(off_stats, shooter_id, 'xG_for', shot_xg, possessing_team_state)
        def_goalie_stats['xG_against'] += shot_xg
        def_goalie_stats[f"{danger_prefix}_shots_against"] += 1
        def_goalie_stats[f"{danger_prefix}_xG_against"] += shot_xg
        if random.random() > final_sv_pct:
            self._increment_stat(off_stats, shooter_id, 'Goals', 1, possessing_team_state)
            def_goalie_stats['Goals_against'] += 1
            def_goalie_stats[f"{danger_prefix}_goals_against"] += 1
            if other_on_ice:
                other_players_list = list(other_on_ice.values())
                assist_weights = [self._get_player_rating(p.player_id, 'oprime_playmaking') for p in other_players_list]
                avg_playmaking_mod = self._convert_rating_to_modifier(np.mean(assist_weights))
                if random.random() < (self.params['shot_resolution']['primary_assist_prob'] * avg_playmaking_mod):
                    primary_assister = random.choices(other_players_list, weights=assist_weights, k=1)[0]
                    self._increment_stat(off_stats, primary_assister.player_id, 'Assists', 1, possessing_team_state)
                    if self.time_in_offensive_zone > 10.0:
                        self._increment_stat(off_stats, primary_assister.player_id, 'Assists_Off_Cycle', 1, possessing_team_state)
                    rem_players = [p for p in other_players_list if p.player_id != primary_assister.player_id]
                    if rem_players:
                        prob_a2 = self.params['shot_resolution']['secondary_assist_prob_pp'] if possessing_team_state == 'PP' else self.params['shot_resolution']['secondary_assist_prob_es']
                        if random.random() < prob_a2:
                            rem_weights = [self._get_player_rating(p.player_id, 'oprime_playmaking') for p in rem_players]
                            secondary_assister = random.choices(rem_players, weights=rem_weights, k=1)[0]
                            self._increment_stat(off_stats, secondary_assister.player_id, 'Assists', 1, possessing_team_state)
                            if self.time_in_offensive_zone > 10.0:
                                self._increment_stat(off_stats, secondary_assister.player_id, 'Assists_Off_Cycle', 1, possessing_team_state)
            if possessing_team_state == 'PP':
                if self.penalty_box: min(self.penalty_box, key=lambda p: p['time_remaining'])['time_remaining'] = 0.0
            else: # Even strength goal
                for p_id in self.home_on_ice: self._increment_stat(self.home_player_stats, p_id, '+/-', 1 if self.possession == 'home' else -1, 'ES')
                for p_id in self.away_on_ice: self._increment_stat(self.away_player_stats, p_id, '+/-', 1 if self.possession == 'away' else -1, 'ES')
            self.possession, self.puck_carrier_id = None, None; return
        else: # Save
            def_goalie_stats['Saves'] += 1
            if random.random() < 0.6 * self._convert_rating_to_modifier(defending_goalie.get('g_freeze_puck_rating', 1000)):
                def_goalie_stats['Freezes'] += 1
                self.possession, self.puck_carrier_id = None, None; return
            rebound_mod = self._convert_rating_to_modifier(self._get_player_rating(shooter_id, 'orebound_creation')) * self._convert_rating_to_modifier(defending_goalie.get('g_rebound_control_rating', 1000), is_defensive=True)
            if random.random() < self.params['shot_resolution']['base_rebound_prob'] * rebound_mod:
                self._increment_stat(off_stats, shooter_id, 'ReboundsCreated', 1, possessing_team_state)
                def_goalie_stats['ReboundsAllowed'] += 1
                if other_on_ice:
                    self.puck_carrier_id = random.choice(list(other_on_ice.keys()))
                else: 
                    self.possession, self.puck_carrier_id = self.possession, None
                    return
            else:
                self.possession, self.puck_carrier_id = self.possession, None
                return

    def _resolve_pass_attempt(self):
        off_players = self.home_on_ice if self.possession == 'home' else self.away_on_ice
        if not off_players or not self.puck_carrier_id or self.puck_carrier_id not in off_players:
            self.possession, self.puck_carrier_id = None, None; return
        passer_id = self.puck_carrier_id
        playmaking_mod = self._convert_rating_to_modifier(self._get_player_rating(passer_id, 'oprime_playmaking'))
        if random.random() < 0.95 * playmaking_mod:
            receivers = {pid: p for pid, p in off_players.items() if pid != passer_id}
            if receivers:
                receiver_list = list(receivers.values())
                weights = [(self._get_player_rating(p.player_id, 'shooting_volume') + self._get_player_rating(p.player_id, 'ocycle_play')) for p in receiver_list]
                self.puck_carrier_id = random.choices(receiver_list, weights=weights, k=1)[0].player_id
            else: 
                self.possession = 'away' if self.possession == 'home' else 'home'
                self.puck_carrier_id = self._resolve_neutral_zone_puck_distribution(self.possession)
                return
        else: 
            self.possession = 'away' if self.possession == 'home' else 'home'
            self.puck_carrier_id = self._resolve_neutral_zone_puck_distribution(self.possession)
            return

    def _resolve_pass_attempt_neutral_zone(self):
        off_players = self.home_on_ice if self.possession == 'home' else self.away_on_ice
        if not off_players or not self.puck_carrier_id or self.puck_carrier_id not in off_players:
            self.possession, self.puck_carrier_id = None, None; return
        passer_id = self.puck_carrier_id
        if random.random() < self._convert_rating_to_modifier(self._get_player_rating(passer_id, 'oprime_playmaking')):
            receivers = {pid: p for pid, p in off_players.items() if pid != passer_id}
            if receivers:
                receiver_list = list(receivers.values())
                weights = [self._get_player_rating(p.player_id, 'entry_volume') for p in receiver_list]
                self.puck_carrier_id = random.choices(receiver_list, weights=weights, k=1)[0].player_id
            else:
                self.possession = 'away' if self.possession == 'home' else 'home'
                self.puck_carrier_id = self._resolve_neutral_zone_puck_distribution(self.possession)
                return
        else:
            self.possession = 'away' if self.possession == 'home' else 'home'
            self.puck_carrier_id = self._resolve_neutral_zone_puck_distribution(self.possession)
            return

    def _resolve_zone_entry_attempt(self):
        off_team_type = self.possession
        def_team_type = 'away' if off_team_type == 'home' else 'home'
        off_players = self.home_on_ice if off_team_type == 'home' else self.away_on_ice
        def_players = self.away_on_ice if def_team_type == 'away' else self.home_on_ice
        off_stats = self.home_player_stats if off_team_type == 'home' else self.away_player_stats
        def_stats = self.away_player_stats if def_team_type == 'away' else self.home_player_stats
        off_game_state = self._get_game_state(off_team_type)
        def_game_state = self._get_game_state(def_team_type)
        puck_carrier_id = self.puck_carrier_id
        if not puck_carrier_id:
            self._handle_turnover(); return
        for p_id in def_players:
            self._increment_stat(def_stats, p_id, 'OnIce_EntryAttempts_Against', 1, def_game_state)
        base_success_prob = self.params['even_strength_logic']['base_entry_success_prob']
        entry_rating_name = 'ozone_entry' if off_game_state == 'PP' else 'entry_volume'
        off_mod = self._convert_rating_to_modifier(self._get_player_rating(puck_carrier_id, entry_rating_name))
        avg_denial_rating = np.mean([self._get_player_rating(p.player_id, 'd_entry_denial') for p in def_players.values()])
        def_rating_modifier = self._convert_rating_to_modifier(avg_denial_rating, is_defensive=False)
        final_success_prob = np.clip(base_success_prob * off_mod / def_rating_modifier, 0.1, 0.9)
        if random.random() < final_success_prob:
            self._increment_stat(off_stats, puck_carrier_id, 'ControlledEntries', 1, off_game_state)
            self.zone = 'offensive'
            self.time_in_offensive_zone = 0.0
            self.offensive_zone_state = 'pp_setup' if off_game_state == 'PP' else 'rush'
        else:
            self._increment_stat(off_stats, puck_carrier_id, 'FailedEntries', 1, off_game_state)
            denial_players_list = list(def_players.values())
            denial_weights = [self._convert_rating_to_modifier(self._get_player_rating(p.player_id, 'd_entry_denial')) for p in denial_players_list]
            if any(w > 0 for w in denial_weights):
                denier = random.choices(denial_players_list, weights=denial_weights, k=1)[0]
                self._increment_stat(def_stats, denier.player_id, 'EntryDenials', 1, def_game_state)
            self.possession = def_team_type
            self.zone = 'neutral'
            self.puck_carrier_id = self._resolve_neutral_zone_puck_distribution(self.possession)

    def _handle_turnover(self):
        if self.possession is None: return
        turnover_zone = self.zone
        losing_team_type = self.possession
        puck_carrier_id = self.puck_carrier_id
        gaining_team_players = self.away_on_ice if losing_team_type == 'home' else self.home_on_ice
        if puck_carrier_id:
            losing_stats = self.home_player_stats if losing_team_type == 'home' else self.away_player_stats
            game_state = self._get_game_state(losing_team_type)
            self._increment_stat(losing_stats, puck_carrier_id, 'Giveaways', 1, game_state)
        if gaining_team_players:
            gaining_stats = self.away_player_stats if losing_team_type == 'home' else self.home_player_stats
            takeaway_player_id = random.choice(list(gaining_team_players.keys()))
            game_state = self._get_game_state('away' if losing_team_type == 'home' else 'home')
            self._increment_stat(gaining_stats, takeaway_player_id, 'Takeaways', 1, game_state)
            if turnover_zone == 'offensive':
                self._increment_stat(gaining_stats, takeaway_player_id, 'ForecheckBreakups', 1, game_state)
        self.possession = 'away' if self.possession == 'home' else 'home'
        self.puck_carrier_id = self._resolve_neutral_zone_puck_distribution(self.possession)

    def _resolve_dump_in(self):
        self.possession = 'away' if self.possession == 'home' else 'home'
        self.zone = 'defensive'
        self.puck_carrier_id = None
        self.offensive_zone_state = None
        self.time_in_offensive_zone = 0.0

    def _resolve_dump_out_exit(self):
        self.possession = 'away' if self.possession == 'home' else 'home'
        self.zone = 'neutral'
        self.puck_carrier_id = None
        self.offensive_zone_state = None
        self.time_in_offensive_zone = 0.0
        
    def _resolve_penalty(self, penalty_type):
        carrier_id = self.puck_carrier_id
        draw_state = self._get_game_state(self.possession)
        off_stats = self.home_player_stats if self.possession == 'home' else self.away_player_stats
        def_team = 'away' if self.possession == 'home' else 'home'
        def_players = self.away_on_ice if def_team == 'away' else self.home_on_ice
        pk_stats = self.away_player_stats if def_team == 'away' else self.home_player_stats
        rating_col = 'min_penalty' if penalty_type == 'minor_penalty' else 'maj_penalty'
        def_players_list = list(def_players.values())
        weights = [(2000 - self._get_player_rating(p.player_id, rating_col)) for p in def_players_list]
        penalized_player = random.choices(def_players_list, weights=weights, k=1)[0]
        self.penalty_box.append({'player_id': penalized_player.player_id, 'team': def_team, 'time_remaining': (2 if penalty_type == 'minor_penalty' else 5) * 60})
        self._increment_stat(pk_stats, penalized_player.player_id, 'Penalty Minutes', 2, self._get_game_state(def_team))
        if penalty_type == 'minor_penalty':
            self._increment_stat(pk_stats, penalized_player.player_id, 'MinorPenaltiesTaken', 1, self._get_game_state(def_team))
        elif penalty_type == 'major_penalty':
            self._increment_stat(pk_stats, penalized_player.player_id, 'MajorPenaltiesTaken', 1, self._get_game_state(def_team))
        if carrier_id: self._increment_stat(off_stats, carrier_id, 'PenaltiesDrawn', 1, draw_state)
        if def_team == 'home': self.home_skaters -= 1
        else: self.away_skaters -= 1
        self.possession = 'home' if def_team == 'away' else 'away'
        self.zone, self.offensive_zone_state = 'neutral', None
        self._resolve_faceoff()

    def _update_penalty_clocks(self, time_elapsed):
        for p in self.penalty_box[:]:
            p['time_remaining'] -= time_elapsed
            if p['time_remaining'] <= 0:
                if p['team'] == 'home': self.home_skaters += 1
                else: self.away_skaters += 1
                self.penalty_box.remove(p)

    def run_simulation(self):
        self._resolve_faceoff()
        loop_counter = 0
        while self.game_clock_seconds > 0 and loop_counter < 30000:
            loop_counter += 1
            if not self.possession or not self.puck_carrier_id:
                self._resolve_faceoff()
                continue
            hazards = self._calculate_hazards()
            if not hazards or sum(hazards.values()) <= 0:
                self.possession, self.puck_carrier_id = None, None
                continue
            total_hazard = sum(hazards.values())
            if total_hazard == 0: continue
            time_to_event = np.random.exponential(1 / (total_hazard / 3600))
            h_state, a_state = self._get_game_state('home'), self._get_game_state('away')
            for p_id in self.home_on_ice: self._increment_stat(self.home_player_stats, p_id, 'TOI', time_to_event, h_state)
            for p_id in self.away_on_ice: self._increment_stat(self.away_player_stats, p_id, 'TOI', time_to_event, a_state)
            self._update_penalty_clocks(time_to_event)
            self.home_shift_time += time_to_event
            self.away_shift_time += time_to_event
            self.game_clock_seconds -= time_to_event
            if self.zone == 'offensive': self.time_in_offensive_zone += time_to_event
            chosen_event = random.choices(list(hazards.keys()), weights=list(hazards.values()), k=1)[0]
            off_stats = self.home_player_stats if self.possession == 'home' else self.away_player_stats
            game_state = self._get_game_state(self.possession)
            if chosen_event == 'controlled_exit':
                self._increment_stat(off_stats, self.puck_carrier_id, 'ControlledExits', 1, game_state)
                self.zone, self.offensive_zone_state, self.time_in_offensive_zone = 'neutral', None, 0.0
            elif chosen_event == 'dump_out_exit':
                self._resolve_dump_out_exit()
            elif chosen_event == 'pk_clear_attempt':
                if random.random() < self.params['pk_logic']['successful_clear_prob']:
                    self._increment_stat(off_stats, self.puck_carrier_id, 'PK_Clears', 1, game_state)
                    self.possession, self.puck_carrier_id = None, None
                    self._handle_turnover()
                else: self.possession, self.puck_carrier_id, self.zone = None, None, 'neutral'
                self.offensive_zone_state, self.time_in_offensive_zone = None, 0.0
            elif chosen_event == 'zone_entry_attempt':
                self._resolve_zone_entry_attempt()
            elif chosen_event.startswith('shot_'):
                self._resolve_shot_attempt(danger_level=chosen_event.split('_')[1])
            elif chosen_event == 'turnover': self._handle_turnover()
            elif chosen_event == 'pass_attempt': self._resolve_pass_attempt()
            elif chosen_event == 'pass_attempt_neutral_zone': self._resolve_pass_attempt_neutral_zone()
            elif chosen_event == 'dump_in':
                self._resolve_dump_in()
            elif 'penalty' in chosen_event: self._resolve_penalty(chosen_event)
            elif chosen_event == 'line_change': self._resolve_faceoff()
        home_flat_stats = [ {'player_id': pid, 'Player': data['Player'], **{f"{sn}_{st}": sv for st, s in data.items() if st != 'Player' for sn, sv in s.items()}} for pid, data in self.home_player_stats.items() ]
        away_flat_stats = [ {'player_id': pid, 'Player': data['Player'], **{f"{sn}_{st}": sv for st, s in data.items() if st != 'Player' for sn, sv in s.items()}} for pid, data in self.away_player_stats.items() ]
        return { 'home_players': pd.DataFrame(home_flat_stats), 'away_players': pd.DataFrame(away_flat_stats), 'home_goalie': pd.DataFrame([self.home_goalie_stats]), 'away_goalie': pd.DataFrame([self.away_goalie_stats]) }

def _run_simulation_chunk(args):
    """Helper function to run a chunk of simulations for parallel processing."""
    num_sims_chunk, home_team_data, away_team_data = args
    if DATAFRAME_SCHEMA is None:
        raise RuntimeError("DATAFRAME_SCHEMA is not loaded. Cannot run simulations.")
    
    sum_home_players = pd.DataFrame(columns=DATAFRAME_SCHEMA['home_players'])
    sum_away_players = pd.DataFrame(columns=DATAFRAME_SCHEMA['away_players'])
    sum_home_goalie = pd.DataFrame(columns=DATAFRAME_SCHEMA['home_goalie'])
    sum_away_goalie = pd.DataFrame(columns=DATAFRAME_SCHEMA['away_goalie'])
    
    sum_home_players[['player_id', 'Player']] = home_team_data['lineup'][['player_id', 'name']]
    sum_away_players[['player_id', 'Player']] = away_team_data['lineup'][['player_id', 'name']]
    sum_home_goalie['Player'] = [home_team_data['goalie']['full_name']]
    sum_away_goalie['Player'] = [away_team_data['goalie']['full_name']]

    for df in [sum_home_players, sum_away_players, sum_home_goalie, sum_away_goalie]:
        for col in df.select_dtypes(include=np.number).columns:
            df[col] = 0

    all_game_scores = []

    for _ in range(num_sims_chunk):
        sim = GameSimulator(home_team_data, away_team_data)
        results = sim.run_simulation()
        
        home_players_aligned = results['home_players'].set_index('player_id')
        away_players_aligned = results['away_players'].set_index('player_id')
        
        current_sum_home = sum_home_players.set_index('player_id')
        current_sum_away = sum_away_players.set_index('player_id')
        
        sum_home_players = current_sum_home.add(home_players_aligned, fill_value=0).reset_index()
        sum_away_players = current_sum_away.add(away_players_aligned, fill_value=0).reset_index()

        numeric_cols_goalie = sum_home_goalie.select_dtypes(include=np.number).columns
        sum_home_goalie[numeric_cols_goalie] += results['home_goalie'][numeric_cols_goalie].values
        sum_away_goalie[numeric_cols_goalie] += results['away_goalie'][numeric_cols_goalie].values

        home_goals = int(results['home_players']['Goals_Total'].sum())
        away_goals = int(results['away_players']['Goals_Total'].sum())
        all_game_scores.append((home_goals, away_goals))
        
    return sum_home_players, sum_away_players, sum_home_goalie, sum_away_goalie, all_game_scores

def run_multiple_simulations(num_sims, home_team_data, away_team_data):
    if DATAFRAME_SCHEMA is None:
        raise RuntimeError("DATAFRAME_SCHEMA is not loaded. Cannot run simulations.")
    
    num_processes = 4
    chunk_size = num_sims // num_processes
    chunks = [chunk_size] * num_processes
    remainder = num_sims % num_processes
    for i in range(remainder):
        chunks[i] += 1
        
    pool = multiprocessing.Pool(processes=num_processes)
    tasks = [(chunk, home_team_data, away_team_data) for chunk in chunks if chunk > 0]
    
    print(f"Running {num_sims} simulations in parallel across {num_processes} cores...")
    results = pool.map(_run_simulation_chunk, tasks)
    pool.close()
    pool.join()
    print("All simulation chunks completed. Aggregating results...")
    
    player_info_home = results[0][0][['player_id', 'Player']]
    player_info_away = results[0][1][['player_id', 'Player']]

    numeric_home_players = [res[0].select_dtypes(include=np.number) for res in results]
    numeric_away_players = [res[1].select_dtypes(include=np.number) for res in results]
    numeric_home_goalie = [res[2].select_dtypes(include=np.number) for res in results]
    numeric_away_goalie = [res[3].select_dtypes(include=np.number) for res in results]

    total_home_players_numeric = sum(numeric_home_players)
    total_away_players_numeric = sum(numeric_away_players)
    total_home_goalie_numeric = sum(numeric_home_goalie)
    total_away_goalie_numeric = sum(numeric_away_goalie)

    total_home_players = pd.concat([player_info_home, total_home_players_numeric.drop(columns=['player_id'], errors='ignore')], axis=1)
    total_away_players = pd.concat([player_info_away, total_away_players_numeric.drop(columns=['player_id'], errors='ignore')], axis=1)
    total_home_goalie = total_home_goalie_numeric
    total_away_goalie = total_away_goalie_numeric
    
    all_game_scores = []
    for _, _, _, _, scores in results:
        all_game_scores.extend(scores)

    numeric_cols_home = total_home_players.select_dtypes(include=np.number).columns.drop('player_id', errors='ignore')
    numeric_cols_away = total_away_players.select_dtypes(include=np.number).columns.drop('player_id', errors='ignore')
    numeric_cols_goalie = total_home_goalie.select_dtypes(include=np.number).columns
    
    avg_home_players = total_home_players.copy()
    if num_sims > 0:
        avg_home_players[numeric_cols_home] /= num_sims
    
    avg_away_players = total_away_players.copy()
    if num_sims > 0:
        avg_away_players[numeric_cols_away] /= num_sims
    
    avg_home_goalie = total_home_goalie.copy()
    if num_sims > 0:
        avg_home_goalie[numeric_cols_goalie] /= num_sims
    
    avg_away_goalie = total_away_goalie.copy()
    if num_sims > 0:
        avg_away_goalie[numeric_cols_goalie] /= num_sims

    avg_home_players = _finalize_player_stats(avg_home_players)
    avg_away_players = _finalize_player_stats(avg_away_players)

    output_cols = ['Goals_Total', 'Assists_Total', 'Shots_Total', 'Shot Attempts_Total', 'Blocks_Total', 'Penalty Minutes_Total']
    avg_home_total = pd.DataFrame(avg_home_players[output_cols].sum()).T
    avg_away_total = pd.DataFrame(avg_away_players[output_cols].sum()).T
    avg_home_total.columns = [c.replace('_Total', '') for c in avg_home_total.columns]
    avg_away_total.columns = [c.replace('_Total', '') for c in avg_away_total.columns]
    
    return {
        'home_total': avg_home_total.round(2),
        'home_players': avg_home_players.round(2),
        'away_total': avg_away_total.round(2),
        'away_players': avg_away_players.round(2),
        'home_goalie_validation': avg_home_goalie.round(2),
        'away_goalie_validation': avg_away_goalie.round(2),
        'all_game_scores': all_game_scores
    }

def _finalize_player_stats(df):
    """
    Optimized function to calculate all final and per-60 stats.
    """
    if df.empty:
        return df

    new_columns = {}
    new_columns['OnIce_CF_PP'] = df.get('OnIce_HDCF_PP', 0) + df.get('OnIce_MDCF_PP', 0) + df.get('OnIce_LDCF_PP', 0)

    def calculate_per_60(source_df, stats, toi_col_suffix):
        per_60_cols = {}
        toi_col = f'TOI_{toi_col_suffix}'
        if toi_col in source_df.columns:
            for stat in stats:
                stat_col = f'{stat}_{toi_col_suffix}'
                if stat_col in source_df.columns:
                    new_col_name = f'Sim_{stat}_per_60_{toi_col_suffix}'
                    mask = source_df[toi_col] > 0
                    per_60_cols[new_col_name] = np.where(mask, (source_df[stat_col] / source_df[toi_col]) * 3600, 0)
        return per_60_cols

    es_stats = ['iHDCF', 'iMDCF', 'iLDCF', 'OnIce_HDCA', 'OnIce_MDCA', 'OnIce_LDCA', 'xG_for', 'ReboundsCreated', 'PenaltiesDrawn', 'ControlledEntries', 'ControlledExits', 'Giveaways', 'Takeaways', 'Faceoffs_Won', 'Faceoffs_Taken', 'Shots_Off_Cycle', 'Assists_Off_Cycle', 'ForecheckBreakups', 'OnIce_EntryAttempts_Against', 'OnIce_ControlledEntries_Against', 'Blocks', 'MinorPenaltiesTaken', 'MajorPenaltiesTaken', 'Assists', 'EntryDenials', 'FailedEntries']
    pp_stats = ['iHDCF', 'iMDCF', 'iLDCF', 'xG_for', 'ReboundsCreated', 'PenaltiesDrawn', 'ControlledEntries', 'OnIce_CF']
    pk_stats = ['OnIce_HDCA', 'OnIce_MDCA', 'OnIce_LDCA', 'PK_Clears', 'Blocks']

    new_columns.update(calculate_per_60(df, es_stats, 'ES'))
    new_columns.update(calculate_per_60(df, pp_stats, 'PP'))
    new_columns.update(calculate_per_60(df, pk_stats, 'PK'))

    new_columns['Sim_ShotAccuracy_Pct'] = np.where(df.get('Shot Attempts_Total', 0) > 0, (df.get('Shots_Total', 0) / df.get('Shot Attempts_Total', 0)) * 100, 0)
    new_columns['Sim_Shooting_Pct'] = np.where(df.get('Shots_Total', 0) > 0, (df.get('Goals_Total', 0) / df.get('Shots_Total', 0)) * 100, 0)
    new_columns['Sim_Faceoff_Pct'] = np.where(df.get('Faceoffs_Taken_Total', 0) > 0, (df.get('Faceoffs_Won_Total', 0) / df.get('Faceoffs_Taken_Total', 0)) * 100, 0)
    new_columns['Sim_GoalsAboveExpected_Total'] = df.get('Goals_Total', 0) - df.get('xG_for_Total', 0)
    new_columns['Sim_GoalsAboveExpected_PP'] = df.get('Goals_PP', 0) - df.get('xG_for_PP', 0)

    return df.assign(**new_columns).fillna(0)