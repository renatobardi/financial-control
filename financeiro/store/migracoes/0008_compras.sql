-- Histórico de cada ordem de compra (quem mudou o quê e quando).

CREATE TABLE compra_historico (
    id         INTEGER PRIMARY KEY,
    bd_id      INTEGER NOT NULL REFERENCES bd (id),
    compra_id  INTEGER NOT NULL,
    em         TEXT NOT NULL,
    usuario_id INTEGER NOT NULL REFERENCES usuario (id),
    texto      TEXT NOT NULL,
    FOREIGN KEY (bd_id, compra_id) REFERENCES compra (bd_id, id)
);
