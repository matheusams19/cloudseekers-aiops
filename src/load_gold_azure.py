from pathlib import Path
import os
import sys
from urllib.parse import quote_plus

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

# ============================================================
# CloudSeekers - Carga da camada Gold no Azure SQL
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = PROJECT_ROOT / ".env"

FORECAST_FILE = PROJECT_ROOT / "data" / "gold" / "forecast" / "fct_previsao_futura.csv"
RISK_FILE = PROJECT_ROOT / "data" / "gold" / "risco_ola" / "fct_risco_ola.csv"

FORECAST_TABLE = "fct_previsao_futura"
RISK_TABLE = "fct_risco_ola"
SCHEMA = "gold"

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


def validate_columns(df: pd.DataFrame, expected: list[str], name: str):
    missing = [c for c in expected if c not in df.columns]
    if missing:
        fail(f"{name}: colunas ausentes: {missing}")


def build_engine():
    load_dotenv(ENV_FILE)

    server = os.getenv("AZURE_SQL_SERVER")
    database = os.getenv("AZURE_SQL_DATABASE", "db-cloudseekers-gold")
    user = os.getenv("AZURE_SQL_USER")
    driver = os.getenv("AZURE_SQL_DRIVER", "ODBC Driver 18 for SQL Server")
    auth = os.getenv("AZURE_SQL_AUTH", "ActiveDirectoryInteractive")

    if not server:
        fail(
            "AZURE_SQL_SERVER não definido. "
            "Crie o arquivo .env na raiz do projeto."
        )

    connection_string = (
        f"DRIVER={{{driver}}};"
        f"SERVER=tcp:{server},1433;"
        f"DATABASE={database};"
        f"Authentication={auth};"
        "Encrypt=yes;"
        "TrustServerCertificate=no;"
        "Connection Timeout=30;"
    )

    return create_engine(
        "mssql+pyodbc:///?odbc_connect=" + quote_plus(connection_string),
        fast_executemany=True,
        pool_pre_ping=True,
    )


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

    print("\n2. Conectando ao Azure SQL...")
    engine = build_engine()

    try:
        with engine.connect() as conn:
            database = conn.execute(text("SELECT DB_NAME()")).scalar_one()
            print(f"   Conexão realizada com: {database}")
    except Exception as exc:
        fail(f"Falha na conexão com Azure SQL:\n{exc}")

    print("\n3. Publicando camada Gold...")
    try:
        # O processo é idempotente para o MVP:
        # limpa os snapshots anteriores e publica os resultados atuais.
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
                method=None,
            )

            risk.to_sql(
                RISK_TABLE,
                con=conn,
                schema=SCHEMA,
                if_exists="append",
                index=False,
                chunksize=1000,
                method=None,
            )

        print(f"   {len(forecast):,} previsões inseridas.")
        print(f"   {len(risk):,} scores de risco inseridos.")

    except Exception as exc:
        fail(
            "A carga falhou. A transação foi revertida; "
            f"os dados anteriores foram preservados.\n{exc}"
        )

    print("\n4. Validando carga...")
    with engine.connect() as conn:
        forecast_count = conn.execute(
            text(f"SELECT COUNT(*) FROM {SCHEMA}.{FORECAST_TABLE}")
        ).scalar_one()

        risk_count = conn.execute(
            text(f"SELECT COUNT(*) FROM {SCHEMA}.{RISK_TABLE}")
        ).scalar_one()

        max_risk = conn.execute(
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

    if max_risk:
        print(
            "   Maior score: "
            f"{max_risk['numero_incidente']} | "
            f"{max_risk['prioridade']} | "
            f"{float(max_risk['score_risco_ola']):.4f} | "
            f"{max_risk['nivel_risco']}"
        )

    if forecast_count != len(forecast) or risk_count != len(risk):
        fail("As contagens locais e do Azure não coincidem.")

    print("\n" + "=" * 58)
    print("Carga Gold concluída com sucesso.")
    print("=" * 58)


if __name__ == "__main__":
    main()
