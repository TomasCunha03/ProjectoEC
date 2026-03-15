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
    st.subheader("Um chatbot inteligente para diagnosticar doenças e outras mazelas")
    image = Image.open("src/assets/Dr.House_S4E3_15.png")
    st.image(image, use_container_width=True)

    st.markdown(
        """
        O uso deste chatbot não substitui a consulta de um médico a sério.
        """
    )

    if st.button("💬 Conversar com o DrHouseGPT", use_container_width=True):
        st.session_state.page = "chat"
        st.rerun()

    # Expander com os testes de status

    with st.expander("⚙️ Estado do sistema"):
        st.header("Status da Infraestrutura")
        col1, col2, col3 = st.columns(3)

        with col1:
            if test_sql():
                st.success("SQL (PostgreSQL) - Conectado")
            else:
                st.error("SQL - Falha na Ligação")

        with col2:
            if test_nosql():
                st.success("NoSQL (MongoDB) - Conectado")
            else:
                st.error("NoSQL - Falha na Ligação")

        with col3:
            if test_vector():
                st.success("Vetorial (Chroma) - Conectado")
            else:
                st.warning("Vetorial - Offline ou em Setup")


# Página de Chat


def chat_page():
    st.title("👨🏻‍⚕️ DrHouseGPT")

    st.caption("Escreve uma mensagem para iniciar a conversa")

    # Mostrar histórico
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # Input do utilizador
    if prompt := st.chat_input("Escreve aqui..."):
        st.session_state.messages.append({"role": "user", "content": prompt})

        with st.chat_message("user"):
            st.markdown(prompt)

        # ---- Aqui entra a lógica do chatbot (mock por agora) ----
        API_URL = f"http://{os.getenv('API_HOST')}:{os.getenv('API_PORT')}/chat/"

        r = requests.post(
            API_URL,
            json={"message": prompt},
            timeout=600,
        )

        if r.status_code != 200:
            response = f"Erro da API: {r.status_code} - {r.text}"
        else:
            response = r.json()["response"]

        st.session_state.messages.append({"role": "assistant", "content": response})

        with st.chat_message("assistant"):
            st.markdown(response)

    st.markdown("---")

    if st.button("⬅ Voltar"):
        st.session_state.page = "landing"
        st.rerun()


# Router

if st.session_state.page == "landing":
    landing_page()
else:
    chat_page()
