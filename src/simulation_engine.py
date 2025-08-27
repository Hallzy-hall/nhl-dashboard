import numpy as np
import pandas as pd
import random
from dataclasses import dataclass
from src.simulation_constants import BASE_HAZARD_RATES, SIMULATION_PARAMETERS

@dataclass
class PlayerProfile:
    # This dataclass holds all ratings for a single player for fast access.
    # It uses default values of 1000 for any ratings that might be missing from the input data.
    player_id: int
    name: str
    position: str
    line: str
    st_roles: list
    toi_individual_rating: int = 1000
    shooting_volume: int = 1000
    shooting_accuracy: int = 1000
    hdshot_creation: int = 1000
    mshot_creation: int = 1000
    ofinishing: int = 1000
    orebound_creation: int = 1000
    oprime_playmaking: int = 1000
    osecond_playmaking: int = 1000
    faceoff_rating: int = 1000
    ozone_entry: int = 1000
    opuck_possession: int = 1000
    ocycle_play: int = 1000
    openalty_drawn: int = 1000
    d_breakout_ability: int = 1000
    d_entry_denial: int = 1000
    o_forechecking_pressure: int = 1000
    d_cycle_defense: int = 1000
    d_shot_blocking: int = 1000
    min_penalty: int = 1000
    maj_penalty: int = 1000
    o_hd_shot_creation_rating: int = 1000
    o_md_shot_creation_rating: int = 1000
    o_ld_shot_creation_rating: int = 1000
    d_hd_shot_suppression_rating: int = 1000
    d_md_shot_suppression_rating: int = 1000
    d_ld_shot_suppression_rating: int = 1000
    pp_shot_volume: int = 1000
    pp_shot_on_net: int = 1000
    pp_chance_creation: int = 1000
    pp_playmaking: int = 1000
    pp_zone_entry: int = 1000
    pp_finishing: int = 1000
    pp_rebound_creation: int = 1000
    pk_shot_suppression: int = 1000
    pk_clearing_ability: int = 1000
    pk_shot_blocking: int = 1000

