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

def inject_sidebar_logo():
    with st.sidebar:
        st.markdown("### ")
        st.markdown(
            """
            <a href='/' target='_self'>
                <img src='/public/dash_logo.png' style='width:100%; margin-bottom:10px;' />
            </a>
            <hr style='margin-top:10px;'>
            """,
            unsafe_allow_html=True
        )