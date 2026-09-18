from pathlib import Path
import os
import struct

import pandas as pd
import pyodbc
import streamlit as st

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL
from azure.identity import InteractiveBrowserCredential


# =========================================================
# CONFIGURAÇÃO LOCAL
# =========================================================

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = PROJECT_ROOT / ".env"

load_dotenv(ENV_FILE, override=True)

LOCAL_SERVER = os.getenv("AZURE_SQL_SERVER")
LOCAL_DATABASE = os.getenv("AZURE_SQL_DATABASE")
LOCAL_USER = os.getenv("AZURE_SQL_USER")
LOCAL_DRIVER = os.getenv(
    "AZURE_SQL_DRIVER",
    "ODBC Driver 18 for SQL Server"
)

TOKEN_SCOPE = "https://database.windows.net/.default"
SQL_COPT_SS_ACCESS_TOKEN = 1256


# =========================================================
# DETECTAR AMBIENTE
# =========================================================

def em_producao():
    """
    Retorna True quando as credenciais do Streamlit Cloud
    estiverem configuradas em st.secrets.
    """
    try:
        return "azure_sql" in st.secrets
    except Exception:
        return False


# =========================================================
# PRODUÇÃO - STREAMLIT CLOUD
# =========================================================

@st.cache_resource
def get_engine_producao():

    cfg = st.secrets["azure_sql"]

    server = cfg["server"]
    database = cfg["database"]
    user = cfg["user"]
    password = cfg["password"]

    url = URL.create(
        "mssql+pymssql",
        username=user,
        password=password,
        host=server,
        port=1433,
        database=database,
    )

    return create_engine(
        url,
        pool_pre_ping=True,
        pool_recycle=300,
    )


# =========================================================
# LOCAL - MICROSOFT ENTRA
# =========================================================

@st.cache_resource
def get_credential():

    return InteractiveBrowserCredential(
        login_hint=LOCAL_USER or None
    )


def create_local_connection():

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
        f"DRIVER={{{LOCAL_DRIVER}}};"
        f"SERVER={LOCAL_SERVER};"
        f"DATABASE={LOCAL_DATABASE};"
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


@st.cache_resource
def get_engine_local():

    return create_engine(
        "mssql+pyodbc://",
        creator=create_local_connection,
        pool_pre_ping=True,
    )


# =========================================================
# ENGINE AUTOMÁTICO
# =========================================================

def get_engine():

    if em_producao():
        return get_engine_producao()

    return get_engine_local()


# =========================================================
# TESTE DO BANCO
# =========================================================

def get_database_name():

    engine = get_engine()

    with engine.connect() as conn:

        return conn.execute(
            text("SELECT DB_NAME()")
        ).scalar_one()


# =========================================================
# GOLD - FORECAST
# =========================================================

@st.cache_data(ttl=300)
def carregar_forecast():

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
        get_engine()
    )


# =========================================================
# GOLD - RISCO OLA
# =========================================================

@st.cache_data(ttl=300)
def carregar_risco_ola():

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
        get_engine()
    )