-- A sessão guarda de onde veio (navegador e IP), para a tela de sessões ativas.
ALTER TABLE sessao ADD COLUMN agente TEXT;
ALTER TABLE sessao ADD COLUMN ip TEXT;
