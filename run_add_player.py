import argparse
from utils.add_player import add_single_player

def main():
    """
    Command-line interface for manually adding a single NHL player to the database.
    """
    parser = argparse.ArgumentParser(description="Manually add an NHL player to the database.")
    parser.add_argument("player_id", type=int, help="The NHL Player ID (e.g., 8484762 for Beckett Sennecke).")
    parser.add_argument("team_abbr", type=str, help="The 3-letter team abbreviation (e.g., 'ANA' for Anaheim).")

    args = parser.parse_args()

    # Call the function from the utils file
    add_single_player(args.player_id, args.team_abbr)

if __name__ == "__main__":
    main()