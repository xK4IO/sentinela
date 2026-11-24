"""Parâmetros centrais do Sentinela: gerador, regras, score e agente."""
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DB_PATH = ROOT / "data" / "youshop.db"
SCHEMA_PATH = ROOT / "db" / "schema.sql"
VIEWS_PATH = ROOT / "db" / "views.sql"
MODEL_PATH = ROOT / "detection" / "model.txt"

# --- Reprodutibilidade e LGPD -------------------------------------------------
SEED = 42
HASH_SALT = "sentinela-youshop-2027"
HASH_LEN = 16  # sha256 truncado (64 bits) para manter o .db pequeno

# --- Período simulado ---------------------------------------------------------
DATA_FIM = datetime(2026, 11, 22, 23, 59, 59)
DIAS_SIMULADOS = 90

# --- Volumes (seção 5.2) ------------------------------------------------------
N_PRODUTORES = 150
N_PRODUTOS = 600
N_CREATORS = 2000
N_FRAUDE_POR_TIPO = 20
N_VIRAIS = 30
N_COMPRADORES = 40000
N_COMPRADORES_RESERVADOS_FRAUDE = 1500  # contas "laranja" usadas pelos fraudadores

TIPOS_FRAUDE = [
    "F1_AUTOCOMPRA",
    "F2_REDE_PIX",
    "F3_COMPRA_ESTORNO",
    "F4_CLIQUE_INFLADO",
    "F5_CARTAO_TESTADO",
]
FRAUDE = tuple(TIPOS_FRAUDE)  # alvo do modelo: virais e NENHUMA são 0

# --- Comportamento legítimo ---------------------------------------------------
VENDAS_MEDIA_90D = 20          # média de vendas por creator no período (lognormal)
CONVERSAO_LEGIT = (0.06, 0.15)  # vendas / cliques
TAXA_REEMBOLSO_LEGIT = 0.04
TAXA_CHARGEBACK_LEGIT = 0.004
LIBERACAO_COMISSAO_DIAS = 2     # comissão liberada D+2 (correção 2 do plano)
GARANTIAS_DIAS = [7, 14, 30]
MEIOS_PAGAMENTO = {"CARTAO": 0.55, "PIX": 0.35, "BOLETO": 0.10}
INTERVALO_SAQUE_DIAS = (7, 15)
JANELA_SAQUE_PENDENTE_DIAS = 3  # saque pendente pedido nos últimos 3 dias

# --- Ruído plantado (correção 5): legítimos com sinais parciais ----------------
N_RUIDO_PIX_CASAL = 5          # pares de creators legítimos com a mesma Pix
N_RUIDO_FAMILIA_DISP = 12      # parentes comprando no mesmo celular (5%–18% das vendas)
N_RUIDO_CORPORATIVO = 6        # um comprador corporativo concentra muitas compras
FRAC_FRAUDE_DISCRETA = 0.2     # fração de cada tipo com sinal mais fraco

# --- Features -----------------------------------------------------------------
JANELA_FEATURES_DIAS = 30
MIN_COMPRADORES_CARTAO_REPETIDO = 3

# --- Regras (seção 6.1) — chutes iniciais, recalibrar no D2 --------------------
REGRAS = {
    "R1_AUTOCOMPRA":        {"feature": "pct_vendas_disp_creator",    "op": ">=", "limiar": 0.20, "pontos": 40, "critica": True},
    # recalibrado no D2: 1 → 2 (casal/família dividindo Pix é comum; rede = 3+ contas)
    "R2_PIX_COMPARTILHADA": {"feature": "qtd_creators_mesma_pix",     "op": ">=", "limiar": 2,    "pontos": 40, "critica": True},
    "R3_ESTORNO_POS_LIB":   {"feature": "taxa_estorno_pos_liberacao", "op": ">=", "limiar": 0.15, "pontos": 25, "critica": False},
    "R4_CLIQUE_RELAMPAGO":  {"feature": "mediana_seg_clique_compra",  "op": "<",  "limiar": 15,   "pontos": 20, "critica": False},
    "R5_CARTAO_REPETIDO":   {"feature": "qtd_cartoes_repetidos",      "op": ">=", "limiar": 1,    "pontos": 30, "critica": False},
    "R6_CHARGEBACK_ALTO":   {"feature": "taxa_chargeback",            "op": ">=", "limiar": 0.05, "pontos": 25, "critica": False},
    "R7_DISP_COMPARTILHADO": {"feature": "qtd_creators_mesmo_disp",   "op": ">=", "limiar": 2,    "pontos": 20, "critica": False},
}

# --- Score final (seção 6.3, recalibrado no D2 — ver docs/recalibracao.md) -----
# score_final = max(prob_modelo, PESO_MODELO*prob + PESO_REGRAS*score_regras)
PESO_MODELO = 0.6
PESO_REGRAS = 0.4
LIMIAR_ALTO = 0.50   # doc v0.1: 0.70
LIMIAR_MEDIO = 0.30  # doc v0.1: 0.40

# --- Agente -------------------------------------------------------------------
AGENTE_MAX_ITERACOES = 3
# Roteamento por complexidade: caso "claro" (modelo e regras concordam com força) vai direto
# para a redação, porque as consultas canônicas já são a prova. Na base atual: 62 claros
# (100% fraude) × 28 ambíguos (onde estão todos os falsos positivos) → investigação completa.
AGENTE_CLARO_PROB_MIN = 0.90
AGENTE_CLARO_REGRAS_MIN = 1
AGENTE_LIMIT_MAX = 200
# 2.5-flash foi aposentado para contas novas. Comparação no mesmo alerta (24/11):
# 3.5-flash-lite = 10 s/dossiê · 3.5-flash = 80 s/dossiê (acima da meta de 60 s). Ver docs/agente.md
GEMINI_MODEL = "gemini-3.5-flash-lite"  # sobrescrever com a variável de ambiente GEMINI_MODEL
PRAZO_RETENCAO_HORAS = 48
