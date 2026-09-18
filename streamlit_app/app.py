from pathlib import Path
import unicodedata

import pandas as pd
import plotly.express as px
import streamlit as st

from db import (
    get_database_name,
    carregar_forecast,
    carregar_risco_ola,
)

# =========================================================
# CONFIGURAÇÃO GERAL
# =========================================================

st.set_page_config(
    page_title="CloudSeekers",
    page_icon="☁️",
    layout="wide",
    initial_sidebar_state="expanded",
)

BASE_DIR = Path(__file__).resolve().parent
LOGO = BASE_DIR / "assets" / "logo_cloudseekers.png"

# =========================================================
# IDENTIDADE VISUAL
# =========================================================

st.markdown(
    """
    <style>
    :root {
        --bg: #0b0f17;
        --panel: #111827;
        --panel-2: #151d2d;
        --border: #243044;
        --text: #f8fafc;
        --muted: #94a3b8;
    }

    .stApp {
        background:
            radial-gradient(circle at top right, rgba(139,92,246,.08), transparent 32%),
            radial-gradient(circle at top left, rgba(34,211,238,.05), transparent 28%),
            var(--bg);
    }

    .block-container {
        padding-top: 1.4rem;
        padding-bottom: 3rem;
        max-width: 1550px;
    }

    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #0f172a 0%, #111827 100%);
        border-right: 1px solid #1f2937;
    }

    [data-testid="stSidebar"] * {
        color: #e5e7eb;
    }

    h1, h2, h3 {
        color: var(--text);
    }

    [data-testid="stMetric"] {
        background: linear-gradient(145deg, var(--panel), var(--panel-2));
        border: 1px solid var(--border);
        padding: 18px 18px 14px 18px;
        border-radius: 16px;
        box-shadow: 0 10px 28px rgba(0,0,0,.20);
        min-height: 118px;
    }

    [data-testid="stMetricLabel"] {
        color: var(--muted);
        font-weight: 600;
    }

    [data-testid="stMetricValue"] {
        color: #ffffff;
        font-size: 2rem;
        font-weight: 800;
    }

    [data-testid="stDataFrame"] {
        border: 1px solid #1f2937;
        border-radius: 12px;
        overflow: hidden;
    }

    hr {
        border-color: #1f2937 !important;
        opacity: .8;
    }

    .cs-subtitle {
        color: #94a3b8;
        font-size: 15px;
        margin-top: -8px;
        margin-bottom: 8px;
    }

    .cs-kicker {
        display: inline-block;
        color: #c4b5fd;
        background: rgba(139,92,246,.12);
        border: 1px solid rgba(139,92,246,.24);
        border-radius: 999px;
        padding: 6px 10px;
        font-size: 12px;
        font-weight: 700;
        letter-spacing: .4px;
        margin-bottom: 8px;
    }

    .cs-card {
        background: linear-gradient(145deg, #111827, #151d2d);
        border: 1px solid #243044;
        border-radius: 16px;
        padding: 18px;
        box-shadow: 0 8px 24px rgba(0,0,0,.18);
    }

    .cs-card-title {
        color: #94a3b8;
        font-size: 12px;
        text-transform: uppercase;
        letter-spacing: .8px;
        margin-bottom: 8px;
        font-weight: 700;
    }

    .cs-card-value {
        color: #ffffff;
        font-size: 25px;
        font-weight: 800;
        line-height: 1.2;
    }

    .cs-card-text {
        color: #cbd5e1;
        font-size: 13px;
        line-height: 1.5;
        margin-top: 7px;
    }

    .cs-status-ok,
    .cs-status-warn {
        display: inline-block;
        border-radius: 999px;
        padding: 7px 11px;
        font-weight: 700;
        font-size: 12px;
    }

    .cs-status-ok {
        color: #86efac;
        background: rgba(34,197,94,.10);
        border: 1px solid rgba(34,197,94,.30);
    }

    .cs-status-warn {
        color: #fcd34d;
        background: rgba(245,158,11,.10);
        border: 1px solid rgba(245,158,11,.30);
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# =========================================================
# FUNÇÕES AUXILIARES
# =========================================================

def normalizar_texto(valor):
    if pd.isna(valor):
        return ""
    valor = str(valor).strip().lower()
    return "".join(
        c
        for c in unicodedata.normalize("NFD", valor)
        if unicodedata.category(c) != "Mn"
    )


def eh_sim(valor):
    return normalizar_texto(valor) in {"sim", "yes", "true", "1", "s"}


def formatar_numero(valor, casas=0):
    if pd.isna(valor):
        return "-"
    if casas == 0:
        return f"{valor:,.0f}".replace(",", ".")
    return f"{valor:,.{casas}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def preparar_dados(forecast, risco):
    forecast = forecast.copy()
    risco = risco.copy()

    forecast["data_previsao"] = pd.to_datetime(
        forecast["data_previsao"], errors="coerce"
    )
    forecast["data_referencia"] = pd.to_datetime(
        forecast["data_referencia"], errors="coerce"
    )
    forecast["volume_previsto"] = pd.to_numeric(
        forecast["volume_previsto"], errors="coerce"
    )
    forecast["horizonte_dias"] = pd.to_numeric(
        forecast["horizonte_dias"], errors="coerce"
    )

    risco["score_risco_ola"] = pd.to_numeric(
        risco["score_risco_ola"], errors="coerce"
    )
    risco["aberto"] = pd.to_datetime(
        risco["aberto"], errors="coerce"
    )

    return forecast, risco


def criar_recomendacao(forecast, risco):
    alertas_mask = risco["alerta_modelo"].apply(eh_sim)
    qtd_alertas = int(alertas_mask.sum())

    d1 = forecast.loc[
        forecast["horizonte_dias"] == 1, "volume_previsto"
    ].sum()

    if qtd_alertas > 0:
        risco_alertado = risco.loc[alertas_mask].copy()
        grupo = "-"

        if "grupo_designado" in risco_alertado.columns:
            modos = risco_alertado["grupo_designado"].dropna().mode()
            if not modos.empty:
                grupo = str(modos.iloc[0])

        texto_grupo = f", com atenção ao grupo {grupo}" if grupo != "-" else ""

        return (
            f"Foram identificados {qtd_alertas} incidentes sinalizados pelo modelo. "
            f"Priorize a triagem dos maiores scores de risco{texto_grupo}. "
            f"O forecast D+1 indica volume previsto de {formatar_numero(d1)} incidentes."
        )

    return (
        "Nenhum alerta foi sinalizado pelo modelo neste recorte. "
        "Mantenha o acompanhamento do forecast D+1/D+7 e revise os incidentes de maior score."
    )

# =========================================================
# CARREGAMENTO DOS DADOS
# =========================================================

try:
    banco = get_database_name()
    forecast = carregar_forecast()
    risco = carregar_risco_ola()
    forecast, risco = preparar_dados(forecast, risco)

except Exception as e:
    st.error("Não foi possível carregar os dados do Azure SQL.")
    st.exception(e)
    st.stop()

# =========================================================
# MÉTRICAS GERAIS
# =========================================================

d1 = forecast.loc[
    forecast["horizonte_dias"] == 1, "volume_previsto"
].sum()

d7 = forecast.loc[
    forecast["horizonte_dias"] == 7, "volume_previsto"
].sum()

p2_7d = forecast.loc[
    forecast["prioridade"].astype(str).str.upper() == "P2",
    "volume_previsto",
].sum()

p3_7d = forecast.loc[
    forecast["prioridade"].astype(str).str.upper() == "P3",
    "volume_previsto",
].sum()

alertas_mask = risco["alerta_modelo"].apply(eh_sim)
qtd_alertas = int(alertas_mask.sum())
status_operacional = "Atenção" if qtd_alertas > 0 else "Estável"

# =========================================================
# SIDEBAR
# =========================================================

with st.sidebar:
    if LOGO.exists():
        st.image(str(LOGO), width=210)
    else:
        st.markdown("## ☁️ CloudSeekers")

    st.caption("Inteligência Preditiva para Operações de TI")
    st.divider()

    pagina = st.radio(
        "Navegação",
        [
            "📊 Visão Geral",
            "📈 Forecast",
            "⚠️ Risco de OLA",
            "🔎 Incidentes",
            "🧠 Modelos & Evidências",
        ],
        label_visibility="collapsed",
    )

    st.divider()
    st.caption("AMBIENTE")

    st.markdown(
        f"""
        <div class="cs-card">
            <div class="cs-card-title">Banco</div>
            <div class="cs-card-value" style="font-size:17px;">{banco}</div>
            <div class="cs-card-text">{len(forecast)} previsões • {len(risco)} incidentes</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.write("")

    if st.button("🔄 Atualizar dados", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

# =========================================================
# CABEÇALHO
# =========================================================

head_text, head_status = st.columns([8.2, 1.8])

with head_text:
    st.title("CloudSeekers")
    st.markdown(
        '<div class="cs-subtitle">Previsão Inteligente de Incidentes e Gestão Proativa de OLA</div>',
        unsafe_allow_html=True,
    )

with head_status:
    st.write("")
    st.write("")
    if status_operacional == "Atenção":
        st.markdown(
            '<span class="cs-status-warn">● Status: Atenção</span>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            '<span class="cs-status-ok">● Status: Estável</span>',
            unsafe_allow_html=True,
        )

st.divider()

# =========================================================
# PÁGINA 1 — VISÃO GERAL
# =========================================================

if pagina == "📊 Visão Geral":
    st.subheader("Visão Operacional Preditiva")
    st.caption("Forecast dos próximos dias e priorização de risco de OLA.")

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Forecast D+1", formatar_numero(d1))
    c2.metric("Forecast D+7", formatar_numero(d7))
    c3.metric("P2 • 7 dias", formatar_numero(p2_7d))
    c4.metric("P3 • 7 dias", formatar_numero(p3_7d))
    c5.metric("Alertas de risco", formatar_numero(qtd_alertas))

    st.write("")

    esquerda, direita = st.columns([1.65, 1])

    with esquerda:
        st.markdown("### Forecast diário")

        fig_forecast = px.line(
            forecast,
            x="data_previsao",
            y="volume_previsto",
            color="prioridade",
            markers=True,
            labels={
                "data_previsao": "Data",
                "volume_previsto": "Volume previsto",
                "prioridade": "Prioridade",
            },
        )

        fig_forecast.update_layout(
            template="plotly_dark",
            height=420,
            margin=dict(l=20, r=20, t=30, b=20),
            paper_bgcolor="#0b0f17",
            plot_bgcolor="#111827",
            legend_title_text="",
            hovermode="x unified",
        )

        st.plotly_chart(fig_forecast, use_container_width=True)

    with direita:
        st.markdown("### Distribuição de risco")

        distribuicao = (
            risco["nivel_risco"]
            .fillna("Não informado")
            .value_counts()
            .rename_axis("nivel_risco")
            .reset_index(name="quantidade")
        )

        fig_risco = px.pie(
            distribuicao,
            names="nivel_risco",
            values="quantidade",
            hole=0.67,
        )

        fig_risco.update_layout(
            template="plotly_dark",
            height=420,
            margin=dict(l=20, r=20, t=30, b=20),
            paper_bgcolor="#0b0f17",
            legend_title_text="",
        )

        fig_risco.update_traces(
            textposition="inside",
            textinfo="percent",
            hovertemplate="<b>%{label}</b><br>%{value} incidentes<br>%{percent}<extra></extra>",
        )

        st.plotly_chart(fig_risco, use_container_width=True)

    st.markdown("### Recomendação operacional")
    recomendacao = criar_recomendacao(forecast, risco)

    st.markdown(
        f"""
        <div class="cs-card">
            <div class="cs-card-title">Leitura do modelo</div>
            <div class="cs-card-text" style="font-size:15px;">{recomendacao}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.write("")
    st.markdown("### Incidentes prioritários")

    colunas_top = [
        c for c in [
            "numero_incidente",
            "prioridade",
            "produto",
            "categoria",
            "grupo_designado",
            "score_risco_ola",
            "nivel_risco",
            "alerta_modelo",
        ]
        if c in risco.columns
    ]

    top_risco = (
        risco.sort_values("score_risco_ola", ascending=False)
        .head(12)
        .loc[:, colunas_top]
    )

    st.dataframe(
        top_risco,
        use_container_width=True,
        hide_index=True,
        height=430,
        column_config={
            "score_risco_ola": st.column_config.ProgressColumn(
                "Score de risco",
                min_value=0.0,
                max_value=1.0,
                format="%.3f",
            )
        },
    )

# =========================================================
# PÁGINA 2 — FORECAST
# =========================================================

elif pagina == "📈 Forecast":
    st.subheader("Forecast D+1 a D+7")
    st.caption("Previsão de volume para incidentes P2 e P3.")

    prioridades = sorted(
        forecast["prioridade"].dropna().astype(str).unique().tolist()
    )

    filtro_prioridade = st.multiselect(
        "Prioridade",
        prioridades,
        default=prioridades,
    )

    forecast_filtrado = forecast[
        forecast["prioridade"].astype(str).isin(filtro_prioridade)
    ].copy()

    f1, f2, f3 = st.columns(3)
    f1.metric("Registros", len(forecast_filtrado))
    f2.metric(
        "Volume previsto",
        formatar_numero(forecast_filtrado["volume_previsto"].sum()),
    )
    f3.metric(
        "Média diária",
        formatar_numero(forecast_filtrado["volume_previsto"].mean(), 1),
    )

    fig = px.bar(
        forecast_filtrado,
        x="data_previsao",
        y="volume_previsto",
        color="prioridade",
        barmode="group",
        hover_data=["horizonte_dias", "modelo"],
        labels={
            "data_previsao": "Data",
            "volume_previsto": "Volume previsto",
            "prioridade": "Prioridade",
            "horizonte_dias": "Horizonte",
            "modelo": "Modelo",
        },
    )

    fig.update_layout(
        template="plotly_dark",
        height=500,
        paper_bgcolor="#0b0f17",
        plot_bgcolor="#111827",
        legend_title_text="",
        margin=dict(l=20, r=20, t=30, b=20),
    )

    st.plotly_chart(fig, use_container_width=True)

    st.markdown("### Detalhamento")
    st.dataframe(
        forecast_filtrado,
        use_container_width=True,
        hide_index=True,
    )

# =========================================================
# PÁGINA 3 — RISCO DE OLA
# =========================================================

elif pagina == "⚠️ Risco de OLA":
    st.subheader("Risco de Violação de OLA")
    st.caption("Priorização dos incidentes a partir do score probabilístico do modelo.")

    col1, col2, col3 = st.columns(3)

    prioridades_risco = sorted(
        risco["prioridade"].dropna().astype(str).unique().tolist()
    )
    niveis_risco = sorted(
        risco["nivel_risco"].dropna().astype(str).unique().tolist()
    )
    grupos = sorted(
        risco["grupo_designado"].dropna().astype(str).unique().tolist()
    )

    with col1:
        filtro_prioridade = st.multiselect(
            "Prioridade",
            prioridades_risco,
            default=prioridades_risco,
        )

    with col2:
        filtro_nivel = st.multiselect(
            "Nível de risco",
            niveis_risco,
            default=niveis_risco,
        )

    with col3:
        filtro_grupo = st.multiselect(
            "Grupo designado",
            grupos,
        )

    risco_filtrado = risco[
        risco["prioridade"].astype(str).isin(filtro_prioridade)
        & risco["nivel_risco"].astype(str).isin(filtro_nivel)
    ].copy()

    if filtro_grupo:
        risco_filtrado = risco_filtrado[
            risco_filtrado["grupo_designado"].astype(str).isin(filtro_grupo)
        ]

    r1, r2, r3, r4 = st.columns(4)

    r1.metric("Incidentes", len(risco_filtrado))
    r2.metric(
        "Score médio",
        f"{risco_filtrado['score_risco_ola'].mean():.1%}"
        if not risco_filtrado.empty
        else "0%",
    )
    r3.metric(
        "Maior score",
        f"{risco_filtrado['score_risco_ola'].max():.1%}"
        if not risco_filtrado.empty
        else "0%",
    )
    r4.metric(
        "Alertas",
        int(risco_filtrado["alerta_modelo"].apply(eh_sim).sum())
        if not risco_filtrado.empty
        else 0,
    )

    g1, g2 = st.columns([1, 1.4])

    with g1:
        dist = (
            risco_filtrado["nivel_risco"]
            .fillna("Não informado")
            .value_counts()
            .rename_axis("nivel_risco")
            .reset_index(name="quantidade")
        )

        fig_dist = px.bar(
            dist,
            x="nivel_risco",
            y="quantidade",
            labels={
                "nivel_risco": "Nível de risco",
                "quantidade": "Incidentes",
            },
        )

        fig_dist.update_layout(
            template="plotly_dark",
            height=420,
            paper_bgcolor="#0b0f17",
            plot_bgcolor="#111827",
            margin=dict(l=20, r=20, t=30, b=20),
        )

        st.plotly_chart(fig_dist, use_container_width=True)

    with g2:
        top_grupo = (
            risco_filtrado.groupby("grupo_designado", dropna=False)
            .agg(
                incidentes=("numero_incidente", "count"),
                score_medio=("score_risco_ola", "mean"),
            )
            .reset_index()
            .sort_values(["score_medio", "incidentes"], ascending=False)
            .head(10)
        )

        fig_grupos = px.bar(
            top_grupo,
            x="score_medio",
            y="grupo_designado",
            orientation="h",
            hover_data=["incidentes"],
            labels={
                "score_medio": "Score médio",
                "grupo_designado": "Grupo",
                "incidentes": "Incidentes",
            },
        )

        fig_grupos.update_layout(
            template="plotly_dark",
            height=420,
            paper_bgcolor="#0b0f17",
            plot_bgcolor="#111827",
            margin=dict(l=20, r=20, t=30, b=20),
            yaxis={"categoryorder": "total ascending"},
        )

        st.plotly_chart(fig_grupos, use_container_width=True)

    st.markdown("### Incidentes por risco")
    st.dataframe(
        risco_filtrado.sort_values("score_risco_ola", ascending=False),
        use_container_width=True,
        hide_index=True,
        height=540,
        column_config={
            "score_risco_ola": st.column_config.ProgressColumn(
                "Score de risco",
                min_value=0.0,
                max_value=1.0,
                format="%.3f",
            )
        },
    )

# =========================================================
# PÁGINA 4 — INCIDENTES
# =========================================================

elif pagina == "🔎 Incidentes":
    st.subheader("Explorador de Incidentes")
    st.caption("Consulta operacional dos incidentes avaliados pelo modelo.")

    q1, q2, q3 = st.columns(3)

    categorias = sorted(
        risco["categoria"].dropna().astype(str).unique().tolist()
    )
    produtos = sorted(
        risco["produto"].dropna().astype(str).unique().tolist()
    )
    prioridades = sorted(
        risco["prioridade"].dropna().astype(str).unique().tolist()
    )

    with q1:
        filtro_categoria = st.multiselect("Categoria", categorias)

    with q2:
        filtro_produto = st.multiselect("Produto", produtos)

    with q3:
        filtro_prioridade = st.multiselect("Prioridade", prioridades)

    dados = risco.copy()

    if filtro_categoria:
        dados = dados[dados["categoria"].astype(str).isin(filtro_categoria)]

    if filtro_produto:
        dados = dados[dados["produto"].astype(str).isin(filtro_produto)]

    if filtro_prioridade:
        dados = dados[dados["prioridade"].astype(str).isin(filtro_prioridade)]

    dados = dados.sort_values("score_risco_ola", ascending=False)

    st.caption(f"{len(dados):,} registros encontrados".replace(",", "."))

    st.dataframe(
        dados,
        use_container_width=True,
        hide_index=True,
        height=650,
        column_config={
            "score_risco_ola": st.column_config.ProgressColumn(
                "Score de risco",
                min_value=0.0,
                max_value=1.0,
                format="%.3f",
            )
        },
    )

# =========================================================
# PÁGINA 5 — MODELOS & EVIDÊNCIAS
# =========================================================

elif pagina == "🧠 Modelos & Evidências":
    st.subheader("Modelos & Evidências do MVP")
    st.caption("Visão técnica resumida da solução implementada.")

    e1, e2, e3 = st.columns(3)
    e1.metric("Previsões Gold", len(forecast))
    e2.metric("Scores Gold", len(risco))
    e3.metric("Banco", "Azure SQL")

    st.markdown(
        """
        <div class="cs-card">
            <div class="cs-card-title">Pipeline implementado</div>
            <div class="cs-card-text" style="font-size:15px;">
                Dataset histórico → tratamento e feature engineering →
                Forecast D+1/D+7 + Risco de OLA →
                Camada Gold → Azure SQL → Streamlit.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.write("")
    st.markdown("### Modelos utilizados no Forecast")

    modelos = (
        forecast[["prioridade", "modelo"]]
        .drop_duplicates()
        .sort_values("prioridade")
    )

    st.dataframe(
        modelos,
        use_container_width=True,
        hide_index=True,
    )

    st.markdown("### Informações do modelo de risco")
    st.write(
        "Cada incidente recebe um score probabilístico de risco de violação de OLA. "
        "O score é usado para classificação operacional e priorização dos casos de maior risco."
    )

    if "kpi_violado_real" in risco.columns:
        distribuicao_kpi = (
            risco["kpi_violado_real"]
            .fillna("Não informado")
            .value_counts()
            .rename_axis("KPI violado")
            .reset_index(name="quantidade")
        )

        st.dataframe(
            distribuicao_kpi,
            use_container_width=True,
            hide_index=True,
        )