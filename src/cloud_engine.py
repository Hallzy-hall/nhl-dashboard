# src/cloud_engine.py

import requests
import pandas as pd
from typing import Dict, Any
import streamlit as st
from io import StringIO
import numpy as np # Add numpy import to handle NaN

def run_cloud_simulations(
    num_sims: int,
    home_team_data: Dict[str, Any],
    away_team_data: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Triggers the remote Python simulation on Cloud Run and processes the results.
    """
    empty_return = {
        'home_total': pd.DataFrame(), 'home_players': pd.DataFrame(),
        'away_total': pd.DataFrame(), 'away_players': pd.DataFrame(),
        'home_goalie_validation': pd.DataFrame(), 'away_goalie_validation': pd.DataFrame(),
        'all_game_scores': []
    }

    try:
        cloud_run_url = st.secrets.app_secrets.CLOUD_RUN_SIMULATION_URL
    except Exception:
        st.error("Could not find CLOUD_RUN_SIMULATION_URL in secrets.toml.")
        return empty_return

    # --- THIS IS THE FIX ---
    # Convert any NaN values in the lineup DataFrames to None before serialization.
    # JSON can handle `None` (it becomes `null`), but it cannot handle `NaN`.
    home_lineup_clean = home_team_data["lineup"].replace({np.nan: None})
    away_lineup_clean = away_team_data["lineup"].replace({np.nan: None})
    # ----------------------

    # Prepare the payload for the API
    payload = {
        "numSims": num_sims,
        "homeTeamData": {
            # Use the cleaned DataFrames
            "lineup": home_lineup_clean.to_dict(orient="records"),
            "coach": home_team_data["coach"],
            "goalie": home_team_data["goalie"]
        },
        "awayTeamData": {
            # Use the cleaned DataFrames
            "lineup": away_lineup_clean.to_dict(orient="records"),
            "coach": away_team_data["coach"],
            "goalie": away_team_data["goalie"]
        }
    }

    try:
        response = requests.post(cloud_run_url, json=payload, timeout=1200)
        response.raise_for_status() # This will raise an error for non-200 status codes
    except requests.exceptions.RequestException as e:
        st.error(f"Failed to connect to the cloud simulation service: {e}")
        return empty_return

    st.success( "✅ Simulation complete! Processing results..." )
    results_json = response.json()

    # Reconstruct DataFrames from the JSON response
    return {
        'home_total': pd.read_json(StringIO(results_json.get('home_total', '[]')), orient='split'),
        'home_players': pd.read_json(StringIO(results_json.get('home_players', '[]')), orient='split'),
        'away_total': pd.read_json(StringIO(results_json.get('away_total', '[]')), orient='split'),
        'away_players': pd.read_json(StringIO(results_json.get('away_players', '[]')), orient='split'),
        'home_goalie_validation': pd.read_json(StringIO(results_json.get('home_goalie_validation', '[]')), orient='split'),
        'away_goalie_validation': pd.read_json(StringIO(results_json.get('away_goalie_validation', '[]')), orient='split'),
        'all_game_scores': [tuple(score) for score in results_json.get("all_game_scores", [])]
    }