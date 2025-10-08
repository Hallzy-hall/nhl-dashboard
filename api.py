# api.py (with enhanced error logging)
import os
from flask import Flask, request, jsonify
from src.simulation_engine import run_multiple_simulations
import pandas as pd
import traceback # Import the traceback module

app = Flask(__name__)

@app.route('/run-simulation', methods=['POST'])
def run_simulation_endpoint():
    print("--- Received new simulation request ---")
    try:
        # --- NEW: Log the raw request body to help diagnose input errors ---
        raw_data = request.data
        print(f"--- Raw request body (first 500 chars): {raw_data[:500]}...")
        # --- END NEW LOGGING ---

        data = request.get_json()
        if not data:
            print("!!! ERROR: No JSON body found in request.")
            return jsonify({"error": "Bad Request: No JSON body found"}), 400

        num_sims = data.get("numSims")
        home_team_data = data.get("homeTeamData")
        away_team_data = data.get("awayTeamData")
        print(f"--- Preparing to run {num_sims} simulations. ---")

        # Reconstruct DataFrames from the JSON payload
        home_team_data['lineup'] = pd.DataFrame(home_team_data['lineup'])
        away_team_data['lineup'] = pd.DataFrame(away_team_data['lineup'])

        # Run the simulation engine
        results = run_multiple_simulations(num_sims, home_team_data, away_team_data)
        print("--- Simulation engine finished successfully. Preparing response. ---")

        # Convert final DataFrames to JSON strings for the response
        for key, value in results.items():
            if isinstance(value, pd.DataFrame):
                results[key] = value.to_json(orient='split')

        print("--- Sending back successful JSON response. ---")
        return jsonify(results)

    except Exception as e:
        # This will print the full, detailed error to your Google Cloud logs
        print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
        print("!!! AN UNHANDLED EXCEPTION OCCURRED IN API   !!!")
        print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
        print(f"Exception Type: {type(e).__name__}")
        print(f"Exception Details: {e}")
        print("--- Full Traceback ---")
        traceback.print_exc()
        print("----------------------")
        return jsonify({"error": "Internal Server Error", "details": str(e)}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)
