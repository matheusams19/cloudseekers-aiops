# ☁️ CloudSeekers

### Previsão Inteligente de Incidentes e Gestão Proativa de OLA

Projeto desenvolvido para o **Enterprise Challenge FIAP + Locaweb 2026**.

O **CloudSeekers** é uma solução de AIOps que transforma dados históricos de incidentes em inteligência preditiva para apoiar equipes de operações de TI.

A solução prevê o volume de incidentes **P2 e P3 nos horizontes D+1 e D+7**, calcula o **risco de violação de OLA por incidente** e disponibiliza os resultados em uma aplicação web desenvolvida em **Streamlit**.

---

## 🎯 Objetivo

Apoiar equipes de **NOC, SRE e operações de infraestrutura** na antecipação de cenários críticos.

O CloudSeekers busca:

- prever o volume de incidentes P2 e P3;
- antecipar comportamento para D+1 e D+7;
- calcular um score de risco de violação de OLA;
- classificar incidentes por nível de risco;
- facilitar a priorização operacional;
- transformar dados históricos em apoio à tomada de decisão.

---

## 🚨 Problema

Em operações de TI de grande escala, o volume de incidentes pode variar significativamente ao longo do tempo.

Picos inesperados podem aumentar a carga das equipes operacionais e elevar o risco de descumprimento dos acordos de nível operacional.

Em uma operação predominantemente reativa, esse cenário costuma ser percebido somente quando o impacto já está acontecendo.

O CloudSeekers propõe uma abordagem preditiva:

> **antecipar → identificar risco → priorizar → agir**

---

## 💡 Solução

A solução é baseada em três pilares principais:

### 1. Forecast de Incidentes

Previsão do volume de incidentes P2 e P3 para os próximos dias.

Horizontes utilizados:

- D+1
- D+2
- D+3
- D+4
- D+5
- D+6
- D+7

### 2. Risco de OLA

Cada incidente recebe um **score probabilístico de risco**, permitindo identificar quais chamados possuem maior probabilidade de violação do OLA.

Os resultados são classificados em níveis operacionais de risco.

### 3. Priorização Operacional

A aplicação permite visualizar os incidentes de maior risco e aplicar filtros por características como prioridade e categoria, apoiando a tomada de decisão da operação.

---

## 🏗️ Arquitetura

O CloudSeekers utiliza uma arquitetura em camadas:

```text
Dados históricos
      ↓
Bronze
      ↓
ETL / Python / Pandas
      ↓
Silver
      ↓
Feature Engineering
      ↓
Machine Learning
      ├── Forecast P2/P3
      └── Risco de OLA
      ↓
Gold
      ↓
Azure SQL Database
      ↓
Streamlit
      ↓
Decisão Operacional
