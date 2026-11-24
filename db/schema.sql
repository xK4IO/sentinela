-- Sentinela · schema do protótipo (SQLite)
-- Dados pessoais só como hash (sha256 + salt, truncado). Timestamps em ISO 8601 'YYYY-MM-DD HH:MM:SS'.

PRAGMA foreign_keys = ON;

CREATE TABLE produtores (
    produtor_id  TEXT PRIMARY KEY,
    nome         TEXT NOT NULL,
    categoria    TEXT NOT NULL,
    criado_em    TEXT NOT NULL
);

CREATE TABLE produtos (
    produto_id     TEXT PRIMARY KEY,
    produtor_id    TEXT NOT NULL REFERENCES produtores(produtor_id),
    nome           TEXT NOT NULL,
    tipo           TEXT NOT NULL CHECK (tipo IN ('FISICO','DIGITAL')),
    preco          REAL NOT NULL,
    comissao_pct   REAL NOT NULL,
    garantia_dias  INTEGER NOT NULL
);

CREATE TABLE creators (
    creator_id       TEXT PRIMARY KEY,
    nome             TEXT NOT NULL,
    cpf_hash         TEXT NOT NULL,
    pix_hash         TEXT NOT NULL,
    canal_principal  TEXT NOT NULL,
    criado_em        TEXT NOT NULL
);

CREATE TABLE logins_creator (
    login_id          INTEGER PRIMARY KEY,
    creator_id        TEXT NOT NULL REFERENCES creators(creator_id),
    dispositivo_hash  TEXT NOT NULL,
    ip_hash           TEXT NOT NULL,
    ts                TEXT NOT NULL
);

CREATE TABLE links (
    link_id     TEXT PRIMARY KEY,
    creator_id  TEXT NOT NULL REFERENCES creators(creator_id),
    produto_id  TEXT NOT NULL REFERENCES produtos(produto_id),
    criado_em   TEXT NOT NULL
);

CREATE TABLE cliques (
    clique_id         INTEGER PRIMARY KEY,
    link_id           TEXT NOT NULL REFERENCES links(link_id),
    ts                TEXT NOT NULL,
    ip_hash           TEXT NOT NULL,
    dispositivo_hash  TEXT NOT NULL
);

CREATE TABLE compradores (
    comprador_id  TEXT PRIMARY KEY,
    cpf_hash      TEXT NOT NULL,
    email_hash    TEXT NOT NULL,
    criado_em     TEXT NOT NULL
);

CREATE TABLE vendas (
    venda_id              TEXT PRIMARY KEY,
    link_id               TEXT NOT NULL REFERENCES links(link_id),
    comprador_id          TEXT NOT NULL REFERENCES compradores(comprador_id),
    ts                    TEXT NOT NULL,
    valor                 REAL NOT NULL,
    meio_pagamento        TEXT NOT NULL CHECK (meio_pagamento IN ('CARTAO','PIX','BOLETO')),
    cartao_hash           TEXT,              -- NULL se Pix/boleto
    dispositivo_hash      TEXT NOT NULL,
    ip_hash               TEXT NOT NULL,
    status                TEXT NOT NULL CHECK (status IN ('APROVADA','REEMBOLSADA','CHARGEBACK')),
    status_atualizado_em  TEXT               -- correção 1: quando virou REEMBOLSADA/CHARGEBACK
);

CREATE TABLE comissoes (
    comissao_id  TEXT PRIMARY KEY,
    venda_id     TEXT NOT NULL UNIQUE REFERENCES vendas(venda_id),
    creator_id   TEXT NOT NULL REFERENCES creators(creator_id),
    valor        REAL NOT NULL,
    status       TEXT NOT NULL CHECK (status IN ('PENDENTE','LIBERADA','ESTORNADA')),
    liberada_em  TEXT              -- correção 2: venda.ts + LIBERACAO_COMISSAO_DIAS
);