class GameSimulator:
    def __init__(self, home_team_data, away_team_data):
        self.home_team = home_team_data
        self.away_team = away_team_data

        # --- FIX: Rely solely on **p unpacking to avoid duplicate arguments ---
        self.home_players_dict = {p['player_id']: PlayerProfile(**p) for _, p in home_team_data['lineup'].iterrows()}
        self.away_players_dict = {p['player_id']: PlayerProfile(**p) for _, p in away_team_data['lineup'].iterrows()}
        
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
        self.home_lines = {
            'F1': [p.player_id for p in self.home_players_dict.values() if p.line == 'F1'],
            'F2': [p.player_id for p in self.home_players_dict.values() if p.line == 'F2'],
            'F3': [p.player_id for p in self.home_players_dict.values() if p.line == 'F3'],
            'F4': [p.player_id for p in self.home_players_dict.values() if p.line == 'F4'],
            'D1': [p.player_id for p in self.home_players_dict.values() if p.line == 'D1'],
            'D2': [p.player_id for p in self.home_players_dict.values() if p.line == 'D2'],
            'D3': [p.player_id for p in self.home_players_dict.values() if p.line == 'D3'],
            'PP1': [p.player_id for p in self.home_players_dict.values() if 'PP1' in p.st_roles],
            'PP2': [p.player_id for p in self.home_players_dict.values() if 'PP2' in p.st_roles],
            'PK1': [p.player_id for p in self.home_players_dict.values() if 'PK1' in p.st_roles],
            'PK2': [p.player_id for p in self.home_players_dict.values() if 'PK2' in p.st_roles],
        }
        self.away_lines = {
            'F1': [p.player_id for p in self.away_players_dict.values() if p.line == 'F1'],
            'F2': [p.player_id for p in self.away_players_dict.values() if p.line == 'F2'],
            'F3': [p.player_id for p in self.away_players_dict.values() if p.line == 'F3'],
            'F4': [p.player_id for p in self.away_players_dict.values() if p.line == 'F4'],
            'D1': [p.player_id for p in self.away_players_dict.values() if p.line == 'D1'],
            'D2': [p.player_id for p in self.away_players_dict.values() if p.line == 'D2'],
            'D3': [p.player_id for p in self.away_players_dict.values() if p.line == 'D3'],
            'PP1': [p.player_id for p in self.away_players_dict.values() if 'PP1' in p.st_roles],
            'PP2': [p.player_id for p in self.away_players_dict.values() if 'PP2' in p.st_roles],
            'PK1': [p.player_id for p in self.away_players_dict.values() if 'PK1' in p.st_roles],
            'PK2': [p.player_id for p in self.away_players_dict.values() if 'PK2' in p.st_roles],
        }
        self._change_lines('home', 'F1', 'D1')
        self._change_lines('away', 'F1', 'D1')

    def _initialize_stat_trackers(self):
        stat_template = lambda: {
            'TOI': 0.0, 'Goals': 0, 'Assists': 0, 'Shots': 0, 'Shot Attempts': 0,
            'Blocks': 0, '+/-': 0, 'Penalty Minutes': 0, 'iHDCF': 0, 'iMDCF': 0,
            'iLDCF': 0, 'OnIce_CF': 0, 'OnIce_HDCA': 0, 'OnIce_MDCA': 0, 'OnIce_LDCA': 0,
            'xG_for': 0.0, 'ReboundsCreated': 0, 'PenaltiesDrawn': 0, 'ControlledEntries': 0,
            'ControlledExits': 0, 'OnIce_EntryAttempts_Against': 0,
            'OnIce_ControlledEntries_Against': 0, 'ForecheckBreakups': 0, 'PK_Clears': 0,
            'xG_against': 0.0, 'Goals_against': 0, 'HD_shots_against': 0, 'HD_goals_against': 0,
            'HD_xG_against': 0.0, 'MD_shots_against': 0, 'MD_goals_against': 0,
            'MD_xG_against': 0.0, 'LD_shots_against': 0, 'LD_goals_against': 0,
            'LD_xG_against': 0.0, 'Saves': 0, 'ReboundsAllowed': 0, 'Freezes': 0
        }
        
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

    def _increment_stat(self, player_stats, player_id, stat, value, game_state):
        if player_id in player_stats:
            player_stats[player_id][game_state][stat] += value
            player_stats[player_id]['Total'][stat] += value

    def _convert_rating_to_modifier(self, rating, is_defensive=False):
        std_dev = self.params['ratings']['std_dev']
        impact_factor = self.params['ratings']['impact_factor']
        z_score = (rating - 1000) / std_dev
        modifier = 1 + (z_score * impact_factor)
        if is_defensive:
            modifier = 1 - (z_score * impact_factor)
        return max(0.1, modifier)

    def _change_lines(self, team_type, f_line_name, d_pair_name):
        if team_type == 'home':
            line_ids = self.home_lines.get(f_line_name, []) + self.home_lines.get(d_pair_name, [])
            self.home_on_ice = {pid: self.home_players_dict[pid] for pid in line_ids if pid in self.home_players_dict}
            self.home_shift_time = 0.0
            if self.home_on_ice:
                ratings_df = pd.DataFrame([p.__dict__ for p in self.home_on_ice.values()])
                # FIX: Add numeric_only=True to the mean() calculation
                self.home_on_ice_avg = ratings_df.mean(numeric_only=True).to_dict()
        else:
            line_ids = self.away_lines.get(f_line_name, []) + self.away_lines.get(d_pair_name, [])
            self.away_on_ice = {pid: self.away_players_dict[pid] for pid in line_ids if pid in self.away_players_dict}
            self.away_shift_time = 0.0
            if self.away_on_ice:
                ratings_df = pd.DataFrame([p.__dict__ for p in self.away_on_ice.values()])
                # FIX: Add numeric_only=True to the mean() calculation
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

        prob_home_wins = 0.5 + ((home_c.faceoff_rating - away_c.faceoff_rating) / self.params['general_logic']['faceoff_rating_divisor'])
        
        if random.random() < prob_home_wins:
            self.possession, self.puck_carrier_id = 'home', home_c.player_id
        else:
            self.possession, self.puck_carrier_id = 'away', away_c.player_id
        
        self.zone, self.offensive_zone_state = 'neutral', None

    def _calculate_hazards(self):
        hazards = {}
        off_players = self.home_on_ice if self.possession == 'home' else self.away_on_ice
        def_on_ice_avg = self.away_on_ice_avg if self.possession == 'home' else self.home_on_ice_avg
        
        if not off_players or not self.puck_carrier_id or self.puck_carrier_id not in off_players:
            self._handle_turnover(); return {}

        carrier = off_players[self.puck_carrier_id]
        hazards['line_change'] = BASE_HAZARD_RATES['line_change'] * (1 + (self.home_shift_time / self.params['general_logic']['shift_fatigue_seconds']))
        hazards['minor_penalty'] = BASE_HAZARD_RATES['minor_penalty'] * self._convert_rating_to_modifier(carrier.openalty_drawn) * (1 / self._convert_rating_to_modifier(def_on_ice_avg['min_penalty'], is_defensive=True))

        is_pp = (self.possession == 'home' and self.home_skaters > self.away_skaters) or (self.possession == 'away' and self.away_skaters > self.home_skaters)
        is_pk = (self.possession == 'home' and self.home_skaters < self.away_skaters) or (self.possession == 'away' and self.away_skaters < self.home_skaters)
        
        if is_pp:
            if self.zone in ['offensive', 'pp_setup']:
                shot_mult, pass_mult, turnover_mult = self.params['pp_logic']['shot_multiplier'], self.params['pp_logic']['pass_multiplier'], self.params['pp_logic']['turnover_multiplier']
                pk_suppress = self._convert_rating_to_modifier(def_on_ice_avg['pk_shot_suppression'], is_defensive=True)
                pp_vol = self._convert_rating_to_modifier(carrier.pp_shot_volume)
                
                hazards['shot_high_danger'] = BASE_HAZARD_RATES['shot_high_danger'] * shot_mult * self._convert_rating_to_modifier(carrier.o_hd_shot_creation_rating) * pp_vol * pk_suppress
                hazards['shot_medium_danger'] = BASE_HAZARD_RATES['shot_medium_danger'] * shot_mult * self._convert_rating_to_modifier(carrier.o_md_shot_creation_rating) * pp_vol * pk_suppress
                hazards['shot_low_danger'] = BASE_HAZARD_RATES['shot_low_danger'] * shot_mult * self._convert_rating_to_modifier(carrier.o_ld_shot_creation_rating) * pp_vol * pk_suppress

                pp_playmake = self._convert_rating_to_modifier(carrier.pp_playmaking)
                hazards['pass_attempt'] = BASE_HAZARD_RATES['pass_attempt'] * pass_mult * pp_playmake
                hazards['turnover'] = BASE_HAZARD_RATES['turnover'] * turnover_mult / pp_playmake
            elif self.zone == 'neutral':
                hazards['zone_entry_attempt'] = self.params['pp_logic']['zone_entry_hazard']
                hazards['turnover'] = BASE_HAZARD_RATES['turnover'] * self.params['pp_logic']['turnover_multiplier']
            else:
                hazards['pass_attempt'] = self.params['pp_logic']['regroup_pass_hazard']
                hazards['turnover'] = BASE_HAZARD_RATES['turnover'] * self.params['pp_logic']['regroup_turnover_multiplier']
        elif is_pk:
            if self.zone == 'defensive':
                pk_clear = self._convert_rating_to_modifier(carrier.pk_clearing_ability)
                pp_pressure = self._convert_rating_to_modifier(def_on_ice_avg['pp_playmaking'], is_defensive=True)
                hazards['pk_clear_attempt'] = BASE_HAZARD_RATES['dump_out_exit'] * self.params['pk_logic']['clear_attempt_multiplier'] * pk_clear * pp_pressure
                hazards['turnover'] = BASE_HAZARD_RATES['turnover'] * self.params['pk_logic']['turnover_multiplier'] / pk_clear
            else:
                hazards['pk_clear_attempt'] = self.params['pk_logic']['neutral_zone_clear_hazard']
                hazards['turnover'] = BASE_HAZARD_RATES['turnover'] * self.params['pk_logic']['turnover_multiplier']
        else:
            if self.zone == 'defensive':
                hazards['controlled_exit'] = BASE_HAZARD_RATES['controlled_exit'] * self._convert_rating_to_modifier(carrier.d_breakout_ability)
                hazards['dump_out_exit'] = BASE_HAZARD_RATES['dump_out_exit']
                hazards['turnover'] = BASE_HAZARD_RATES['turnover'] / self._convert_rating_to_modifier(carrier.opuck_possession) / self._convert_rating_to_modifier(def_on_ice_avg['o_forechecking_pressure'], is_defensive=True)
            elif self.zone == 'neutral':
                hazards['zone_entry_attempt'] = self.params['even_strength_logic']['zone_entry_hazard'] * self._convert_rating_to_modifier(carrier.ozone_entry) * self._convert_rating_to_modifier(def_on_ice_avg['d_entry_denial'], is_defensive=True)
                hazards['turnover'] = BASE_HAZARD_RATES['turnover'] / self._convert_rating_to_modifier(carrier.opuck_possession)
            else:
                hd_mod = self._convert_rating_to_modifier(carrier.o_hd_shot_creation_rating) * self._convert_rating_to_modifier(def_on_ice_avg['d_hd_shot_suppression_rating'], is_defensive=True)
                md_mod = self._convert_rating_to_modifier(carrier.o_md_shot_creation_rating) * self._convert_rating_to_modifier(def_on_ice_avg['d_md_shot_suppression_rating'], is_defensive=True)
                ld_mod = self._convert_rating_to_modifier(carrier.o_ld_shot_creation_rating) * self._convert_rating_to_modifier(def_on_ice_avg['d_ld_shot_suppression_rating'], is_defensive=True)
                hazards['shot_high_danger'] = BASE_HAZARD_RATES['shot_high_danger'] * hd_mod
                hazards['shot_medium_danger'] = BASE_HAZARD_RATES['shot_medium_danger'] * md_mod
                hazards['shot_low_danger'] = BASE_HAZARD_RATES['shot_low_danger'] * ld_mod
                
                cycle_mod = self._convert_rating_to_modifier(carrier.ocycle_play)
                hazards['pass_attempt'] = BASE_HAZARD_RATES['pass_attempt'] * cycle_mod
                hazards['turnover'] = BASE_HAZARD_RATES['turnover'] / cycle_mod
        return hazards

    def _resolve_shot_attempt(self, danger_level):
        off_players = self.home_on_ice if self.possession == 'home' else self.away_on_ice
        def_players = self.away_on_ice if self.possession == 'home' else self.home_on_ice
        def_on_ice_avg = self.away_on_ice_avg if self.possession == 'home' else self.home_on_ice_avg
        
        if not off_players or not self.puck_carrier_id or self.puck_carrier_id not in off_players:
            self._handle_turnover(); return

        shooter = off_players[self.puck_carrier_id]
        shooter_id = shooter.player_id

        possessing_team_state = self._get_game_state(self.possession)
        defending_team_state = self._get_game_state('away' if self.possession == 'home' else 'home')
        
        off_stats, def_stats = (self.home_player_stats, self.away_player_stats) if self.possession == 'home' else (self.away_player_stats, self.home_player_stats)
        def_goalie_stats, defending_goalie = (self.away_goalie_stats, self.away_goalie) if self.possession == 'home' else (self.home_goalie_stats, self.home_goalie)

        danger_prefix = {'high': 'HD', 'medium': 'MD', 'low': 'LD'}.get(danger_level)
        self._increment_stat(off_stats, shooter_id, f"i{danger_prefix}CF", 1, possessing_team_state)
        for p_id in def_players: self._increment_stat(def_stats, p_id, f"OnIce_{danger_prefix}CA", 1, defending_team_state)
        self._increment_stat(off_stats, shooter_id, 'Shot Attempts', 1, possessing_team_state)

        is_pp = possessing_team_state == 'PP'
        block_rating_name = 'pk_shot_blocking' if is_pp else 'd_shot_blocking'
        if random.random() < self.params['shot_resolution']['base_block_prob'] * self._convert_rating_to_modifier(def_on_ice_avg[block_rating_name], is_defensive=True):
            blocker = random.choice(list(def_players.values()))
            self._increment_stat(def_stats, blocker.player_id, 'Blocks', 1, defending_team_state)
            self.possession, self.puck_carrier_id = None, None; return

        accuracy_rating_name = 'pp_shot_on_net' if is_pp else 'shooting_accuracy'
        if random.random() < self.params['shot_resolution']['base_miss_prob'] / self._convert_rating_to_modifier(getattr(shooter, accuracy_rating_name)):
            self._handle_turnover(); return

        self._increment_stat(off_stats, shooter_id, 'Shots', 1, possessing_team_state)
        other_on_ice = {pid: p for pid, p in off_players.items() if pid != shooter_id}
        
        sv_map = {'high': ('g_high_danger_sv_rating', 'lg_avg_hd_sv_pct'), 'medium': ('g_medium_danger_sv_rating', 'lg_avg_md_sv_pct'), 'low': ('g_low_danger_sv_rating', 'lg_avg_ld_sv_pct')}
        g_rating_name, lg_sv_name = sv_map[danger_level]
        goalie_sv_rating = defending_goalie[g_rating_name]
        league_avg_sv = self.params['goalie_logic'][lg_sv_name]
        
        goalie_z = (goalie_sv_rating - 1000) / self.params['ratings']['std_dev']
        goalie_true_sv = league_avg_sv + (goalie_z * self.params['goalie_logic']['sv_pct_swing_factor'])
        finishing_rating_name = 'pp_finishing' if is_pp else 'ofinishing'
        finishing_mod = self._convert_rating_to_modifier(getattr(shooter, finishing_rating_name))
        final_sv_pct = np.clip(goalie_true_sv / finishing_mod, 0.0, 1.0)
        shot_xg = 1.0 - final_sv_pct

        self._increment_stat(off_stats, shooter_id, 'xG_for', shot_xg, possessing_team_state)
        def_goalie_stats['xG_against'] += shot_xg
        def_goalie_stats[f"{danger_prefix}_shots_against"] += 1
        def_goalie_stats[f"{danger_prefix}_xG_against"] += shot_xg

        if random.random() > final_sv_pct:
            # GOAL
            self._increment_stat(off_stats, shooter_id, 'Goals', 1, possessing_team_state)
            def_goalie_stats['Goals_against'] += 1
            def_goalie_stats[f"{danger_prefix}_goals_against"] += 1
            
            if other_on_ice:
                playmaking_rating_name = 'pp_playmaking' if is_pp else 'oprime_playmaking'
                other_players_list = list(other_on_ice.values())
                assist_weights = [getattr(p, playmaking_rating_name) for p in other_players_list]
                avg_playmaking_mod = self._convert_rating_to_modifier(np.mean(assist_weights))
                
                if random.random() < (self.params['shot_resolution']['primary_assist_prob'] * avg_playmaking_mod):
                    primary_assister = random.choices(other_players_list, weights=assist_weights, k=1)[0]
                    self._increment_stat(off_stats, primary_assister.player_id, 'Assists', 1, possessing_team_state)
                    
                    rem_players = [p for p in other_players_list if p.player_id != primary_assister.player_id]
                    if rem_players:
                        prob_a2 = self.params['shot_resolution']['secondary_assist_prob_pp'] if is_pp else self.params['shot_resolution']['secondary_assist_prob_es']
                        if random.random() < prob_a2:
                            rem_weights = [getattr(p, playmaking_rating_name) for p in rem_players]
                            secondary_assister = random.choices(rem_players, weights=rem_weights, k=1)[0]
                            self._increment_stat(off_stats, secondary_assister.player_id, 'Assists', 1, possessing_team_state)

            if is_pp:
                if self.penalty_box: min(self.penalty_box, key=lambda p: p['time_remaining'])['time_remaining'] = 0.0
            else:
                for p_id in self.home_on_ice: self._increment_stat(self.home_player_stats, p_id, '+/-', 1 if self.possession == 'home' else -1, 'ES')
                for p_id in self.away_on_ice: self._increment_stat(self.away_player_stats, p_id, '+/-', 1 if self.possession == 'away' else -1, 'ES')
            
            self.possession, self.puck_carrier_id = None, None; return
        else:
            # SAVE
            def_goalie_stats['Saves'] += 1
            if random.random() < 0.6 * self._convert_rating_to_modifier(defending_goalie['g_freeze_puck_rating']):
                def_goalie_stats['Freezes'] += 1
                self.possession, self.puck_carrier_id = None, None; return
            
            rebound_rating_name = 'pp_rebound_creation' if is_pp else 'orebound_creation'
            rebound_mod = self._convert_rating_to_modifier(getattr(shooter, rebound_rating_name)) * self._convert_rating_to_modifier(defending_goalie['g_rebound_control_rating'], is_defensive=True)
            if random.random() < self.params['shot_resolution']['base_rebound_prob'] * rebound_mod:
                self._increment_stat(off_stats, shooter_id, 'ReboundsCreated', 1, possessing_team_state)
                def_goalie_stats['ReboundsAllowed'] += 1
                if other_on_ice:
                    self.puck_carrier_id = random.choice(list(other_on_ice.keys()))
                else: self._handle_turnover()
            else:
                self.possession, self.puck_carrier_id = None, None

    def _resolve_pass_attempt(self):
        off_players = self.home_on_ice if self.possession == 'home' else self.away_on_ice
        if not off_players or not self.puck_carrier_id or self.puck_carrier_id not in off_players:
            self._handle_turnover(); return

        passer = off_players[self.puck_carrier_id]
        playmaking = 'pp_playmaking' if self._get_game_state(self.possession) == 'PP' else 'oprime_playmaking'
        if random.random() < 0.95 * self._convert_rating_to_modifier(getattr(passer, playmaking)):
            receivers = {pid: p for pid, p in off_players.items() if pid != self.puck_carrier_id}
            if receivers:
                receiver_list = list(receivers.values())
                weights = [(p.shooting_volume + p.ocycle_play) for p in receiver_list]
                self.puck_carrier_id = random.choices(receiver_list, weights=weights, k=1)[0].player_id
            else: self._handle_turnover()
        else: self._handle_turnover()

    def _handle_turnover(self):
        if self.possession is None: return
        self.possession = 'away' if self.possession == 'home' else 'home'
        new_off = self.away_on_ice if self.possession == 'away' else self.home_on_ice
        if new_off:
            self.puck_carrier_id = random.choice(list(new_off.keys()))
        else:
            self.puck_carrier_id, self.possession = None, None

    def _resolve_penalty(self, penalty_type):
        carrier_id = self.puck_carrier_id
        draw_state = self._get_game_state(self.possession)
        off_stats = self.home_player_stats if self.possession == 'home' else self.away_player_stats

        def_team = 'away' if self.possession == 'home' else 'home'
        def_players = self.away_on_ice if def_team == 'away' else self.home_on_ice
        pk_stats = self.away_player_stats if def_team == 'away' else self.home_player_stats
        
        rating_col = 'min_penalty' if penalty_type == 'minor_penalty' else 'maj_penalty'
        
        def_players_list = list(def_players.values())
        weights = [(2000 - getattr(p, rating_col)) for p in def_players_list]
        penalized_player = random.choices(def_players_list, weights=weights, k=1)[0]
        
        self.penalty_box.append({'player_id': penalized_player.player_id, 'team': def_team, 'time_remaining': (2 if penalty_type == 'minor_penalty' else 5) * 60})
        self._increment_stat(pk_stats, penalized_player.player_id, 'Penalty Minutes', 2, self._get_game_state(def_team))
        
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
                self.possession, self.puck_carrier_id, self.zone, self.offensive_zone_state, self.time_in_offensive_zone = None, None, 'neutral', None, 0.0
            elif chosen_event == 'pk_clear_attempt':
                if random.random() < self.params['pk_logic']['successful_clear_prob']:
                    self._increment_stat(off_stats, self.puck_carrier_id, 'PK_Clears', 1, game_state)
                    self._handle_turnover(); self.zone = 'defensive'
                else: self.possession, self.puck_carrier_id, self.zone = None, None, 'neutral'
                self.offensive_zone_state, self.time_in_offensive_zone = None, 0.0
            elif chosen_event == 'zone_entry_attempt':
                self._increment_stat(off_stats, self.puck_carrier_id, 'ControlledEntries', 1, game_state)
                self.zone, self.time_in_offensive_zone = 'offensive', 0.0
                self.offensive_zone_state = 'pp_setup' if game_state == 'PP' else 'rush'
            elif chosen_event.startswith('shot_'):
                self._resolve_shot_attempt(danger_level=chosen_event.split('_')[1])
            elif chosen_event == 'turnover': self._handle_turnover()
            elif chosen_event == 'pass_attempt': self._resolve_pass_attempt()
            elif 'penalty' in chosen_event: self._resolve_penalty(chosen_event)
            elif chosen_event == 'line_change': self._resolve_faceoff()
        
        home_flat_stats = [ {'player_id': pid, 'Player': data['Player'], **{f"{sn}_{st}": sv for st, s in data.items() if st != 'Player' for sn, sv in s.items()}} for pid, data in self.home_player_stats.items() ]
        away_flat_stats = [ {'player_id': pid, 'Player': data['Player'], **{f"{sn}_{st}": sv for st, s in data.items() if st != 'Player' for sn, sv in s.items()}} for pid, data in self.away_player_stats.items() ]
        
        return {
            'home_players': pd.DataFrame(home_flat_stats), 'away_players': pd.DataFrame(away_flat_stats),
            'home_goalie': pd.DataFrame([self.home_goalie_stats]), 'away_goalie': pd.DataFrame([self.away_goalie_stats])
        }

