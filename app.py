# app.py (your new home page)
import streamlit as st

st.set_page_config(
    page_title="NHL Analytics Home",
    page_icon="🏒",
)

st.title("Welcome to the NHL Analytics Hub! 🏒")
st.sidebar.success("Select a tool above.")

st.markdown(
    """
    This is a multi-page app designed for advanced NHL analytics and simulation.
    **👈 Select a tool from the sidebar** to get started, such as the Lineup Builder.
    ### Want to learn more?
    - Check out [Streamlit's documentation](https://docs.streamlit.io)
    """
)