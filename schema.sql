CREATE TABLE IF NOT EXISTS empresa (
    id_empresa   INTEGER PRIMARY KEY AUTOINCREMENT,
    razao_social TEXT NOT NULL,
    cnpj         TEXT NOT NULL UNIQUE,
    segmento     TEXT,
    porte        TEXT,
    cidade       TEXT,
    uf           TEXT
);

CREATE TABLE IF NOT EXISTS usuario (
    id_usuario INTEGER PRIMARY KEY AUTOINCREMENT,
    nome       TEXT NOT NULL,
    email      TEXT NOT NULL UNIQUE,
    senha_hash TEXT NOT NULL,
    perfil     TEXT NOT NULL DEFAULT 'consultor',
    ativo      INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS lead (
    id_lead      INTEGER PRIMARY KEY AUTOINCREMENT,
    id_empresa   INTEGER NOT NULL,
    id_usuario   INTEGER NOT NULL,
    nome_contato TEXT NOT NULL,
    cargo        TEXT,
    email        TEXT,
    telefone     TEXT,
    origem       TEXT NOT NULL,
    status       TEXT NOT NULL DEFAULT 'Novo',
    score        INTEGER NOT NULL DEFAULT 0,
    data_captura DATE NOT NULL,
    FOREIGN KEY (id_empresa) REFERENCES empresa (id_empresa),
    FOREIGN KEY (id_usuario) REFERENCES usuario (id_usuario),
    CHECK (status IN ('Novo', 'Contatado', 'Qualificado', 'Proposta', 'Ganho', 'Perdido'))
);

CREATE TABLE IF NOT EXISTS interacao (
    id_interacao  INTEGER PRIMARY KEY AUTOINCREMENT,
    id_lead       INTEGER NOT NULL,
    id_usuario    INTEGER NOT NULL,
    tipo          TEXT NOT NULL,
    data_hora     DATETIME NOT NULL,
    resumo        TEXT NOT NULL,
    proximo_passo TEXT,
    FOREIGN KEY (id_lead) REFERENCES lead (id_lead),
    FOREIGN KEY (id_usuario) REFERENCES usuario (id_usuario)
);

CREATE INDEX IF NOT EXISTS idx_lead_status ON lead (status);
CREATE INDEX IF NOT EXISTS idx_lead_origem ON lead (origem);
CREATE INDEX IF NOT EXISTS idx_lead_data   ON lead (data_captura);
