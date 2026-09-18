from pathlib import Path
import os
import struct

import pandas as pd
import pyodbc
import streamlit as st

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from azure.identity import InteractiveBrowserCredential


# =========================================================
# CONFIGURAÇÃO
# =========================================================

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = PROJECT_ROOT / ".env"

load_dotenv(ENV_FILE, override=True)

SERVER = os.getenv("AZURE_SQL_SERVER")
DATABASE = os.getenv("AZURE_SQL_DATABASE")
USER = os.getenv("AZURE_SQL_USER")
DRIVER = os.getenv(
    "AZURE_SQL_DRIVER",
    "ODBC Driver 18 for SQL Server"
)

TOKEN_SCOPE = "https://database.windows.net/.default"
SQL_COPT_SS_ACCESS_TOKEN = 1256


# =========================================================
# CREDENCIAL MICROSOFT ENTRA
# =========================================================

@st.cache_resource
def get_credential():

    return InteractiveBrowserCredential(
        login_hint=USER or None
    )


# =========================================================
# CONEXÃO AZURE SQL
# =========================================================

def create_connection():

    credential = get_credential()

    token = credential.get_token(
        TOKEN_SCOPE
    )

    token_bytes = token.token.encode(
        "utf-16-le"
    )

    token_struct = struct.pack(
        f"<I{len(token_bytes)}s",
        len(token_bytes),
        token_bytes
    )

    connection_string = (
        f"DRIVER={{{DRIVER}}};"
        f"SERVER={SERVER};"
        f"DATABASE={DATABASE};"
        "Encrypt=yes;"
        "TrustServerCertificate=no;"
        "Connection Timeout=30;"
    )

    return pyodbc.connect(
        connection_string,
        attrs_before={
            SQL_COPT_SS_ACCESS_TOKEN: token_struct
        }
    )


# =========================================================
# SQLALCHEMY ENGINE
# =========================================================

@st.cache_resource
def get_engine():

    return create_engine(
        "mssql+pyodbc://",
        creator=create_connection,
        pool_pre_ping=True
    )


# =========================================================
# CONSULTAS
# =========================================================

def get_database_name():

    engine = get_engine()

    with engine.connect() as conn:

        return conn.execute(
            text("SELECT DB_NAME()")
        ).scalar_one()


@st.cache_data(ttl=300)
def carregar_forecast():

    engine = get_engine()

    query = """
        SELECT
            data_referencia,
            data_previsao,
            prioridade,
            horizonte_dias,
            volume_previsto,
            modelo
        FROM gold.fct_previsao_futura
        ORDER BY data_previsao, prioridade
    """

    return pd.read_sql(
        query,
        engine
    )


@st.cache_data(ttl=300)
def carregar_risco_ola():

    engine = get_engine()

    query = """
        SELECT
            numero_incidente,
            aberto,
            prioridade,
            produto,
            categoria,
            grupo_designado,
            score_risco_ola,
            nivel_risco,
            alerta_modelo,
            kpi_violado_real
        FROM gold.fct_risco_ola
        ORDER BY score_risco_ola DESC
    """

    return pd.read_sql(
        query,
        engine
    )