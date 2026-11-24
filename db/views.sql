-- Views expostas ao agente investigador. Sem gabarito, sem nomes, sem cpf.

CREATE VIEW vw_creators AS
SELECT creator_id, pix_hash, canal_principal, criado_em
FROM creators;

CREATE VIEW vw_vendas AS
SELECT v.venda_id, l.creator_id, v.link_id, l.produto_id, p.tipo AS produto_tipo,
       p.garantia_dias, p.comissao_pct, v.comprador_id, v.ts, v.valor, v.meio_pagamento,
       v.cartao_hash, v.dispositivo_hash, v.ip_hash, v.status, v.status_atualizado_em
FROM vendas v
JOIN links l    ON l.link_id = v.link_id
JOIN produtos p ON p.produto_id = l.produto_id;

CREATE VIEW vw_comissoes AS
SELECT c.comissao_id, c.venda_id, c.creator_id, c.valor, c.status, c.liberada_em,
       v.status AS venda_status, v.status_atualizado_em AS venda_status_atualizado_em
FROM comissoes c
JOIN vendas v ON v.venda_id = c.venda_id;

CREATE VIEW vw_saques AS
SELECT saque_id, creator_id, valor, pix_hash, solicitado_em, status
FROM saques;

CREATE VIEW vw_logins AS
SELECT login_id, creator_id, dispositivo_hash, ip_hash, ts
FROM logins_creator;

CREATE VIEW vw_cliques AS
SELECT k.clique_id, l.creator_id, k.link_id, k.ts, k.ip_hash, k.dispositivo_hash
FROM cliques k
JOIN links l ON l.link_id = k.link_id;
