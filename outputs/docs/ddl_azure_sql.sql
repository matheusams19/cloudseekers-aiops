-- =========================================================
-- CloudSeekers - Camada GOLD - Azure SQL
-- Estrutura alinhada aos CSVs exportados pela v4
-- =========================================================

IF NOT EXISTS (
    SELECT 1
    FROM sys.schemas
    WHERE name = 'gold'
)
BEGIN
    EXEC('CREATE SCHEMA gold');
END;
GO

CREATE TABLE gold.fct_previsao_futura (
    id_previsao        INT IDENTITY(1,1) PRIMARY KEY,
    data_referencia    DATE          NOT NULL,
    data_previsao      DATE          NOT NULL,
    prioridade         VARCHAR(20)   NOT NULL,
    horizonte_dias     INT           NOT NULL,
    volume_previsto    DECIMAL(10,2) NOT NULL,
    modelo             VARCHAR(100)  NULL,
    data_carga         DATETIME2     DEFAULT SYSDATETIME()
);
GO

CREATE INDEX ix_previsao_data
ON gold.fct_previsao_futura (data_previsao, prioridade);
GO

CREATE TABLE gold.fct_risco_ola (
    id_risco            INT IDENTITY(1,1) PRIMARY KEY,
    numero_incidente    VARCHAR(30)   NOT NULL,
    aberto              DATETIME2     NULL,
    prioridade          VARCHAR(20)   NULL,
    produto             VARCHAR(255)  NULL,
    categoria           VARCHAR(255)  NULL,
    grupo_designado     VARCHAR(255)  NULL,
    score_risco_ola     DECIMAL(8,6)  NOT NULL,
    nivel_risco         VARCHAR(20)   NOT NULL,
    alerta_modelo       VARCHAR(3)    NULL,
    kpi_violado_real    VARCHAR(3)    NULL,
    data_carga          DATETIME2     DEFAULT SYSDATETIME()
);
GO

CREATE INDEX ix_risco_score
ON gold.fct_risco_ola (score_risco_ola DESC, prioridade);
GO