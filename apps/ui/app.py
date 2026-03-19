import os

import requests
import streamlit as st
from dotenv import load_dotenv
from PIL import Image

from chat_saude.infrastructure.database.db_connection import test_nosql, test_sql, test_vector

load_dotenv()


# Configuração geral

st.set_page_config(page_title="DrHouseGPT", page_icon="💉", layout="centered")

if "page" not in st.session_state:
    st.session_state.page = "landing"

if "messages" not in st.session_state:
    st.session_state.messages = []


# Landing Page


def landing_page():
    st.title("DrHouseGPT")
    st.subheader("An intelligent chatbot for diagnosing diseases and other ailments")
    image = Image.open("src/assets/Dr.House_S4E3_15.png")
    st.image(image, use_container_width=True)

    st.markdown(
        """
        Using this chatbot does not replace a real consultation with a healthcare professional.
        """
    )

    if st.button("💬 Chat with DrHouseGPT", use_container_width=True):
        st.session_state.page = "chat"
        st.rerun()

    # Expander com os testes de status

    with st.expander("⚙️ System status"):
        st.header("Infrastructure status")
        col1, col2, col3 = st.columns(3)

        with col1:
            if test_sql():
                st.success("SQL (PostgreSQL) - Connected")
            else:
                st.error("SQL - Connection failed")

        with col2:
            if test_nosql():
                st.success("NoSQL (MongoDB) - Connected")
            else:
                st.error("NoSQL - Connection failed")

        with col3:
            if test_vector():
                st.success("Vector (Chroma) - Connected")
            else:
                st.warning("Vector - Offline or in setup")


# Página de Chat


def chat_page():
    st.title("👨🏻‍⚕️ DrHouseGPT")

    st.caption("Type a message to start the conversation")

    # Mostrar histórico
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # Input do utilizador
    if prompt := st.chat_input("Type here..."):
        st.session_state.messages.append({"role": "user", "content": prompt})

        with st.chat_message("user"):
            st.markdown(prompt)

        # ---- Chatbot logic is triggered here (mock for now) ----
        API_URL = f"http://{os.getenv('API_HOST')}:{os.getenv('API_PORT')}/chat/"

        r = requests.post(
            API_URL,
            json={"message": prompt},
            timeout=600,
        )

        if r.status_code != 200:
            response = f"API error: {r.status_code} - {r.text}"
        else:
            response = r.json()["response"]

        st.session_state.messages.append({"role": "assistant", "content": response})

        with st.chat_message("assistant"):
            st.markdown(response)

    st.markdown("---")

    if st.button("⬅ Back"):
        st.session_state.page = "landing"
        st.rerun()


# Router

if st.session_state.page == "landing":
    landing_page()
else:
    chat_page()