# This function is defined OUTSIDE the GameSimulator class
def run_multiple_simulations(num_sims, home_team_data, away_team_data):
    all_home_players, all_away_players = [], []
    all_home_goalies, all_away_goalies = [], []
    all_game_scores = []

    for i in range(num_sims):
        sim = GameSimulator(home_team_data, away_team_data)
        results = sim.run_simulation()
        all_home_players.append(results['home_players'])
        all_away_players.append(results['away_players'])
        all_home_goalies.append(results['home_goalie'])
        all_away_goalies.append(results['away_goalie'])
        
        home_goals = results['home_players']['Goals_Total'].sum()
        away_goals = results['away_players']['Goals_Total'].sum()
        all_game_scores.append((home_goals, away_goals))

        print(f"Completed Simulation {i+1}/{num_sims}")

    avg_home_players = pd.concat(all_home_players).groupby(['player_id', 'Player']).mean().reset_index()
    avg_away_players = pd.concat(all_away_players).groupby(['player_id', 'Player']).mean().reset_index()
    avg_home_goalie = pd.concat(all_home_goalies).groupby(['Player']).mean().reset_index()
    avg_away_goalie = pd.concat(all_away_goalies).groupby(['Player']).mean().reset_index()

    def calculate_per_60(df, stats, toi_col_suffix):
        toi_col = f'TOI_{toi_col_suffix}'
        if toi_col in df.columns:
            df[toi_col] = df[toi_col] / 60
            for stat in stats:
                stat_col = f'{stat}_{toi_col_suffix}'
                if stat_col in df.columns:
                    new_col_name = f'Sim_{stat}_per_60_{toi_col_suffix}'
                    df[new_col_name] = np.where(df[toi_col] > 0, (df[stat_col] / df[toi_col]) * 60, 0)
        return df

    es_stats = ['iHDCF', 'iMDCF', 'iLDCF', 'OnIce_HDCA', 'OnIce_MDCA', 'OnIce_LDCA', 
                'xG_for', 'ReboundsCreated', 'PenaltiesDrawn', 'ControlledEntries', 'ControlledExits']
    pp_stats = ['iHDCF', 'iMDCF', 'iLDCF', 'xG_for', 'ReboundsCreated', 'PenaltiesDrawn', 'ControlledEntries']
    pk_stats = ['OnIce_HDCA', 'OnIce_MDCA', 'OnIce_LDCA', 'PK_Clears']

    for df in [avg_home_players, avg_away_players]:
        df = calculate_per_60(df, es_stats, 'ES')
        df = calculate_per_60(df, pp_stats, 'PP')
        df = calculate_per_60(df, pk_stats, 'PK')
        if 'TOI_Total' in df.columns: df['TOI_Total'] /= 60

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