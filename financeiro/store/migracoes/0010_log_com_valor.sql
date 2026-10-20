-- O log do fechamento passa a guardar o valor congelado no ato de fechar.
ALTER TABLE fechamento_log ADD COLUMN valor_centavos BIGINT;
