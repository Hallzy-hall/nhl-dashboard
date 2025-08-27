# generate_game_ids.py

def generate_nhl_season_ids(start_year):
    """
    Generates a list of all regular season and potential playoff game IDs for a given season.
    """
    season_str = str(start_year)
    all_game_ids = []

    # 1. Regular Season (Always 1312 games for a 32-team league)
    # Format: YYYY02NNNN
    num_regular_season_games = 1312
    for i in range(1, num_regular_season_games + 1):
        game_num_str = str(i).zfill(4)
        game_id = f"{season_str}02{game_num_str}"
        all_game_ids.append(game_id)

    # 2. Playoffs (Generate all *potential* games, some won't exist)
    # Format: YYYY030RST (R=Round, S=Series, T=Game)
    playoff_structure = {
        1: 8,  # Round 1 has 8 series
        2: 4,  # Round 2 has 4 series
        3: 2,  # Round 3 has 2 series (Conference Finals)
        4: 1   # Round 4 has 1 series (Stanley Cup Final)
    }

    for round_num, num_series in playoff_structure.items():
        for series_num in range(1, num_series + 1):
            for game_num in range(1, 8): # Series are best-of-7
                game_id = f"{season_str}030{round_num}{series_num}{game_num}"
                all_game_ids.append(game_id)
                
    return all_game_ids

if __name__ == "__main__":
    # --- CONFIGURATION ---
    SEASON_START_YEAR = 2024
    
    # --- EXECUTION ---
    game_ids_for_season = generate_nhl_season_ids(SEASON_START_YEAR)
    
    # --- OUTPUT ---
    print("Copy the list below into your '1_fetch_game_data.py' script.")
    print("\nGAME_IDS_TO_FETCH = [")
    for game_id in game_ids_for_season:
        print(f'    "{game_id}",')
    print("]")
    
    print(f"\nGenerated a total of {len(game_ids_for_season)} potential game IDs for the {SEASON_START_YEAR}-{SEASON_START_YEAR+1} season.")