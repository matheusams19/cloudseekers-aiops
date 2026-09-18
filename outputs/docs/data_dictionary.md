# Dicionário de Dados — Camada Silver

Base tratada usada no pipeline de forecast P2/P3.

| Campo | Tipo | Descrição / regra |
|---|---|---|
| Número | string | Chave de negócio; duplicados removidos |
| Prioridade | string | Prioridade original padronizada |
| Prioridade_Cod | int | Código numérico derivado da prioridade |
| Prioridade_Label | string | Rótulo derivado da prioridade |
| Produto / Categoria / Subcategoria / Item de configuração | string | Nulos convertidos em Não informado |
| Aberto / Resolvido / Encerrado | datetime | Tipagem de marcos temporais |
| Duração | numérico | Campo oficial preservado; validado contra cálculo temporal |
| Duracao_Divergente_60s | bool | Flag de auditoria para diferença superior a 60s |
| Entrou para KPI? | SIM/NAO | Indicador oficial padronizado |
| KPI Violado? | SIM/NAO/null | Indicador oficial; nulo quando não entra no KPI |
| KPI_Violado_Bool | boolean | Versão booleana derivada |

## Evidências de qualidade
- Volume Bronze: 122,543
- Volume Silver: 122,543
- Registros removidos: 0
- Violações da regra KPI: 0
- Duração com correspondência exata: 99.59%
- Duração com diferença de até 60s: 99.78%
- Correlação da Duração com cálculo temporal: 0.998895