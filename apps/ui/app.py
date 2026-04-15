import os

import requests
import streamlit as st
from dotenv import load_dotenv

from chat_saude.dashboard import DashboardFilters
from chat_saude.dashboard.ui import render_dashboard_section

load_dotenv()


# General configuration

st.set_page_config(page_title="DrHouseGPT", page_icon="💉", layout="wide")

if "page" not in st.session_state:
    st.session_state.page = "landing"

if "messages" not in st.session_state:
    st.session_state.messages = []


def apply_layout_styles():
    st.markdown(
        """
        <style>
        [data-testid="stAppViewContainer"],
        [data-testid="stAppViewContainer"] > .main {
            height: 100vh;
            overflow: hidden;
        }

        [data-testid="stAppViewContainer"] .main .block-container {
            max-width: 100%;
            padding-top: 0.8rem;
            padding-bottom: 0.8rem;
            padding-left: 1rem;
            padding-right: 1rem;
            height: 100vh;
            overflow: hidden;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


apply_layout_styles()


@st.cache_data(show_spinner=False)
def load_landing_image(path: str) -> bytes:
    with open(path, "rb") as file:
        return file.read()


def get_dashboard_filters_from_chat() -> DashboardFilters:
    payload = st.session_state.get("dashboard_filters", {})
    if not isinstance(payload, dict):
        return DashboardFilters()

    allowed_keys = {
        "global_start_year",
        "global_end_year",
        "global_country",
        "global_disease_category",
        "chronic_start_year",
        "chronic_end_year",
        "chronic_location",
        "chronic_topic",
    }
    filtered_payload = {k: payload.get(k) for k in allowed_keys if k in payload}
    return DashboardFilters(**filtered_payload)


# Landing Page


def landing_page():
    left, center, right = st.columns([1, 1.3, 1])
    with center:
        with st.container(border=True):
            st.markdown(
                """
                <h1 style="text-align:center; margin-bottom:0.25rem;">DrHouseGPT</h1>
                <p style="text-align:center; font-size:1.15rem; margin-top:0;">
                    An intelligent chatbot for diagnosing diseases and other ailments
                </p>
                """,
                unsafe_allow_html=True,
            )

            image_bytes = load_landing_image("src/assets/Dr.House_S4E3_15.png")
            st.image(image_bytes, use_container_width=True)

            st.markdown(
                """
                <p style="text-align:center; margin:0.5rem 0 1rem 0;">
                    Using this chatbot does not replace a real consultation
                    with a healthcare professional.
                </p>
                """,
                unsafe_allow_html=True,
            )

            if st.button("💬 Enter chat", use_container_width=True):
                st.session_state.page = "chat"
                st.rerun()


# Chat Page


def chat_page():
    st.title("👨🏻‍⚕️ DrHouseGPT")

    left_col, right_col = st.columns([0.78, 1.22], gap="medium")

    with left_col:
        st.subheader("Chat")
        chat_history = st.container(height=520, border=True)
        with chat_history:
            recent_messages = st.session_state.messages[-12:]
            if not recent_messages:
                st.info("Send a message to start.")
            for msg in recent_messages:
                avatar = "🧑" if msg["role"] == "user" else "👨🏻‍⚕️"
                with st.chat_message(msg["role"], avatar=avatar):
                    st.markdown(msg["content"])

        with st.form("chat_form", clear_on_submit=True):
            prompt = st.text_input(
                "Message", placeholder="Type here...", label_visibility="collapsed"
            )
            submitted = st.form_submit_button("Send", use_container_width=True)

        if submitted and prompt.strip():
            st.session_state.messages.append({"role": "user", "content": prompt})

            api_url = f"http://{os.getenv('API_HOST')}:{os.getenv('API_PORT')}/chat/"
            try:
                r = requests.post(
                    api_url,
                    json={"message": prompt},
                    timeout=600,
                )
                if r.status_code != 200:
                    response = f"API error: {r.status_code} - {r.text}"
                else:
                    response = r.json().get("response", "No response from API.")
            except requests.RequestException as exc:
                response = f"API connection error: {exc}"

            st.session_state.messages.append({"role": "assistant", "content": response})
            st.rerun()

        if st.button("⬅ Back", use_container_width=True):
            st.session_state.page = "landing"
            st.rerun()

    with right_col:
        dashboard_panel = st.container(height=760, border=True)
        with dashboard_panel:
            render_dashboard_section(get_dashboard_filters_from_chat())


# Router

if st.session_state.page == "landing":
    landing_page()
else:
    chat_page()
