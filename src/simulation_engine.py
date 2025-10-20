# src/simulation_engine.py (Updated to use shared constants and new shot logic)
import numpy as np
import pandas as pd
import random
import multiprocessing
import dataclasses
import json

# --- Import Shared Components ---
# We now import the harmonized PlayerProfile and all constants.
from src.shared_simulation_constants import (
    PlayerProfile,
    BASE_HAZARD_RATES,
    SIMULATION_PARAMETERS
)

class GameSimulator:
    def __init__(self, home_team_data, away_team_data):
        self.home_team = home_team_data
        self.away_team = away_team_data
        # Get the set of valid field names directly from the PlayerProfile dataclass
        profile_fields = {f.name for f in dataclasses.fields(PlayerProfile)}

        def create_player_dict(team_df):
            player_dict = {}
            for _, player_row in team_df.iterrows():
                player_data = player_row.to_dict()
                
                # Ensure st_roles is always a list
                if not isinstance(player_data.get('st_roles'), (list, tuple)):
                    player_data['st_roles'] = []

                # Filter the player_data dictionary to only include keys that
                # are actual fields in the PlayerProfile dataclass. This is robust.
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
        self.home_goalie = home_team_data.get('goalie', {})
        self.away_goalie = away_team_data.get('goalie', {})
        self._initialize_lines()
        self.game_log = []
        self._initialize_stat_trackers()

    def _initialize_lines(self):
        # This function now works correctly without workarounds because 'line' and 'st_roles'
        # are part of the imported PlayerProfile.
        self.home_lines = { 'F1': [p.player_id for p in self.home_players_dict.values() if p.line == 'F1'], 'F2': [p.player_id for p in self.home_players_dict.values() if p.line == 'F2'], 'F3': [p.player_id for p in self.home_players_dict.values() if p.line == 'F3'], 'F4': [p.player_id for p in self.home_players_dict.values() if p.line == 'F4'], 'D1': [p.player_id for p in self.home_players_dict.values() if p.line == 'D1'], 'D2': [p.player_id for p in self.home_players_dict.values() if p.line == 'D2'], 'D3': [p.player_id for p in self.home_players_dict.values() if p.line == 'D3'], 'PP1': [p.player_id for p in self.home_players_dict.values() if 'PP1' in p.st_roles], 'PP2': [p.player_id for p in self.home_players_dict.values() if 'PP2' in p.st_roles], 'PK1': [p.player_id for p in self.home_players_dict.values() if 'PK1' in p.st_roles], 'PK2': [p.player_id for p in self.home_players_dict.values() if 'PK2' in p.st_roles], }
        self.away_lines = { 'F1': [p.player_id for p in self.away_players_dict.values() if p.line == 'F1'], 'F2': [p.player_id for p in self.away_players_dict.values() if p.line == 'F2'], 'F3': [p.player_id for p in self.away_players_dict.values() if p.line == 'F3'], 'F4': [p.player_id for p in self.away_players_dict.values() if p.line == 'F4'], 'D1': [p.player_id for p in self.away_players_dict.values() if p.line == 'D1'], 'D2': [p.player_id for p in self.away_players_dict.values() if p.line == 'D2'], 'D3': [p.player_id for p in self.away_players_dict.values() if p.line == 'D3'], 'PP1': [p.player_id for p in self.away_players_dict.values() if 'PP1' in p.st_roles], 'PP2': [p.player_id for p in self.away_players_dict.values() if 'PP2' in p.st_roles], 'PK1': [p.player_id for p in self.away_players_dict.values() if 'PK1' in p.st_roles], 'PK2': [p.player_id for p in self.away_players_dict.values() if 'PK2' in p.st_roles], }
        self._change_lines('home', 'F1', 'D1')
        self._change_lines('away', 'F1', 'D1')

    def _initialize_stat_trackers(self):
        stat_template = lambda: { 'TOI': 0.0, 'Goals': 0, 'Assists': 0, 'Shots': 0, 'Shot Attempts': 0, 'Blocks': 0, '+/-': 0, 'Penalty Minutes': 0, 'iHDCF': 0, 'iMDCF': 0, 'iLDCF': 0, 'OnIce_CF': 0, 'OnIce_HDCF': 0, 'OnIce_MDCF': 0, 'OnIce_LDCF': 0, 'OnIce_HDCA': 0, 'OnIce_MDCA': 0, 'OnIce_LDCA': 0, 'xG_for': 0.0, 'ReboundsCreated': 0, 'PenaltiesDrawn': 0, 'ControlledEntries': 0, 'ControlledExits': 0, 'OnIce_EntryAttempts_Against': 0, 'OnIce_ControlledEntries_Against': 0, 'ForecheckBreakups': 0, 'PK_Clears': 0, 'xG_against': 0.0, 'Goals_against': 0, 'HD_shots_against': 0, 'HD_goals_against': 0, 'HD_xG_against': 0.0, 'MD_shots_against': 0, 'MD_goals_against': 0, 'MD_xG_against': 0.0, 'LD_shots_against': 0, 'LD_goals_against': 0, 'LD_xG_against': 0.0, 'Saves': 0, 'ReboundsAllowed': 0, 'Freezes': 0, 'Giveaways': 0, 'Takeaways': 0, 'Shots_Off_Cycle': 0, 'Assists_Off_Cycle': 0, 'Faceoffs_Won': 0, 'Faceoffs_Taken': 0, 'MinorPenaltiesTaken': 0, 'MajorPenaltiesTaken': 0, 'EntryDenials': 0, 'FailedEntries': 0 }
        # Updated p.name to p.full_name to match the unified dataclass
        self.home_player_stats = { p.player_id: { 'Player': p.full_name, 'Total': stat_template(), 'ES': stat_template(), 'PP': stat_template(), 'PK': stat_template() } for p in self.home_players_dict.values() }
        self.away_player_stats = { p.player_id: { 'Player': p.full_name, 'Total': stat_template(), 'ES': stat_template(), 'PP': stat_template(), 'PK': stat_template() } for p in self.away_players_dict.values() }
        self.home_goalie_stats = stat_template()
        self.home_goalie_stats['Player'] = self.home_goalie.get('full_name', 'Unknown Goalie')
        self.home_goalie_stats['player_id'] = self.home_goalie.get('player_id', 999999)

        self.away_goalie_stats = stat_template()
        self.away_goalie_stats['Player'] = self.away_goalie.get('full_name', 'Unknown Goalie')
        self.away_goalie_stats['player_id'] = self.away_goalie.get('player_id', 999998)

    # --- NO OTHER CHANGES ARE NEEDED BELOW THIS LINE ---
    # The rest of the file remains identical to your working version.

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
        """
        UPDATED: Calculates a single 'shot_attempt' hazard instead of three separate ones.
        The danger level is now determined in _resolve_shot_attempt.
        """
        hazards = {}
        off_players = self.home_on_ice if self.possession == 'home' else self.away_on_ice
        def_players = self.away_on_ice if self.possession == 'home' else self.home_on_ice
        
        if not off_players or not self.puck_carrier_id or self.puck_carrier_id not in off_players:
            self._handle_turnover(); return {}
        carrier_id = self.puck_carrier_id
        
        hazards['line_change'] = BASE_HAZARD_RATES.get('line_change', 50.0) * (1 + (self.home_shift_time / self.params['general_logic'].get('shift_fatigue_seconds', 45.0)))

        game_state_off = self._get_game_state(self.possession)
        if game_state_off == 'PP':
            if self.zone in ['offensive', 'pp_setup']:
                shot_mult, pass_mult, turnover_mult = self.params['pp_logic']['shot_multiplier'], self.params['pp_logic']['pass_multiplier'], self.params['pp_logic']['turnover_multiplier']
                pk_suppress_rating = np.mean([self._get_player_rating(p.player_id, 'd_hd_shot_suppression_rating') for p in def_players.values()]) if def_players else 1000
                pk_suppress = self._convert_rating_to_modifier(pk_suppress_rating, is_defensive=True)
                
                hazards['shot_attempt'] = BASE_HAZARD_RATES.get('shot_attempt', 1000) * shot_mult * self._convert_rating_to_modifier(self._get_player_rating(carrier_id, 'shooting_volume')) * pk_suppress
                
                pp_playmake = self._convert_rating_to_modifier(self._get_player_rating(carrier_id, 'oprime_playmaking'))
                hazards['pass_attempt'] = BASE_HAZARD_RATES['pass_attempt'] * pass_mult * pp_playmake
                hazards['turnover'] = BASE_HAZARD_RATES['turnover'] * turnover_mult / pp_playmake
            elif self.zone == 'neutral':
                hazards['pass_attempt_neutral_zone'] = self.params['pp_logic'].get('regroup_pass_hazard', 700)
                hazards['zone_entry_attempt'] = self.params['pp_logic'].get('zone_entry_hazard', 500) * self._convert_rating_to_modifier(self._get_player_rating(carrier_id, 'ozone_entry'))
                hazards['turnover'] = BASE_HAZARD_RATES['turnover'] * self.params['pp_logic']['turnover_multiplier']
            else:
                hazards['pass_attempt'] = self.params['pp_logic'].get('regroup_pass_hazard', 700)
                hazards['turnover'] = BASE_HAZARD_RATES['turnover'] * self.params['pp_logic'].get('regroup_turnover_multiplier', 0.5)
        elif game_state_off == 'PK':
            if self.zone == 'defensive':
                pk_clear = self._convert_rating_to_modifier(self._get_player_rating(carrier_id, 'd_breakout_ability'))
                pp_pressure_rating = np.mean([self._get_player_rating(p.player_id, 'oprime_playmaking') for p in def_players.values()]) if def_players else 1000
                pp_pressure = self._convert_rating_to_modifier(pp_pressure_rating, is_defensive=True)
                hazards['pk_clear_attempt'] = BASE_HAZARD_RATES['dump_out_exit'] * self.params['pk_logic']['clear_attempt_multiplier'] * pk_clear * pp_pressure
                hazards['turnover'] = BASE_HAZARD_RATES['turnover'] * self.params['pk_logic']['turnover_multiplier'] / pk_clear
            else:
                hazards['pk_clear_attempt'] = self.params['pk_logic'].get('neutral_zone_clear_hazard', 600)
                hazards['turnover'] = BASE_HAZARD_RATES['turnover'] * self.params['pk_logic']['turnover_multiplier']
        else: # Even Strength
            def_on_ice_avg = self.away_on_ice_avg if self.possession == 'home' else self.home_on_ice_avg
            penalty_drawn_mod = self._convert_rating_to_modifier(self._get_player_rating(carrier_id, 'openalty_drawn'))
            penalty_taken_mod = self._convert_rating_to_modifier(def_on_ice_avg.get('min_penalty', 1000), is_defensive=True)
            hazards['minor_penalty'] = BASE_HAZARD_RATES['minor_penalty'] * penalty_drawn_mod * (1 / penalty_taken_mod)

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
                
                avg_def_suppress = np.mean([self._get_player_rating(p.player_id, 'd_hd_shot_suppression_rating') for p in def_players.values()]) if def_players else 1000
                def_suppress_mod = self._convert_rating_to_modifier(avg_def_suppress, is_defensive=True)

                hazards['shot_attempt'] = BASE_HAZARD_RATES.get('shot_attempt', 1000) * shot_vol_mod * def_suppress_mod

                cycle_mod = self._convert_rating_to_modifier(self._get_player_rating(carrier_id, 'ocycle_play'))
                hazards['pass_attempt'] = BASE_HAZARD_RATES['pass_attempt'] * cycle_mod
                hazards['turnover'] = BASE_HAZARD_RATES['turnover'] / cycle_mod
        return hazards

    def _resolve_shot_attempt(self):
        """
        NEW: Implements the full "Shooting Event Decision Tree".
        This single function now handles the entire sequence from attempt to rebound.
        """
        # --- Step 0: Identify Participants ---
        off_team = self.possession
        def_team = 'away' if off_team == 'home' else 'home'
        shooter_id = self.puck_carrier_id
        
        off_players = self.home_on_ice if off_team == 'home' else self.away_on_ice
        def_players = self.away_on_ice if def_team == 'away' else self.home_on_ice
        
        off_stats = self.home_player_stats if off_team == 'home' else self.away_player_stats
        def_stats = self.away_player_stats if def_team == 'away' else self.home_player_stats
        
        defending_goalie_stats = self.away_goalie_stats if off_team == 'home' else self.home_goalie_stats
        defending_goalie = self.away_goalie if off_team == 'home' else self.home_goalie
        
        off_gamestate = self._get_game_state(off_team)
        def_gamestate = self._get_game_state(def_team)

        if not shooter_id or shooter_id not in off_players:
            self._handle_turnover(); return

        # --- Step 1: Shot is Attempted ---
        self._increment_stat(off_stats, shooter_id, 'Shot Attempts', 1, off_gamestate)
        for p_id in off_players:
            self._increment_stat(off_stats, p_id, 'OnIce_CF', 1, off_gamestate)

        # --- Step 2: The Block Check ---
        avg_block_rating = np.mean([self._get_player_rating(p.player_id, 'd_shot_blocking') for p in def_players.values()]) if def_players else 1000
        block_mod = self._convert_rating_to_modifier(avg_block_rating) # Higher rating = higher block chance
        if random.random() < self.params['shot_resolution']['base_block_prob'] * block_mod:
            if def_players:
                blocker = random.choice(list(def_players.values()))
                self._increment_stat(def_stats, blocker.player_id, 'Blocks', 1, def_gamestate)
            self.possession = def_team
            self.puck_carrier_id = self._resolve_neutral_zone_puck_distribution(self.possession)
            return

        # --- Step 3: The Accuracy Check (Miss) ---
        accuracy_mod = self._convert_rating_to_modifier(self._get_player_rating(shooter_id, 'shooting_accuracy'))
        # Higher accuracy modifier REDUCES miss probability
        if random.random() < self.params['shot_resolution']['base_miss_prob'] / accuracy_mod:
            self.possession = def_team
            self.puck_carrier_id = self._resolve_neutral_zone_puck_distribution(self.possession)
            return

        # --- If not blocked or missed, it's a Shot on Goal ---
        self._increment_stat(off_stats, shooter_id, 'Shots', 1, off_gamestate)
        
        # --- Step 4: Danger Level Assignment ---
        danger_weights = [
            self._get_player_rating(shooter_id, 'o_hd_shot_creation_rating'),
            self._get_player_rating(shooter_id, 'o_md_shot_creation_rating'),
            self._get_player_rating(shooter_id, 'o_ld_shot_creation_rating')
        ]
        danger_levels = ['high', 'medium', 'low']
        danger_level = random.choices(danger_levels, weights=danger_weights, k=1)[0]
        
        danger_prefix = {'high': 'HD', 'medium': 'MD', 'low': 'LD'}.get(danger_level)
        self._increment_stat(off_stats, shooter_id, f"i{danger_prefix}CF", 1, off_gamestate)
        for p_id in def_players: self._increment_stat(def_stats, p_id, f"OnIce_{danger_prefix}CA", 1, def_gamestate)
        for p_id in off_players: self._increment_stat(off_stats, p_id, f"OnIce_{danger_prefix}CF", 1, off_gamestate)

        # --- Step 5: The Save Check (Goal vs. Save) ---
        sv_map = {'high': 'g_high_danger_sv_rating', 'medium': 'g_medium_danger_sv_rating', 'low': 'g_low_danger_sv_rating'}
        lg_sv_map = {'high': 'lg_avg_hd_sv_pct', 'medium': 'lg_avg_md_sv_pct', 'low': 'lg_avg_ld_sv_pct'}
        
        goalie_sv_rating = defending_goalie.get(sv_map[danger_level], 1000)
        league_avg_sv = self.params['goalie_logic'][lg_sv_map[danger_level]]
        
        goalie_z = (goalie_sv_rating - 1000) / self.params['ratings']['std_dev']
        goalie_true_sv = league_avg_sv + (goalie_z * self.params['goalie_logic']['sv_pct_swing_factor'])
        
        finishing_mod = self._convert_rating_to_modifier(self._get_player_rating(shooter_id, 'ofinishing'))
        final_sv_pct = np.clip(goalie_true_sv / finishing_mod, 0.0, 1.0)
        
        shot_xg = 1.0 - final_sv_pct
        self._increment_stat(off_stats, shooter_id, 'xG_for', shot_xg, off_gamestate)
        defending_goalie_stats['xG_against'] += shot_xg
        defending_goalie_stats[f"{danger_prefix}_shots_against"] += 1
        defending_goalie_stats[f"{danger_prefix}_xG_against"] += shot_xg

        if random.random() > final_sv_pct: # GOAL
            self._increment_stat(off_stats, shooter_id, 'Goals', 1, off_gamestate)
            defending_goalie_stats['Goals_against'] += 1
            defending_goalie_stats[f"{danger_prefix}_goals_against"] += 1
            
            other_on_ice = {pid: p for pid, p in off_players.items() if pid != shooter_id}
            if other_on_ice:
                other_players_list = list(other_on_ice.values())
                assist_weights = [self._get_player_rating(p.player_id, 'oprime_playmaking') for p in other_players_list]
                avg_playmaking_mod = self._convert_rating_to_modifier(np.mean(assist_weights)) if other_players_list else 1.0
                if random.random() < (self.params['shot_resolution']['primary_assist_prob'] * avg_playmaking_mod):
                    primary_assister = random.choices(other_players_list, weights=assist_weights, k=1)[0]
                    self._increment_stat(off_stats, primary_assister.player_id, 'Assists', 1, off_gamestate)
                    
                    rem_players = [p for p in other_players_list if p.player_id != primary_assister.player_id]
                    if rem_players:
                        prob_a2 = self.params['shot_resolution']['secondary_assist_prob_pp'] if off_gamestate == 'PP' else self.params['shot_resolution']['secondary_assist_prob_es']
                        if random.random() < prob_a2:
                            rem_weights = [self._get_player_rating(p.player_id, 'oprime_playmaking') for p in rem_players]
                            secondary_assister = random.choices(rem_players, weights=rem_weights, k=1)[0]
                            self._increment_stat(off_stats, secondary_assister.player_id, 'Assists', 1, off_gamestate)
            
            if off_gamestate == 'PP':
                if self.penalty_box: min(self.penalty_box, key=lambda p: p['time_remaining'])['time_remaining'] = 0.0
            else: # Even strength goal
                for p_id in self.home_on_ice: self._increment_stat(self.home_player_stats, p_id, '+/-', 1 if off_team == 'home' else -1, 'ES')
                for p_id in self.away_on_ice: self._increment_stat(self.away_player_stats, p_id, '+/-', 1 if off_team == 'away' else -1, 'ES')
            
            self.possession, self.puck_carrier_id = None, None # Reset for faceoff
            return

        # --- Step 6: The Rebound Check ---
        else: # SAVE
            defending_goalie_stats['Saves'] += 1
            rebound_mod = self._convert_rating_to_modifier(self._get_player_rating(shooter_id, 'orebound_creation'))
            rebound_control_mod = self._convert_rating_to_modifier(defending_goalie.get('g_rebound_control_rating', 1000), is_defensive=True)
            
            if random.random() < self.params['shot_resolution']['base_rebound_prob'] * rebound_mod * rebound_control_mod: # REBOUND
                self._increment_stat(off_stats, shooter_id, 'ReboundsCreated', 1, off_gamestate)
                defending_goalie_stats['ReboundsAllowed'] += 1
                # Puck stays in zone with offensive team, new carrier
                other_off_players = [p_id for p_id in off_players if p_id != shooter_id]
                if other_off_players:
                    self.puck_carrier_id = random.choice(other_off_players)
                else: # Only shooter was there, he gets his own rebound
                    self.puck_carrier_id = shooter_id
                return
            else: # Goalie controls, check for freeze vs. play on
                if random.random() < self.params['goalie_logic'].get('base_freeze_prob', 0.6) * self._convert_rating_to_modifier(defending_goalie.get('g_freeze_puck_rating', 1000)):
                    defending_goalie_stats['Freezes'] += 1
                    self.possession, self.puck_carrier_id = None, None # Faceoff
                else: # Goalie plays puck to defenseman
                    def_d_men = [p.player_id for p in def_players.values() if p.position == 'D']
                    if def_d_men:
                        self.puck_carrier_id = random.choice(def_d_men)
                        self.possession = def_team
                        self.zone = 'defensive'
                    else: # No d-men, freeze for faceoff
                        defending_goalie_stats['Freezes'] += 1
                        self.possession, self.puck_carrier_id = None, None
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
                if sum(weights) > 0:
                    self.puck_carrier_id = random.choices(receiver_list, weights=weights, k=1)[0].player_id
                else:
                    self.puck_carrier_id = random.choice(receiver_list).player_id
            else:
                self._handle_turnover()
        else:
            self._handle_turnover()

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
                if sum(weights) > 0:
                    self.puck_carrier_id = random.choices(receiver_list, weights=weights, k=1)[0].player_id
                else:
                    self.puck_carrier_id = random.choice(receiver_list).player_id
            else:
                self._handle_turnover()
        else:
            self._handle_turnover()

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
        avg_denial_rating = np.mean([self._get_player_rating(p.player_id, 'd_entry_denial') for p in def_players.values()]) if def_players else 1000
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
        if self.possession is None: self.possession = 'home' # Failsafe
        losing_team_type = self.possession
        gaining_team_type = 'away' if losing_team_type == 'home' else 'home'
        puck_carrier_id = self.puck_carrier_id
        gaining_team_players = self.away_on_ice if losing_team_type == 'home' else self.home_on_ice
        if puck_carrier_id:
            losing_stats = self.home_player_stats if losing_team_type == 'home' else self.away_player_stats
            game_state = self._get_game_state(losing_team_type)
            self._increment_stat(losing_stats, puck_carrier_id, 'Giveaways', 1, game_state)
        if gaining_team_players:
            gaining_stats = self.away_player_stats if losing_team_type == 'home' else self.home_player_stats
            takeaway_player_id = random.choice(list(gaining_team_players.keys()))
            game_state = self._get_game_state(gaining_team_type)
            self._increment_stat(gaining_stats, takeaway_player_id, 'Takeaways', 1, game_state)
            if self.zone == 'offensive': # This means the gaining team was on defense
                self._increment_stat(gaining_stats, takeaway_player_id, 'ForecheckBreakups', 1, game_state)
        self.possession = gaining_team_type
        self.zone = 'neutral'
        self.offensive_zone_state = None
        self.time_in_offensive_zone = 0.0
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
        if not def_players: return
        pk_stats = self.away_player_stats if def_team == 'away' else self.home_player_stats
        rating_col = 'min_penalty' if penalty_type == 'minor_penalty' else 'maj_penalty'
        def_players_list = list(def_players.values())
        weights = [(2000 - self._get_player_rating(p.player_id, rating_col)) for p in def_players_list]
        if sum(weights) <= 0: return # Avoid error if all weights are zero
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
            
            if chosen_event == 'shot_attempt':
                self._resolve_shot_attempt()
            elif chosen_event == 'controlled_exit':
                self._increment_stat(off_stats, self.puck_carrier_id, 'ControlledExits', 1, game_state)
                self.zone, self.offensive_zone_state, self.time_in_offensive_zone = 'neutral', None, 0.0
            elif chosen_event == 'dump_out_exit':
                self._resolve_dump_out_exit()
            elif chosen_event == 'pk_clear_attempt':
                if random.random() < self.params['pk_logic']['successful_clear_prob']:
                    self._increment_stat(off_stats, self.puck_carrier_id, 'PK_Clears', 1, game_state)
                    self._handle_turnover()
                else: 
                    self.possession, self.puck_carrier_id = None, None
            elif chosen_event == 'zone_entry_attempt':
                self._resolve_zone_entry_attempt()
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