CREATE TABLE saques (
    saque_id       TEXT PRIMARY KEY,
    creator_id     TEXT NOT NULL REFERENCES creators(creator_id),
    valor          REAL NOT NULL,
    pix_hash       TEXT NOT NULL,
    solicitado_em  TEXT NOT NULL,
    status         TEXT NOT NULL CHECK (status IN ('SOLICITADO','RETIDO','APROVADO','NEGADO'))
);

CREATE TABLE alertas (
    alerta_id          INTEGER PRIMARY KEY,
    creator_id         TEXT NOT NULL REFERENCES creators(creator_id),
    saque_id           TEXT NOT NULL REFERENCES saques(saque_id),
    score_regras       REAL NOT NULL,
    prob_modelo        REAL,
    score_final        REAL NOT NULL,
    faixa_risco        TEXT NOT NULL CHECK (faixa_risco IN ('BAIXO','MEDIO','ALTO')),
    regras_disparadas  TEXT NOT NULL,   -- JSON
    shap_top           TEXT,            -- JSON
    features           TEXT,            -- JSON (snapshot usado pelo agente e pela UI)
    criado_em          TEXT NOT NULL
);

CREATE TABLE dossies (
    dossie_id       INTEGER PRIMARY KEY,
    alerta_id       INTEGER NOT NULL REFERENCES alertas(alerta_id),
    texto_md        TEXT NOT NULL,
    evidencias      TEXT NOT NULL,   -- JSON
    sql_executadas  TEXT NOT NULL,   -- JSON
    confianca       TEXT NOT NULL CHECK (confianca IN ('BAIXA','MEDIA','ALTA')),
    recomendacao    TEXT NOT NULL CHECK (recomendacao IN ('LIBERAR','MANTER_RETIDO')),
    duracao_seg     REAL,
    detalhes        TEXT,            -- JSON: estrutura do dossiê, rede, flags, modelo LLM
    criado_em       TEXT NOT NULL
);

CREATE TABLE revisoes (
    revisao_id  INTEGER PRIMARY KEY,
    dossie_id   INTEGER REFERENCES dossies(dossie_id),
    alerta_id   INTEGER NOT NULL REFERENCES alertas(alerta_id),
    analista    TEXT NOT NULL,
    decisao     TEXT NOT NULL CHECK (decisao IN ('LIBERAR','NEGAR')),
    comentario  TEXT NOT NULL CHECK (length(trim(comentario)) > 0),
    ts          TEXT NOT NULL
);

-- Só treino e avaliação. Nunca exposto ao agente nem à UI do analista.
CREATE TABLE gabarito (
    creator_id   TEXT PRIMARY KEY REFERENCES creators(creator_id),
    fraude_tipo  TEXT NOT NULL CHECK (fraude_tipo IN ('NENHUMA','F1_AUTOCOMPRA','F2_REDE_PIX',
                   'F3_COMPRA_ESTORNO','F4_CLIQUE_INFLADO','F5_CARTAO_TESTADO','LEGITIMO_VIRAL')),
    observacao   TEXT              -- ex.: DISCRETA, RUIDO_PIX_CASAL, RUIDO_FAMILIA_DISP, RUIDO_CORPORATIVO
);

CREATE INDEX ix_logins_creator   ON logins_creator(creator_id);
CREATE INDEX ix_logins_disp      ON logins_creator(dispositivo_hash);
CREATE INDEX ix_links_creator    ON links(creator_id);
CREATE INDEX ix_cliques_link_ts  ON cliques(link_id, ts);
CREATE INDEX ix_vendas_link_ts   ON vendas(link_id, ts);
CREATE INDEX ix_vendas_disp      ON vendas(dispositivo_hash);
CREATE INDEX ix_vendas_cartao    ON vendas(cartao_hash);
CREATE INDEX ix_comissoes_creator ON comissoes(creator_id);
CREATE INDEX ix_saques_creator   ON saques(creator_id, solicitado_em);
CREATE INDEX ix_creators_pix     ON creators(pix_hash);
CREATE INDEX ix_alertas_creator  ON alertas(creator_id, criado_em);
