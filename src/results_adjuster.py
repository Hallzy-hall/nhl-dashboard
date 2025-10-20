import pandas as pd
from copy import deepcopy

class ResultAdjuster:
    """
    Adjusts the results of a baseline simulation based on changes to player ratings.
    This model does NOT re-run a simulation. Instead, it calculates the mathematical
    impact of a rating change and re-allocates stats among players to reflect that
    change, providing a near-instant result.
    """
    def __init__(self, baseline_payload, new_sim_data):
        """
        Initializes the ResultAdjuster.

        Args:
            baseline_payload (dict): The full payload from the initial Poisson sim.
            new_sim_data (dict): The new simulation input data from the dashboard.
        """
        self.baseline_results = baseline_payload['results']
        self.baseline_inputs = baseline_payload['inputs']
        self.new_inputs = new_sim_data
        
        self.adjusted_results = deepcopy(self.baseline_results)
        
        # Create player maps for quick lookups
        self.home_player_map = {p['player_id']: p for p in self.new_inputs['home_team']['players']}
        self.away_player_map = {p['player_id']: p for p in self.new_inputs['away_team']['players']}
        self.all_player_map = {**self.home_player_map, **self.away_player_map}


    def run(self):
        """
        Main execution method. Identifies and applies all rating changes.
        """
        print("Starting result adjustment...")
        self._compare_and_apply_all_changes()
        print("Result adjustment finished.")
        return self.adjusted_results

    def _compare_and_apply_all_changes(self):
        """
        Loops through all players on both teams and triggers adjustment logic.
        """
        all_new_players = self.new_inputs['home_team']['players'] + self.new_inputs['away_team']['players']
        
        baseline_home_players = {p['player_id']: p for p in self.baseline_inputs['home_team']['players']}
        baseline_away_players = {p['player_id']: p for p in self.baseline_inputs['away_team']['players']}
        all_baseline_players = {**baseline_home_players, **baseline_away_players}

        for player_data in all_new_players:
            player_id = player_data['player_id']
            if player_id not in all_baseline_players:
                continue

            baseline_player_ratings = all_baseline_players[player_id]['ratings']
            for rating_name, new_value in player_data['ratings'].items():
                old_value = baseline_player_ratings.get(rating_name)

                if new_value != old_value:
                    print(f"Detected change for Player {player_id}, Rating '{rating_name}': {old_value} -> {new_value}")
                    self._dispatch_adjustment(player_id, rating_name, old_value, new_value)

    def _dispatch_adjustment(self, player_id, rating_name, old_value, new_value):
        """
        Acts as a router, calling the appropriate adjustment function for each rating.
        """
        # --- Even Strength Ratings ---
        if rating_name == 'shooting_volume':
            self._adjust_stat_zero_sum(player_id, old_value, new_value, 'Shot Attempts_Total', 'Goals_Total', 'Shooting %_Total')
        elif rating_name == 'shooting_talent':
             self._adjust_stat_outcome(player_id, old_value, new_value, 'Goals_Total', 'Shot Attempts_Total', 'Shooting %_Total')
        elif rating_name == 'playmaking_passing':
            self._adjust_stat_zero_sum(player_id, old_value, new_value, 'Assists_Total', None, None, pool_type='teammates')
        elif rating_name in ['shot_suppression', 'defensive_positioning']:
             self._adjust_stat_inter_team(player_id, old_value, new_value, 'Shot Attempts_Total', 'Goals_Total', 'Shooting %_Total')
        
        # --- Power Play Ratings ---
        elif rating_name == 'pp_shooting_volume':
            self._adjust_stat_zero_sum(player_id, old_value, new_value, 'Shot Attempts_PP', 'Goals_PP', 'Shooting %_PP')
        elif rating_name == 'pp_shooting_talent':
            self._adjust_stat_outcome(player_id, old_value, new_value, 'Goals_PP', 'Shot Attempts_PP', 'Shooting %_PP')
        elif rating_name == 'pp_playmaking_passing':
            self._adjust_stat_zero_sum(player_id, old_value, new_value, 'Assists_PP', None, None, pool_type='teammates')

        # --- Penalty Kill Ratings ---
        elif rating_name in ['pk_shot_suppression', 'pk_shot_blocking']:
            self._adjust_stat_inter_team(player_id, old_value, new_value, 'Shot Attempts_PP', 'Goals_PP', 'Shooting %_PP')

        else:
            print(f"No adjustment logic implemented for '{rating_name}'. Skipping.")

    def _convert_rating_to_modifier(self, rating):
        """
        Converts a 1000-based rating into a simulation modifier.
        """
        std_dev = 200
        impact_factor = 0.275
        z_score = (rating - 1000) / std_dev
        modifier = 1 + (z_score * impact_factor)
        return modifier
        
    # --- GENERIC ADJUSTMENT LOGIC ---

    def _adjust_stat_zero_sum(self, player_id, old_rating, new_rating, primary_stat, secondary_stat, rate_stat, pool_type='positional_teammates'):
        """
        Adjusts a stat where a player's gain is a teammate's loss.
        Used for: shooting_volume, playmaking_passing, pp_shooting_volume, etc.
        """
        old_modifier = self._convert_rating_to_modifier(old_rating)
        new_modifier = self._convert_rating_to_modifier(new_rating)
        if old_modifier == 0: return
        delta_ratio = new_modifier / old_modifier

        df, opponent_df = self._get_relevant_dfs(player_id)
        if player_id not in df.index: return

        # 1. Apply change to the primary player
        old_value = df.loc[player_id, primary_stat]
        new_value = old_value * delta_ratio
        delta = new_value - old_value
        df.loc[player_id, primary_stat] = new_value
        
        # Update secondary stats if applicable (e.g., Goals from Shots)
        if secondary_stat and rate_stat:
            rate = df.loc[player_id, rate_stat] if df.loc[player_id, primary_stat] > 0 else 0
            df.loc[player_id, secondary_stat] = new_value * rate
        
        # 2. Re-allocate the negative delta to the pool
        pool_ids = self._get_player_pool(player_id, df, pool_type)
        pool_df = df.loc[df.index.isin(pool_ids)]
        pool_total = pool_df[primary_stat].sum()

        if pool_total > 0:
            for pool_player_id in pool_ids:
                if pool_player_id in df.index:
                    share = df.loc[pool_player_id, primary_stat] / pool_total
                    value_to_remove = delta * share
                    
                    teammate_new_value = df.loc[pool_player_id, primary_stat] - value_to_remove
                    df.loc[pool_player_id, primary_stat] = teammate_new_value

                    if secondary_stat and rate_stat:
                        teammate_rate = df.loc[pool_player_id, rate_stat] if df.loc[pool_player_id, primary_stat] > 0 else 0
                        df.loc[pool_player_id, secondary_stat] = teammate_new_value * teammate_rate

    def _adjust_stat_inter_team(self, player_id, old_rating, new_rating, primary_stat, secondary_stat, rate_stat):
        """
        Adjusts a stat where a player's skill impacts their opponents.
        Used for: defensive_positioning, shot_suppression, pk_ratings.
        """
        old_modifier = self._convert_rating_to_modifier(old_rating)
        new_modifier = self._convert_rating_to_modifier(new_rating)
        if new_modifier == 0: return
        # Defensive ratings have an inverse effect
        delta_ratio = old_modifier / new_modifier

        df, opponent_df = self._get_relevant_dfs(player_id)
        
        # This change affects the *entire* opponent team, proportionally
        opponent_total = opponent_df[primary_stat].sum()
        if opponent_total == 0: return

        # Calculate the total change that needs to be applied
        total_delta = opponent_total * (1 - delta_ratio) 

        for opp_id in opponent_df.index:
            share = opponent_df.loc[opp_id, primary_stat] / opponent_total
            value_to_remove = total_delta * share
            
            opp_new_value = opponent_df.loc[opp_id, primary_stat] - value_to_remove
            opponent_df.loc[opp_id, primary_stat] = opp_new_value
            
            if secondary_stat and rate_stat:
                opp_rate = opponent_df.loc[opp_id, rate_stat] if opponent_df.loc[opp_id, primary_stat] > 0 else 0
                opponent_df.loc[opp_id, secondary_stat] = opp_new_value * opp_rate

    def _adjust_stat_outcome(self, player_id, old_rating, new_rating, primary_stat, dependency_stat, rate_stat):
        """
        Adjusts an outcome rate (like Shooting %) without changing event volume.
        Used for: shooting_talent, pp_shooting_talent.
        """
        old_modifier = self._convert_rating_to_modifier(old_rating)
        new_modifier = self._convert_rating_to_modifier(new_rating)
        if old_modifier == 0: return
        delta_ratio = new_modifier / old_modifier
        
        df, _ = self._get_relevant_dfs(player_id)
        if player_id not in df.index: return
        
        # 1. Calculate new rate
        old_rate = df.loc[player_id, rate_stat]
        new_rate = old_rate * delta_ratio
        df.loc[player_id, rate_stat] = new_rate
        
        # 2. Update primary stat based on the new rate and existing dependency stat
        dependency_value = df.loc[player_id, dependency_stat]
        df.loc[player_id, primary_stat] = dependency_value * new_rate

    # --- HELPER METHODS ---

    def _get_relevant_dfs(self, player_id):
        """Gets the player's dataframe and their opponent's dataframe."""
        if player_id in self.home_player_map:
            return self.adjusted_results['home_players'], self.adjusted_results['away_players']
        else:
            return self.adjusted_results['away_players'], self.adjusted_results['home_players']
    
    def _get_player_pool(self, player_id, player_df, pool_type='positional_teammates'):
        """Identifies the pool of players for re-allocation."""
        primary_player_pos = self.all_player_map[player_id]['position']
        
        pool_ids = []
        for pid in player_df.index:
            if pid == player_id: continue
            
            pdata = self.all_player_map.get(pid)
            if not pdata: continue

            if pool_type == 'positional_teammates':
                is_same_pos_type = (pdata['position'] in ['C', 'LW', 'RW'] and primary_player_pos != 'D') or \
                                   (pdata['position'] == 'D' and primary_player_pos == 'D')
                if is_same_pos_type:
                    pool_ids.append(pid)
            
            elif pool_type == 'teammates':
                 pool_ids.append(pid)

        return pool_ids