def run_multiple_simulations(num_sims, home_team_data, away_team_data):
    """
    Runs multiple simulations and aggregates the results efficiently.
    """
    print(f"Running {num_sims} simulations in a single process...")
    all_results = []
    for i in range(num_sims):
        if (i + 1) % 100 == 0:
            print(f" 	...completed {i + 1}/{num_sims} simulations")
        sim = GameSimulator(home_team_data, away_team_data)
        results = sim.run_simulation()
        all_results.append(results)

    print("All simulations completed. Aggregating results...")

    full_home_df = pd.concat([res['home_players'] for res in all_results])
    full_away_df = pd.concat([res['away_players'] for res in all_results])
    full_home_goalie_df = pd.concat([res['home_goalie'] for res in all_results])
    full_away_goalie_df = pd.concat([res['away_goalie'] for res in all_results])
    all_game_scores = [
        (
            int(res['home_players']['Goals_Total'].sum()),
            int(res['away_players']['Goals_Total'].sum())
        ) for res in all_results
    ]

    total_home_players = full_home_df.groupby(['player_id', 'Player']).sum()
    total_away_players = full_away_df.groupby(['player_id', 'Player']).sum()
    total_home_goalie = full_home_goalie_df.groupby(['player_id', 'Player']).sum()
    total_away_goalie = full_away_goalie_df.groupby(['player_id', 'Player']).sum()

    avg_home_players = (total_home_players / num_sims).reset_index()
    avg_away_players = (total_away_players / num_sims).reset_index()
    avg_home_goalie = (total_home_goalie / num_sims).reset_index()
    avg_away_goalie = (total_away_goalie / num_sims).reset_index()

    avg_home_players = _finalize_player_stats(avg_home_players)
    avg_away_players = _finalize_player_stats(avg_away_players)

    output_cols = ['Goals_Total', 'Assists_Total', 'Shots_Total', 'Shot Attempts_Total', 'Blocks_Total', 'Penalty Minutes_Total']
    
    existing_home_cols = [col for col in output_cols if col in avg_home_players.columns]
    existing_away_cols = [col for col in output_cols if col in avg_away_players.columns]

    avg_home_total = pd.DataFrame(avg_home_players[existing_home_cols].sum()).T
    avg_away_total = pd.DataFrame(avg_away_players[existing_away_cols].sum()).T
    
    avg_home_total.columns = [c.replace('_Total', '') for c in avg_home_total.columns]
    avg_away_total.columns = [c.replace('_Total', '') for c in avg_away_total.columns]
    
    return {
        'home_total': avg_home_total.round(2).fillna(0),
        'home_players': avg_home_players.round(2).fillna(0),
        'away_total': avg_away_total.round(2).fillna(0),
        'away_players': avg_away_players.round(2).fillna(0),
        'home_goalie_validation': avg_home_goalie.round(2).fillna(0),
        'away_goalie_validation': avg_away_goalie.round(2).fillna(0),
        'all_game_scores': all_game_scores
    }

