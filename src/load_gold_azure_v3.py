from pathlib import Path
import os
import sys
import struct

import pandas as pd
import pyodbc
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from azure.identity import InteractiveBrowserCredential

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = PROJECT_ROOT / ".env"

FORECAST_FILE = PROJECT_ROOT / "data" / "gold" / "forecast" / "fct_previsao_futura.csv"
RISK_FILE = PROJECT_ROOT / "data" / "gold" / "risco_ola" / "fct_risco_ola.csv"

SCHEMA = "gold"
FORECAST_TABLE = "fct_previsao_futura"
RISK_TABLE = "fct_risco_ola"

SQL_COPT_SS_ACCESS_TOKEN = 1256
TOKEN_SCOPE = "https://database.windows.net/.default"

FORECAST_COLUMNS = [
    "data_referencia",
    "data_previsao",
    "prioridade",
    "horizonte_dias",
    "volume_previsto",
    "modelo",
]

RISK_COLUMNS = [
    "numero_incidente",
    "aberto",
    "prioridade",
    "produto",
    "categoria",
    "grupo_designado",
    "score_risco_ola",
    "nivel_risco",
    "alerta_modelo",
    "kpi_violado_real",
]


def fail(message: str, code: int = 1):
    print(f"\nERRO: {message}")
    sys.exit(code)


def load_config():
    if not ENV_FILE.exists():
        fail(f"Arquivo .env não encontrado em: {ENV_FILE}")

    load_dotenv(ENV_FILE, override=True)

    cfg = {
        "server": os.getenv("AZURE_SQL_SERVER", "").strip(),
        "database": os.getenv("AZURE_SQL_DATABASE", "db-cloudseekers-gold").strip(),
        "user": os.getenv("AZURE_SQL_USER", "").strip(),
        "driver": os.getenv("AZURE_SQL_DRIVER", "ODBC Driver 18 for SQL Server").strip(),
    }

    if not cfg["server"]:
        fail("AZURE_SQL_SERVER está vazio no .env")

    if not cfg["database"]:
        fail("AZURE_SQL_DATABASE está vazio no .env")

    return cfg


def get_access_token(user_hint: str = ""):
    print("   Abrindo autenticação Microsoft Entra ID no navegador...")

    credential = InteractiveBrowserCredential(
        login_hint=user_hint or None,
        redirect_uri="http://localhost",
    )

    token = credential.get_token(TOKEN_SCOPE)

    token_bytes = token.token.encode("utf-16-le")
    token_struct = struct.pack(f"<I{len(token_bytes)}s", len(token_bytes), token_bytes)

    return token_struct


def build_engine():
    cfg = load_config()

    print(f"   Servidor: {cfg['server']}")
    print(f"   Banco:    {cfg['database']}")
    print(f"   Usuário:  {cfg['user'] if cfg['user'] else '(login será escolhido no navegador)'}")
    print("   Auth:     Microsoft Entra access token")

    token_struct = get_access_token(cfg["user"])

    connection_string = (
        f"DRIVER={{{cfg['driver']}}};"
        f"SERVER=tcp:{cfg['server']},1433;"
        f"DATABASE={cfg['database']};"
        "Encrypt=yes;"
        "TrustServerCertificate=no;"
        "Connection Timeout=30;"
    )

    def creator():
        return pyodbc.connect(
            connection_string,
            attrs_before={SQL_COPT_SS_ACCESS_TOKEN: token_struct},
        )

    return create_engine(
        "mssql+pyodbc://",
        creator=creator,
        pool_pre_ping=True,
    )


def validate_columns(df: pd.DataFrame, expected: list[str], name: str):
    missing = [c for c in expected if c not in df.columns]
    if missing:
        fail(f"{name}: colunas ausentes: {missing}")


