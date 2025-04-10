# inject_font.py (now handles both fonts and logo)

import streamlit as st
from PIL import Image

def inject_custom_font():
    # Roboto or your custom font
    st.markdown("""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Roboto&display=swap');

        html, body, [class*="css"]  {
            font-family: 'Roboto', sans-serif;
        }
        </style>
    """, unsafe_allow_html=True)

def inject_sidebar_logo(path="static/dash_logo.png", width=160):
    with st.sidebar:
        st.markdown("<br>", unsafe_allow_html=True)
        st.image(path, width=width)
        st.markdown("<hr style='margin-top:1em;margin-bottom:1em;'>", unsafe_allow_html=True)
