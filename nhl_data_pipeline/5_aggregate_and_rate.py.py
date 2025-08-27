# 5_aggregate_and_rate.py (Corrected Version with Base Rating)
import os
import toml
from supabase import create_client, Client
import pandas as pd
import numpy as np

# --- Load secrets directly from the .toml file ---
try:
    script_dir = os.path.dirname(__file__)
    secrets_path = os.path.join(script_dir, '..', '.streamlit', 'secrets.toml')
    secrets = toml.load(secrets_path)
    
    SUPABASE_URL = secrets["connections"]["supabase"]["SUPABASE_URL"]
    SUPABASE_KEY = secrets["connections"]["supabase"]["SUPABASE_KEY"]
except FileNotFoundError:
    print("Error: secrets.toml not found. Make sure it's in the .streamlit folder in your project root.")
    exit()

# --- Supabase Connection ---
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# --- 1. Fetch All Player Game Stats ---
print("Fetching all data from 'player_game_stats'...")
response = supabase.table('player_game_stats').select('*').execute()
if not response.data:
    print("❌ No player game stats found. Exiting.")
    exit()

df = pd.DataFrame(response.data)
print(f"✅ Found {len(df)} total player-game entries to process.")

# --- 2. Aggregate Season Totals ---
print("Aggregating season totals for each player...")
agg_rules = {
    'game_id': 'count',
    'toi_seconds': 'sum',
    'shot_attempts': 'sum',
    'shots_blocked': 'sum',
    'faceoffs_won': 'sum',
    'faceoffs_lost': 'sum',
    'on_ice_cf': 'sum',
    'on_ice_ca': 'sum'
}
season_df = df.groupby('player_id').agg(agg_rules).reset_index()
season_df.rename(columns={'game_id': 'games_played'}, inplace=True)

# --- 3. Separate players by TOI threshold ---
MIN_TOI_SECONDS = 1200 # 20 minutes total ice time
print(f"Separating players by minimum TOI threshold ({MIN_TOI_SECONDS} seconds)...")
qualified_df = season_df[season_df['toi_seconds'] > MIN_TOI_SECONDS].copy()
unqualified_df = season_df[season_df['toi_seconds'] <= MIN_TOI_SECONDS].copy()
print(f"Found {len(qualified_df)} qualified players and {len(unqualified_df)} unqualified players.")

# --- 4. Calculate Rates and Ratings for QUALIFIED players ---
if not qualified_df.empty:
    print("Calculating per-60 rates for qualified players...")
    qualified_df['toi_minutes'] = qualified_df['toi_seconds'] / 60
    qualified_df['shot_attempts_p60'] = (qualified_df['shot_attempts'] / qualified_df['toi_minutes']) * 60
    qualified_df['shots_blocked_p60'] = (qualified_df['shots_blocked'] / qualified_df['toi_minutes']) * 60
    qualified_df['faceoffs_taken'] = qualified_df['faceoffs_won'] + qualified_df['faceoffs_lost']
    qualified_df['faceoff_pct'] = qualified_df.apply(
        lambda row: row['faceoffs_won'] / row['faceoffs_taken'] if row['faceoffs_taken'] > 0 else 0,
        axis=1
    )

    print("Calculating Z-scores and final ratings for qualified players...")
    def calculate_ratings(df, stat_col, rating_name):
        mean = df[stat_col].mean()
        std = df[stat_col].std()
        if std == 0:
            df[rating_name] = 1000
        else:
            df[f'{stat_col}_z'] = (df[stat_col] - mean) / std
            df[rating_name] = 1000 + (df[f'{stat_col}_z'] * 250)
        return df

    qualified_df = calculate_ratings(qualified_df, 'shot_attempts_p60', 'oshooting_volume_rating')
    qualified_df = calculate_ratings(qualified_df, 'shots_blocked_p60', 'd_shot_blocking_rating')
    qualified_df = calculate_ratings(qualified_df, 'faceoff_pct', 'faceoff_rating')

# --- 5. Assign Base Ratings to UNQUALIFIED players ---
if not unqualified_df.empty:
    print("Assigning base rating of 750 to unqualified players...")
    rating_columns = ['oshooting_volume_rating', 'd_shot_blocking_rating', 'faceoff_rating']
    for col in rating_columns:
        unqualified_df[col] = 750

# --- 6. Combine DataFrames and Prepare for Upload ---
print("Combining qualified and unqualified player ratings...")
final_df = pd.concat([qualified_df, unqualified_df], ignore_index=True)

print("Uploading final ratings to 'player_season_ratings_test'...")
final_columns = [
    'player_id',
    'games_played',
    'toi_seconds',
    'oshooting_volume_rating',
    'd_shot_blocking_rating',
    'faceoff_rating'
]
final_ratings_df = final_df[final_columns].copy()

final_ratings_df.replace([np.inf, -np.inf], np.nan, inplace=True)
final_ratings_df.fillna(1000, inplace=True) # Fill any remaining NaNs with 1000

records_to_upload = final_ratings_df.to_dict('records')

# --- 7. Upload to Supabase ---
response = supabase.table('player_season_ratings_test').upsert(records_to_upload, on_conflict='player_id').execute()

if response.data:
    print(f"✅ Success! {len(response.data)} player ratings have been updated in the test table.")
else:
    print(f"❌ Error uploading final ratings: {response.error}")

print("\n--- Pipeline finished successfully! ---")