def load_files():
    if not FORECAST_FILE.exists():
        fail(f"Gold Forecast não encontrada: {FORECAST_FILE}")

    if not RISK_FILE.exists():
        fail(f"Gold Risco OLA não encontrada: {RISK_FILE}")

    forecast = pd.read_csv(FORECAST_FILE)
    risk = pd.read_csv(RISK_FILE)

    validate_columns(forecast, FORECAST_COLUMNS, "Forecast")
    validate_columns(risk, RISK_COLUMNS, "Risco OLA")

    forecast = forecast[FORECAST_COLUMNS].copy()
    risk = risk[RISK_COLUMNS].copy()

    forecast["data_referencia"] = pd.to_datetime(
        forecast["data_referencia"], errors="raise"
    ).dt.date
    forecast["data_previsao"] = pd.to_datetime(
        forecast["data_previsao"], errors="raise"
    ).dt.date
    forecast["horizonte_dias"] = pd.to_numeric(
        forecast["horizonte_dias"], errors="raise"
    ).astype(int)
    forecast["volume_previsto"] = pd.to_numeric(
        forecast["volume_previsto"], errors="raise"
    )

    risk["aberto"] = pd.to_datetime(risk["aberto"], errors="coerce")
    risk["score_risco_ola"] = pd.to_numeric(
        risk["score_risco_ola"], errors="raise"
    )

    return forecast, risk


def main():
    print("=" * 58)
    print("CloudSeekers - Carga Gold para Azure SQL")
    print("=" * 58)

    print("\n1. Lendo arquivos Gold...")
    forecast, risk = load_files()
    print(f"   Forecast: {len(forecast):,} registros")
    print(f"   Risco OLA: {len(risk):,} registros")

    print("\n2. Autenticando e conectando ao Azure SQL...")
    try:
        engine = build_engine()
        with engine.connect() as conn:
            database = conn.execute(text("SELECT DB_NAME()")).scalar_one()
            print(f"   Conexão realizada com: {database}")
    except Exception as exc:
        fail(f"Falha na autenticação/conexão com Azure SQL:\n{exc}")

    print("\n3. Publicando camada Gold...")
    try:
        with engine.begin() as conn:
            conn.execute(text(f"DELETE FROM {SCHEMA}.{FORECAST_TABLE}"))
            conn.execute(text(f"DELETE FROM {SCHEMA}.{RISK_TABLE}"))

            forecast.to_sql(
                FORECAST_TABLE,
                con=conn,
                schema=SCHEMA,
                if_exists="append",
                index=False,
                chunksize=500,
            )

            risk.to_sql(
                RISK_TABLE,
                con=conn,
                schema=SCHEMA,
                if_exists="append",
                index=False,
                chunksize=1000,
            )

        print(f"   {len(forecast):,} previsões inseridas.")
        print(f"   {len(risk):,} scores de risco inseridos.")

    except Exception as exc:
        fail(
            "A carga falhou. A transação foi revertida; "
            f"os dados anteriores foram preservados.\n{exc}"
        )

    print("\n4. Validando carga...")
    try:
        with engine.connect() as conn:
            forecast_count = conn.execute(
                text(f"SELECT COUNT(*) FROM {SCHEMA}.{FORECAST_TABLE}")
            ).scalar_one()

            risk_count = conn.execute(
                text(f"SELECT COUNT(*) FROM {SCHEMA}.{RISK_TABLE}")
            ).scalar_one()

            top_risk = conn.execute(
                text(
                    f"""
                    SELECT TOP 1
                        numero_incidente,
                        prioridade,
                        score_risco_ola,
                        nivel_risco
                    FROM {SCHEMA}.{RISK_TABLE}
                    ORDER BY score_risco_ola DESC
                    """
                )
            ).mappings().first()

        print(f"   Azure Forecast: {forecast_count:,} registros")
        print(f"   Azure Risco OLA: {risk_count:,} registros")

        if top_risk:
            print(
                "   Maior score: "
                f"{top_risk['numero_incidente']} | "
                f"{top_risk['prioridade']} | "
                f"{float(top_risk['score_risco_ola']):.4f} | "
                f"{top_risk['nivel_risco']}"
            )

        if forecast_count != len(forecast) or risk_count != len(risk):
            fail("As contagens locais e do Azure não coincidem.")

    except Exception as exc:
        fail(f"Falha na validação da carga:\n{exc}")

    print("\n" + "=" * 58)
    print("Carga Gold concluída com sucesso.")
    print("=" * 58)


if __name__ == "__main__":
    main()
