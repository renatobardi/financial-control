-- Onboarding (#60): marca por BD de que o roteiro já abriu sozinho e os passos opcionais dispensados.
-- Os BDs que já existem entram como "já abriu": o roteiro só abre sozinho em BD criado depois.

ALTER TABLE bd ADD COLUMN onboarding_aberto INTEGER NOT NULL DEFAULT 0;
UPDATE bd SET onboarding_aberto = 1;

CREATE TABLE onboarding_dispensa (
    bd_id INTEGER NOT NULL REFERENCES bd (id),
    passo TEXT NOT NULL,
    PRIMARY KEY (bd_id, passo)
);
