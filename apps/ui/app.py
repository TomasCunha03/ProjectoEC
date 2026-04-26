import os
import time

import requests
import streamlit as st
from dotenv import load_dotenv

from chat_saude.dashboard import DashboardFilters
from chat_saude.dashboard.ui import render_dashboard_section
from chat_saude.dashboard.ui.data import clear_dashboard_cache

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

    normalized_payload = dict(payload)
    # Backward compatibility with previous dashboard key names.
    if (
        "immunization_start_year" not in normalized_payload
        and "bcg_start_year" in normalized_payload
    ):
        normalized_payload["immunization_start_year"] = normalized_payload.get("bcg_start_year")
    if "immunization_end_year" not in normalized_payload and "bcg_end_year" in normalized_payload:
        normalized_payload["immunization_end_year"] = normalized_payload.get("bcg_end_year")

    allowed_keys = {
        "global_start_year",
        "global_end_year",
        "global_country",
        "global_disease_name",
        "global_disease_category",
        "immunization_start_year",
        "immunization_end_year",
        "vaccine_code",
        "top_n",
        "chronic_start_year",
        "chronic_end_year",
        "chronic_location",
        "chronic_topic",
    }
    filtered_payload = {
        k: normalized_payload.get(k) for k in allowed_keys if k in normalized_payload
    }
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
def typewriter_effect(text, speed=0.01):
    placeholder = st.empty()
    typed = ""

    for char in text:
        typed += char
        placeholder.markdown(typed)
        time.sleep(speed)


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

            for i, msg in enumerate(recent_messages):
                avatar = "🧑" if msg["role"] == "user" else "👨🏻‍⚕️"

                with st.chat_message(msg["role"], avatar=avatar):
                    if (
                        i == len(recent_messages) - 1
                        and msg["role"] == "assistant"
                        and st.session_state.get("phase") == "done"
                    ):
                        placeholder = st.empty()
                        typed = ""

                        for char in st.session_state.temp_response:
                            typed += char
                            placeholder.markdown(typed)
                            time.sleep(0.02)

                    else:
                        st.markdown(msg["content"])

        with st.form("chat_form", clear_on_submit=True):
            prompt = st.text_input(
                "Message", placeholder="Type here...", label_visibility="collapsed"
            )
            submitted = st.form_submit_button("Send", use_container_width=True)

        if submitted and prompt.strip():
            st.session_state.messages.append({"role": "user", "content": prompt})
            st.session_state.messages.append({"role": "assistant", "content": "🧠 Thinking ..."})

            st.session_state.phase = "thinking"
            st.session_state.pending_prompt = prompt

            st.rerun()

        if st.session_state.get("phase") == "thinking":
            prompt = st.session_state.pending_prompt

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
                    resp_json = r.json()
                    response = resp_json.get("response", "No response from API.")

                    # If the API returned dashboard filters, update session state
                    if "dashboard_filters" in resp_json:
                        new_filters = resp_json["dashboard_filters"]
                        if isinstance(new_filters, dict):
                            if new_filters:
                                # Merge new filters into existing ones
                                current = st.session_state.get("dashboard_filters", {})
                                if not isinstance(current, dict):
                                    current = {}
                                current.update(new_filters)
                                st.session_state.dashboard_filters = current
                            else:
                                # Empty dict means reset all filters
                                st.session_state.dashboard_filters = {}

                            # Ensure dashboard re-queries SQL after chat-driven filter changes.
                            clear_dashboard_cache()
            except requests.RequestException as exc:
                response = f"API connection error: {exc}"

            st.session_state.messages.append({"role": "assistant", "content": response})
                r = requests.post(api_url, json={"message": prompt}, timeout=600)
                data = r.json()

                response = data.get("response", "No response from API.")
                tool = data.get("tool_used", "llm")

                tool_map = {
                    "rag_answer": "Checking documents...",
                    "sql_query": "Checking SQL...",
                    "mongo_query": "Checking MongoDB...",
                    "llm": "Generating response...",
                }

                status = tool_map.get(tool, "Processing ...")

            except Exception as e:
                status = "Erro de ligação à API"
                response = str(e)

            st.session_state.messages[-1]["content"] = status

            st.session_state.temp_response = response
            st.session_state.phase = "show_status"

            st.rerun()

        if st.session_state.get("phase") == "show_status":
            time.sleep(4.5)
            st.session_state.phase = "done"
            st.rerun()

        if st.session_state.get("phase") == "done":
            response = st.session_state.temp_response
            st.session_state.messages[-1]["content"] = response

            st.session_state.phase = None
            st.session_state.pending_prompt = None

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
