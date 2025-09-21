# app_pages/database_page.py

import streamlit as st
import pandas as pd
from utils.db_queries import get_teams # We can add more queries here later

# Placeholder for a function to get all players
def get_all_players():
    # In the future, this would be a real database call
    st.warning("This is placeholder data. A function to fetch all players from the DB needs to be created.")
    return pd.DataFrame({
        'full_name': ['Connor McDavid', 'Auston Matthews', 'Nathan MacKinnon'],
        'team': ['EDM', 'TOR', 'COL'],
        'position': ['C', 'C', 'C']
    })

def main():
    st.title("Database Viewer")

    tab1, tab2, tab3 = st.tabs(["Teams", "Players", "Coaches"])

    with tab1:
        st.subheader("All Teams")
        teams_df = get_teams()
        if not teams_df.empty:
            st.dataframe(teams_df, use_container_width=True, hide_index=True)
        else:
            st.error("Could not load team data.")

    with tab2:
        st.subheader("All Players")
        players_df = get_all_players() # Using our placeholder
        st.dataframe(players_df, use_container_width=True, hide_index=True)

    with tab3:
        st.subheader("All Coaches")
        st.info("Coach data viewer coming soon.")