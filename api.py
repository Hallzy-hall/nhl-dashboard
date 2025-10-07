# api.py
import os
from flask import Flask, request, jsonify
from src.simulation_engine import run_multiple_simulations
import pandas as pd

app = Flask(__name__)

@app.route('/run-simulation', methods=['POST'])
def run_simulation_endpoint():
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "Bad Request: No JSON body found"}), 400

        num_sims = data.get("numSims")
        home_team_data = data.get("homeTeamData")
        away_team_data = data.get("awayTeamData")

        # Reconstruct DataFrames from the JSON payload
        home_team_data['lineup'] = pd.DataFrame(home_team_data['lineup'])
        away_team_data['lineup'] = pd.DataFrame(away_team_data['lineup'])

        # Run the simulation engine
        results = run_multiple_simulations(num_sims, home_team_data, away_team_data)

        # Convert final DataFrames to JSON strings for the response
        for key, value in results.items():
            if isinstance(value, pd.DataFrame):
                results[key] = value.to_json(orient='split')

        return jsonify(results)

    except Exception as e:
        print(f"An error occurred: {e}") # This will show up in your Cloud Run logs
        return jsonify({"error": "Internal Server Error", "details": str(e)}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)