def _finalize_player_stats(df):
    """
    Optimized function to calculate all final and per-60 stats with robust division-by-zero protection.
    """
    if df.empty:
        return df

    df = df.copy()

    df['OnIce_CF_PP'] = df.get('OnIce_HDCF_PP', 0) + df.get('OnIce_MDCF_PP', 0) + df.get('OnIce_LDCF_PP', 0)

    def calculate_per_60(source_df, stats, toi_col_suffix):
        toi_col = f'TOI_{toi_col_suffix}'
        if toi_col in source_df.columns:
            mask = source_df[toi_col] > 0
            for stat in stats:
                stat_col = f'{stat}_{toi_col_suffix}'
                if stat_col in source_df.columns:
                    new_col_name = f'Sim_{stat}_per_60_{toi_col_suffix}'
                    source_df[new_col_name] = np.where(mask, (source_df[stat_col] / source_df[toi_col]) * 3600, 0.0)

    es_stats = ['iHDCF', 'iMDCF', 'iLDCF', 'OnIce_HDCA', 'OnIce_MDCA', 'OnIce_LDCA', 'xG_for', 'ReboundsCreated', 'PenaltiesDrawn', 'ControlledEntries', 'ControlledExits', 'Giveaways', 'Takeaways', 'Faceoffs_Won', 'Faceoffs_Taken', 'Shots_Off_Cycle', 'Assists_Off_Cycle', 'ForecheckBreakups', 'OnIce_EntryAttempts_Against', 'OnIce_ControlledEntries_Against', 'Blocks', 'MinorPenaltiesTaken', 'MajorPenaltiesTaken', 'Assists', 'EntryDenials', 'FailedEntries']
    pp_stats = ['iHDCF', 'iMDCF', 'iLDCF', 'xG_for', 'ReboundsCreated', 'PenaltiesDrawn', 'ControlledEntries', 'OnIce_CF']
    pk_stats = ['OnIce_HDCA', 'OnIce_MDCA', 'OnIce_LDCA', 'PK_Clears', 'Blocks']

    calculate_per_60(df, es_stats, 'ES')
    calculate_per_60(df, pp_stats, 'PP')
    calculate_per_60(df, pk_stats, 'PK')
    
    shot_attempts_mask = df.get('Shot Attempts_Total', 0) > 0
    df['Sim_ShotAccuracy_Pct'] = np.where(shot_attempts_mask, (df.get('Shots_Total', 0) / df.get('Shot Attempts_Total', 1)) * 100, 0.0)
    
    shots_mask = df.get('Shots_Total', 0) > 0
    df['Sim_Shooting_Pct'] = np.where(shots_mask, (df.get('Goals_Total', 0) / df.get('Shots_Total', 1)) * 100, 0.0)

    faceoffs_mask = df.get('Faceoffs_Taken_Total', 0) > 0
    df['Sim_Faceoff_Pct'] = np.where(faceoffs_mask, (df.get('Faceoffs_Won_Total', 0) / df.get('Faceoffs_Taken_Total', 1)) * 100, 0.0)

    df['Sim_GoalsAboveExpected_Total'] = df.get('Goals_Total', 0) - df.get('xG_for_Total', 0)
    df['Sim_GoalsAboveExpected_PP'] = df.get('Goals_PP', 0) - df.get('xG_for_PP', 0)

    return df.fillna(0)

