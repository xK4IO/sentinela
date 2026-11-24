"""Testes das features com uma base mínima em memória (não depende do youshop.db)."""
import math
import sqlite3

import pandas as pd
import pytest

import config as C
from detection.features import calcular_features


@pytest.fixture
def con():
    c = sqlite3.connect(":memory:")
    c.executescript(C.SCHEMA_PATH.read_text(encoding="utf-8"))
    c.executescript("""
        INSERT INTO produtores VALUES ('P1','Prod','Beleza','2025-01-01 00:00:00');
        INSERT INTO produtos VALUES ('PR1','P1','Batom','FISICO',100,0.1,30);
        INSERT INTO compradores VALUES ('B1','x','y','2025-01-01 00:00:00'),('B2','x2','y2','2025-01-01 00:00:00');
        -- CA: creator ativo, CN: creator novo sem vendas (UC04)
        INSERT INTO creators VALUES ('CA','Ana','c1','pixA','TikTok','2026-01-01 00:00:00'),
                                    ('CN','Nina','c2','pixN','TikTok','2026-11-19 00:00:00');
        INSERT INTO logins_creator (creator_id, dispositivo_hash, ip_hash, ts)
            VALUES ('CA','dispA','ipA','2026-11-01 10:00:00');
        INSERT INTO links VALUES ('LA','CA','PR1','2026-01-02 00:00:00');
        -- V1: autocompra (dispositivo do login); V2: chargeback que só chega DEPOIS do saque
        INSERT INTO vendas VALUES
          ('V1','LA','B1','2026-11-10 10:00:00',100,'PIX',NULL,'dispA','ipA','APROVADA',NULL),
          ('V2','LA','B2','2026-11-12 10:00:00',100,'CARTAO','k1','dispB','ipB','CHARGEBACK','2026-11-30 00:00:00');
        INSERT INTO cliques (link_id, ts, ip_hash, dispositivo_hash) VALUES
          ('LA','2026-11-10 09:59:50','ipA','dispA'), ('LA','2026-11-12 09:59:00','ipB','dispB');
        INSERT INTO comissoes VALUES ('K1','V1','CA',10,'LIBERADA','2026-11-12 10:00:00'),
                                     ('K2','V2','CA',10,'LIBERADA','2026-11-14 10:00:00');
    """)
    yield c
    c.close()


def feats(con):
    saques = pd.DataFrame({"saque_id": ["S1", "S2"], "creator_id": ["CA", "CN"],
                           "solicitado_em": pd.to_datetime(["2026-11-20 12:00:00", "2026-11-22 12:00:00"])})
    return calcular_features(con, saques)


def test_autocompra_e_clique(con):
    f = feats(con).loc["S1"]
    assert f.qtd_vendas == 2
    assert f.pct_vendas_disp_creator == 0.5
    assert f.mediana_seg_clique_compra == (10 + 60) / 2
    assert f.conversao == 1.0


def test_sem_vazamento_do_futuro(con):
    # o chargeback de V2 acontece em 30/11, depois do saque de 20/11 → ainda não é conhecido
    assert feats(con).loc["S1"].taxa_chargeback == 0.0


def test_creator_sem_vendas_tem_taxas_nulas(con):  # UC04
    f = feats(con).loc["S2"]
    assert f.qtd_vendas == 0
    assert math.isnan(f.taxa_reembolso) and math.isnan(f.pct_vendas_disp_creator)
    assert math.isnan(f.crescimento_vendas_7d)  # conta com menos de 7 dias
