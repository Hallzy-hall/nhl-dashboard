import streamlit as st
import pandas as pd
from src.data_processing import load_simulation_results

# ==============================================================================
# --- STYLING & HELPER FUNCTIONS ---
# ==============================================================================

def _apply_color_styling(df, colors):
    """
    Applies a faded background color to each row based on a list of hex codes.
    """
    def style_row(row, color):
        if color and isinstance(color, str) and color.startswith('#'):
            return [f'background-color: {color}26'] * len(row)
        return [''] * len(row)

    # Create a new styler object from the DataFrame
    styler = df.style
    # Apply the styling row by row using the provided colors
    for i, color in enumerate(colors):
        styler = styler.apply(style_row, color=color, axis=1, subset=pd.IndexSlice[i:i, :])
    return styler


def _format_american_odds(val):
    """Formats American odds to always show a + for positive values."""
    if isinstance(val, (int, float)) and val > 0:
        return f"+{val}"
    return str(val)

# --- NEW: Helper function for Decimal odds formatting ---
def _format_decimal_odds(val):
    """Formats decimal odds to always show two decimal places."""
    if isinstance(val, (int, float)):
        return f"{val:.2f}"
    return str(val)


# ==============================================================================
# --- DEDICATED DISPLAY FUNCTIONS ---
# ==============================================================================

def _display_main_market_odds(odds_data, odds_format):
    """Renders the three main betting markets (Moneyline, Puckline, Total)."""
    if not odds_data:
        st.warning("Main market odds data is missing.")
        return

    home_name = st.session_state.dashboard_data['home'].get('team_name', 'Home').split()[-1]
    away_name = st.session_state.dashboard_data['away'].get('team_name', 'Away').split()[-1]

    # Determine which odds keys to use based on the format toggle
    if odds_format == 'American':
        ml_home_odds = _format_american_odds(odds_data['moneyline']['home_american'])
        ml_away_odds = _format_american_odds(odds_data['moneyline']['away_american'])
        pl_home_odds = _format_american_odds(odds_data['puckline']['home_american'])
        pl_away_odds = _format_american_odds(odds_data['puckline']['away_american'])
        total_over_odds = _format_american_odds(odds_data['total']['over_american'])
        total_under_odds = _format_american_odds(odds_data['total']['under_american'])
    else: # Decimal
        ml_home_odds = _format_decimal_odds(odds_data['moneyline']['home_decimal'])
        ml_away_odds = _format_decimal_odds(odds_data['moneyline']['away_decimal'])
        pl_home_odds = _format_decimal_odds(odds_data['puckline']['home_decimal'])
        pl_away_odds = _format_decimal_odds(odds_data['puckline']['away_decimal'])
        total_over_odds = _format_decimal_odds(odds_data['total']['over_decimal'])
        total_under_odds = _format_decimal_odds(odds_data['total']['under_decimal'])

    c1, c2, c3 = st.columns(3)
    
    with c1: 
        st.markdown(f"**Moneyline**")
        st.markdown(f"{home_name}: `{ml_home_odds}`")
        st.markdown(f"{away_name}: `{ml_away_odds}`")
        
    with c2: 
        pl = odds_data['puckline']
        st.markdown(f"**Puckline**")
        st.markdown(f"{home_name}: `{pl['home_spread']:+.1f}` `{pl_home_odds}`")
        st.markdown(f"{away_name}: `{pl['away_spread']:+.1f}` `{pl_away_odds}`")
        
    with c3: 
        total = odds_data['total']
        st.markdown(f"**Total**")
        st.markdown(f"Over {total['line']:.1f}: `{total_over_odds}`")
        st.markdown(f"Under {total['line']:.1f}: `{total_under_odds}`")


def _display_player_prop_odds(prop_data, market_title, odds_format):
    """Renders a single player prop market inside an expander with styling."""
    with st.expander(market_title):
        if not prop_data:
            st.write("No prop data available for this market.")
            return

        prop_df = pd.DataFrame(prop_data)
        
        over_col = f'over_{odds_format.lower()}'
        under_col = f'under_{odds_format.lower()}'

        if over_col not in prop_df.columns or under_col not in prop_df.columns:
            st.error("Required odds columns not found in the data.")
            return

        display_df = prop_df[['player', 'line', over_col, under_col]].copy()
        display_df.rename(columns={
            'player': 'Player', 'line': 'Line',
            over_col: 'Over', under_col: 'Under'
        }, inplace=True)
        
        # --- FIX: Apply correct formatter based on odds_format ---
        formatter = {'Line': '{:.1f}'}
        if odds_format == 'American':
            formatter['Over'] = _format_american_odds
            formatter['Under'] = _format_american_odds
        else: # Decimal
            formatter['Over'] = _format_decimal_odds
            formatter['Under'] = _format_decimal_odds

        if 'team_color' in prop_df.columns and prop_df['team_color'].notna().any():
            colors = prop_df['team_color'].tolist()
            styled_df = _apply_color_styling(display_df, colors)
        else:
            styled_df = display_df.style

        st.markdown(
            styled_df.format(formatter=formatter).hide(axis="index").to_html(), 
            unsafe_allow_html=True
        )

# ==============================================================================
# --- MAIN PAGE FUNCTION ---
# ==============================================================================

def main():
    """Main function to render the betting lines page."""
    st.title("Market")

    current_game_id = st.session_state.get('selected_game_id')
    if not current_game_id:
        st.warning("Please select a fixture from the sidebar to view betting lines.")
        return

    sim_results = load_simulation_results(current_game_id)

    if not sim_results:
        st.info("No simulation has been run for this fixture yet.")
        return
        
    _, c2 = st.columns([3, 1])
    with c2:
        odds_format = st.radio(
            "Odds Format", ['American', 'Decimal'],
            key='odds_format_toggle', horizontal=True,
        )
    
    main_market_tab, player_props_tab = st.tabs(["Main Markets", "Player Props"])

    with main_market_tab:
        main_odds_data = sim_results.get('main_markets')
        if main_odds_data:
            _display_main_market_odds(main_odds_data, odds_format)
        else:
            st.error("Main market odds data is missing from the simulation results.")

    with player_props_tab:
        player_props_data = sim_results.get('player_props')
        if player_props_data:
            _display_player_prop_odds(player_props_data.get('goals', []), "Goals", odds_format)
            _display_player_prop_odds(player_props_data.get('assists', []), "Assists", odds_format)
            _display_player_prop_odds(player_props_data.get('points', []), "Points", odds_format)
            _display_player_prop_odds(player_props_data.get('shots', []), "Shots", odds_format)
            _display_player_prop_odds(player_props_data.get('blocks', []), "Blocks", odds_format)
        else:
            st.error("Player prop data is missing from the simulation results.")

