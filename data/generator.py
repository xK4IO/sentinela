"""Gera data/youshop.db com dados sintéticos, fraudes plantadas e gabarito.

Uso (na raiz do projeto):  python -m data.generator

Camadas:
  1. base legítima (produtores, produtos, creators, compradores, links, logins, vendas, cliques)
  2. injetores de fraude F1–F5 (uma função por tipo)
  3. creators virais legítimos (teste de falso positivo)
  4. ruído: legítimos com sinais parciais (Pix de casal, família no mesmo celular, compra corporativa)
  5. comissões (liberação D+2) e saques (histórico APROVADO + um saque SOLICITADO por creator)
"""
from __future__ import annotations

import hashlib
import sqlite3
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
from faker import Faker

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config as C  # noqa: E402

FMT = "%Y-%m-%d %H:%M:%S"
FIM = C.DATA_FIM
INICIO = FIM - timedelta(days=C.DIAS_SIMULADOS)
LIB = timedelta(days=C.LIBERACAO_COMISSAO_DIAS)

CATEGORIAS = ["Beleza", "Moda", "Educação", "Fitness", "Finanças", "Casa",
              "Tecnologia", "Games", "Culinária", "Pets"]
CATEGORIAS_DIGITAIS = {"Educação", "Finanças"}
CANAIS = ["Instagram", "TikTok", "YouTube", "Kwai", "WhatsApp", "Blog"]


def h(*parts) -> str:
    """Hash de dado pessoal: sha256(salt|partes), truncado."""
    s = C.HASH_SALT + "|" + "|".join(map(str, parts))
    return hashlib.sha256(s.encode()).hexdigest()[: C.HASH_LEN]


def f(dt: datetime | None) -> str | None:
    return dt.strftime(FMT) if dt else None


@dataclass
class Creator:
    idx: int
    cid: str
    criado_em: datetime
    pix_hash: str
    devices: list[str]
    ips: list[str]
    n_legit: int
    links: list[tuple[str, int, datetime]] = field(default_factory=list)
    tipo: str = "NENHUMA"
    obs: str | None = None
    inativo_recente: bool = False
    saque_raro: bool = False
    especial: bool = False

    @property
    def inicio_atividade(self) -> datetime:
        return max(INICIO, self.criado_em + timedelta(days=1))


class Gerador:
    def __init__(self) -> None:
        self.rng = np.random.default_rng(C.SEED)
        self.fake = Faker("pt_BR")
        self.fake.seed_instance(C.SEED)
        self.produtores: list[tuple] = []
        self.produtos: list[dict] = []
        self.creators: list[Creator] = []
        self.vendas: list[dict] = []
        self.cliques: list[tuple] = []
        self.logins: list[tuple] = []
        self.saques: list[tuple] = []
        self.n_legit_buyers = C.N_COMPRADORES - C.N_COMPRADORES_RESERVADOS_FRAUDE

    # ------------------------------------------------------------------ util
    def dt_entre(self, a: datetime, b: datetime) -> datetime:
        seg = max(1.0, (b - a).total_seconds())
        return a + timedelta(seconds=float(self.rng.uniform(0, seg)))

    def escolha(self, seq):
        return seq[int(self.rng.integers(len(seq)))]

    def unif(self, a: float, b: float) -> float:
        return float(self.rng.uniform(a, b))

    def inteiro(self, a: int, b: int) -> int:
        """Inteiro em [a, b] (inclusivo)."""
        return int(self.rng.integers(a, b + 1))

    # ------------------------------------------------------- compradores
    def _init_compradores(self) -> None:
        n = C.N_COMPRADORES
        self.b_ndev = self.rng.integers(1, 3, size=n)
        self.b_nip = self.rng.integers(1, 3, size=n)
        self.b_ncard = self.rng.integers(1, 3, size=n)
        self.reservados = np.arange(self.n_legit_buyers, n)

    def bid(self, i: int) -> str:
        return f"B{i:05d}"

    def comprador_legit(self) -> int:
        return int(self.rng.integers(self.n_legit_buyers))

    def b_disp(self, i: int) -> str:
        return h("bdisp", i, int(self.rng.integers(self.b_ndev[i])))

    def b_ip(self, i: int) -> str:
        return h("bip", i, int(self.rng.integers(self.b_nip[i])))

    def b_cartao(self, i: int) -> str:
        return h("card", i, int(self.rng.integers(self.b_ncard[i])))

    def laranjas(self, k: int) -> list[int]:
        return [int(x) for x in self.rng.choice(self.reservados, size=k, replace=False)]

    def meio(self) -> str:
        meios = list(C.MEIOS_PAGAMENTO)
        return meios[int(self.rng.choice(len(meios), p=list(C.MEIOS_PAGAMENTO.values())))]

    # ------------------------------------------------------------ camada 1
    def gerar_catalogo(self) -> None:
        for i in range(C.N_PRODUTORES):
            cat = self.escolha(CATEGORIAS)
            criado = self.dt_entre(FIM - timedelta(days=1500), INICIO)
            self.produtores.append((f"P{i:04d}", self.fake.company(), cat, f(criado)))
        for i in range(C.N_PRODUTOS):
            pid, _, cat, _ = self.escolha(self.produtores)
            digital = cat in CATEGORIAS_DIGITAIS or self.rng.random() < 0.25
            if digital:
                preco = float(self.escolha([47, 97, 147, 197, 297, 497]))
                comissao = round(self.unif(0.30, 0.50), 2)
            else:
                preco = round(float(np.clip(self.rng.lognormal(np.log(110), 0.6), 25, 900)), 2)
                comissao = round(self.unif(0.08, 0.20), 2)
            self.produtos.append({
                "id": f"PR{i:04d}", "produtor_id": pid,
                "nome": f"{cat} {self.fake.word().capitalize()} {i}",
                "tipo": "DIGITAL" if digital else "FISICO", "preco": preco,
                "comissao_pct": comissao, "garantia_dias": int(self.escolha(C.GARANTIAS_DIAS)),
            })

    def gerar_creators(self) -> None:
        mu = np.log(C.VENDAS_MEDIA_90D) - 0.5
        for i in range(C.N_CREATORS):
            cid = f"C{i:04d}"
            if self.rng.random() < 0.85:
                criado = self.dt_entre(FIM - timedelta(days=730), INICIO - timedelta(days=1))
            else:
                criado = self.dt_entre(INICIO, FIM - timedelta(days=2))
            ativo_frac = min(1.0, (FIM - max(criado, INICIO)).days / C.DIAS_SIMULADOS)
            n = 0 if self.rng.random() < 0.12 else int(self.rng.lognormal(mu, 1.0) * ativo_frac)
            cr = Creator(
                idx=i, cid=cid, criado_em=criado, pix_hash=h("pix", cid),
                devices=[h("disp", cid, k) for k in range(self.inteiro(1, 3))],
                ips=[h("ip", cid, k) for k in range(self.inteiro(1, 4))],
                n_legit=n,
                inativo_recente=self.rng.random() < 0.08,
                saque_raro=self.rng.random() < 0.30,
            )
            link_base = max(criado, INICIO - timedelta(days=60))
            for p in self.rng.choice(C.N_PRODUTOS, size=self.inteiro(1, 6), replace=False):
                lc = link_base + timedelta(hours=self.unif(0, 12))
                cr.links.append((f"L{i:04d}{len(cr.links):02d}", int(p), lc))
            self.creators.append(cr)

    def gerar_logins(self) -> None:
        for cr in self.creators:
            inicio = max(INICIO, cr.criado_em)
            # garante que todo dispositivo (inclusive os compartilhados) aparece ao menos uma vez
            for d in cr.devices:
                self.logins.append((cr.cid, d, self.escolha(cr.ips), f(self.dt_entre(inicio, FIM))))
            pesos = np.array([3.0] + [1.0] * (len(cr.devices) - 1))
            pesos /= pesos.sum()
            for _ in range(self.inteiro(10, 80)):
                d = cr.devices[int(self.rng.choice(len(cr.devices), p=pesos))]
                self.logins.append((cr.cid, d, self.escolha(cr.ips), f(self.dt_entre(inicio, FIM))))

    def venda(self, cr: Creator, ts: datetime, *, link=None, comprador: int | None = None,
              meio: str | None = None, cartao: str | None = None, disp: str | None = None,
              ip: str | None = None, delay_clique: float | None = None,
              p_reembolso: float = C.TAXA_REEMBOLSO_LEGIT, reembolso_pos_lib: bool = False,
              p_chargeback: float = C.TAXA_CHARGEBACK_LEGIT,
              chargeback_dias: tuple[float, float] = (15, 60)) -> None:
        lid, pidx, _ = link or self.escolha(cr.links)
        prod = self.produtos[pidx]
        b = self.comprador_legit() if comprador is None else comprador
        meio = meio or self.meio()
        cartao = (cartao or self.b_cartao(b)) if meio == "CARTAO" else None
        disp = disp or self.b_disp(b)
        ip = ip or self.b_ip(b)
        garantia = prod["garantia_dias"]

        status, st_ts = "APROVADA", None
        delta = None
        if reembolso_pos_lib:
            delta = self.unif(C.LIBERACAO_COMISSAO_DIAS + 0.1, max(C.LIBERACAO_COMISSAO_DIAS + 0.3, garantia - 0.05))
        elif self.rng.random() < p_reembolso:
            delta = self.unif(0.05, garantia)
        if delta is not None and ts + timedelta(days=delta) <= FIM:
            status, st_ts = "REEMBOLSADA", ts + timedelta(days=delta)
        if status == "APROVADA" and meio == "CARTAO" and self.rng.random() < p_chargeback:
            cb = ts + timedelta(days=self.unif(*chargeback_dias))
            if cb <= FIM:
                status, st_ts = "CHARGEBACK", cb

        if delay_clique is None:
            if self.rng.random() < 0.03:  # comprador impulsivo legítimo
                delay_clique = self.unif(5, 15)
            else:
                delay_clique = float(np.clip(self.rng.lognormal(np.log(1200), 1.3), 20, 3 * 86400))
        self.cliques.append((lid, ts - timedelta(seconds=delay_clique), ip, disp))

        self.vendas.append({
            "link_id": lid, "comprador_id": self.bid(b), "ts": ts, "valor": prod["preco"],
            "meio": meio, "cartao": cartao, "disp": disp, "ip": ip, "status": status,
            "st_ts": st_ts, "creator_id": cr.cid, "comissao_pct": prod["comissao_pct"],
        })

    def gerar_vendas_legitimas(self) -> None:
        for cr in self.creators:
            ini = cr.inicio_atividade
            fim = FIM
            if cr.inativo_recente and not cr.especial and ini < FIM - timedelta(days=40):
                fim = FIM - timedelta(days=35)
            for _ in range(cr.n_legit):
                self.venda(cr, self.dt_entre(ini, fim))

    def gerar_cliques_sem_conversao(self) -> None:
        vendas_por_creator: dict[str, int] = {}
        for v in self.vendas:
            vendas_por_creator[v["creator_id"]] = vendas_por_creator.get(v["creator_id"], 0) + 1
        for cr in self.creators:
            n_v = vendas_por_creator.get(cr.cid, 0)
            conv = self.unif(*C.CONVERSAO_LEGIT)
            n_extra = int(n_v * (1 / conv - 1)) + int(self.rng.poisson(6))
            ini = cr.inicio_atividade
            for _ in range(n_extra):
                lid = self.escolha(cr.links)[0]
                self.cliques.append((lid, self.dt_entre(ini, FIM),
                                     h("vip", int(self.rng.integers(10**9))),
                                     h("vdev", int(self.rng.integers(10**9)))))

    # -------------------------------------------------- seleção de papéis
    def atribuir_papeis(self) -> dict[str, list[Creator]]:
        elegiveis = [cr for cr in self.creators if cr.criado_em < INICIO - timedelta(days=30)]
        ordem = [elegiveis[i] for i in self.rng.permutation(len(elegiveis))]
        papeis: dict[str, list[Creator]] = {}
        pos = 0

        def pegar(nome: str, k: int, n_legit: tuple[int, int]) -> None:
            nonlocal pos
            grupo = ordem[pos:pos + k]
            pos += k
            for cr in grupo:
                cr.especial = True
                cr.inativo_recente = False
                cr.saque_raro = False
                cr.n_legit = self.inteiro(*n_legit)
            papeis[nome] = grupo

        for t in C.TIPOS_FRAUDE:
            pegar(t, C.N_FRAUDE_POR_TIPO, (8, 35))
        pegar("LEGITIMO_VIRAL", C.N_VIRAIS, (20, 60))
        pegar("RUIDO_PIX_CASAL", 2 * C.N_RUIDO_PIX_CASAL, (10, 40))
        pegar("RUIDO_FAMILIA_DISP", C.N_RUIDO_FAMILIA_DISP, (20, 50))
        pegar("RUIDO_CORPORATIVO", C.N_RUIDO_CORPORATIVO, (20, 45))

        for t in C.TIPOS_FRAUDE + ["LEGITIMO_VIRAL"]:
            n_disc = int(round(len(papeis[t]) * C.FRAC_FRAUDE_DISCRETA)) if t != "LEGITIMO_VIRAL" else 0
            for j, cr in enumerate(papeis[t]):
                cr.tipo = t
                if j < n_disc:
                    cr.obs = "DISCRETA"
        for nome in ("RUIDO_PIX_CASAL", "RUIDO_FAMILIA_DISP", "RUIDO_CORPORATIVO"):
            for cr in papeis[nome]:
                cr.obs = nome
        return papeis

    def janela_fraude(self, cr: Creator, dias: int = 60) -> tuple[datetime, datetime]:
        return max(cr.inicio_atividade, FIM - timedelta(days=dias)), FIM

    # ------------------------------------------------------------ camada 2
    def f1_autocompra(self, grupo: list[Creator]) -> None:
        for cr in grupo:
            p = self.unif(0.12, 0.19) if cr.obs == "DISCRETA" else self.unif(0.30, 0.70)
            n_self = max(2, round(cr.n_legit * p / (1 - p)))
            contas = self.laranjas(self.inteiro(1, 3))
            cartao_proprio = h("ccard", cr.cid)
            a, b = self.janela_fraude(cr)
            for _ in range(n_self):
                self.venda(cr, self.dt_entre(a, b), comprador=self.escolha(contas),
                           meio="PIX" if self.rng.random() < 0.5 else "CARTAO",
                           cartao=cartao_proprio, disp=self.escolha(cr.devices),
                           ip=self.escolha(cr.ips),
                           reembolso_pos_lib=self.rng.random() < 0.4)

    def _preparar_aneis_f2(self, grupo: list[Creator]) -> None:
        """Monta anéis de 4 a 6 creators com a mesma Pix (antes dos logins)."""
        aneis, i = [], 0
        while i < len(grupo):
            k = min(self.inteiro(4, 6), len(grupo) - i)
            if len(grupo) - (i + k) in (1, 2, 3):  # evita anel final pequeno demais
                k = len(grupo) - i if len(grupo) - i <= 6 else 4
            aneis.append(grupo[i:i + k])
            i += k
        for r, anel in enumerate(aneis):
            pix = h("pixrede", r)
            disp_comum = anel[0].devices[0]
            for j, cr in enumerate(anel):
                cr.pix_hash = pix
                if 0 < j < 3 and disp_comum not in cr.devices:  # 3 membros logam no mesmo celular
                    cr.devices.append(disp_comum)
        self.aneis_f2 = aneis

    def _vendas_cruzadas_f2(self) -> None:
        """Membros do anel compram uns dos links dos outros."""
        for anel in self.aneis_f2:
            contas = {cr.cid: self.laranjas(1)[0] for cr in anel}
            for comprador_cr in anel:
                n_cruz = self.inteiro(2, 4) if comprador_cr.obs == "DISCRETA" else self.inteiro(5, 15)
                for _ in range(n_cruz):
                    alvo = self.escolha([c for c in anel if c is not comprador_cr])
                    a, b = self.janela_fraude(alvo)
                    self.venda(alvo, self.dt_entre(a, b), comprador=contas[comprador_cr.cid],
                               disp=comprador_cr.devices[0], ip=comprador_cr.ips[0])

    def f3_compra_estorno(self, grupo: list[Creator]) -> None:
        for cr in grupo:
            frac = self.unif(0.15, 0.25) if cr.obs == "DISCRETA" else self.unif(0.40, 1.0)
            n_e = max(2, round(cr.n_legit * frac))
            contas = self.laranjas(self.inteiro(8, 20))
            a, b = self.janela_fraude(cr)
            for _ in range(n_e):
                self.venda(cr, self.dt_entre(a, b - LIB), comprador=self.escolha(contas),
                           reembolso_pos_lib=True)

    def f4_clique_inflado(self, grupo: list[Creator]) -> None:
        for cr in grupo:
            bot_ips = [h("botip", cr.cid, k) for k in range(self.inteiro(3, 5))]
            bot_devs = [h("botdev", cr.cid, k) for k in range(self.inteiro(2, 3))]
            mult = self.unif(0.3, 0.6) if cr.obs == "DISCRETA" else self.unif(1.0, 3.0)
            n_b = max(3, round(cr.n_legit * mult))
            contas = self.laranjas(self.inteiro(8, 15))
            a, b = self.janela_fraude(cr)
            for _ in range(n_b):
                ts = self.dt_entre(a, b)
                ip, dv = self.escolha(bot_ips), self.escolha(bot_devs)
                self.venda(cr, ts, comprador=self.escolha(contas), meio="PIX", disp=dv, ip=ip,
                           delay_clique=self.unif(2, 12), p_reembolso=0.08)
                # rajada de cliques sem conversão a partir dos mesmos IPs
                lid = self.escolha(cr.links)[0]
                for _ in range(self.inteiro(2, 6)):
                    self.cliques.append((lid, ts - timedelta(seconds=self.unif(1, 600)),
                                         self.escolha(bot_ips), self.escolha(bot_devs)))

    def f5_cartao_testado(self, grupo: list[Creator]) -> None:
        for cr in grupo:
            discreta = cr.obs == "DISCRETA"
            n_cartoes = 1 if discreta else self.inteiro(2, 4)
            a = max(cr.inicio_atividade, FIM - timedelta(days=75))
            b = FIM - timedelta(days=5)
            for k in range(n_cartoes):
                cartao = h("roubado", cr.cid, k)
                n_comp = 3 if discreta else self.inteiro(3, 10)
                for comp in self.laranjas(n_comp):
                    for _ in range(self.inteiro(1, 2)):
                        self.venda(cr, self.dt_entre(a, b), comprador=comp, meio="CARTAO",
                                   cartao=cartao, p_reembolso=0.0,
                                   p_chargeback=0.3 if discreta else 0.6, chargeback_dias=(7, 30))

    # ------------------------------------------------------------ camada 3
    def virais(self, grupo: list[Creator]) -> None:
        for cr in grupo:
            taxa_dia = cr.n_legit / C.DIAS_SIMULADOS
            d0 = FIM - timedelta(days=self.unif(4, 9))
            n_pico = max(30, round(3 * 10 * taxa_dia))
            for _ in range(n_pico):
                self.venda(cr, self.dt_entre(d0, min(FIM, d0 + timedelta(days=3))))

    # ------------------------------------------------------------ camada 4
    def ruido(self, papeis: dict[str, list[Creator]]) -> None:
        casais = papeis["RUIDO_PIX_CASAL"]
        for a, b in zip(casais[::2], casais[1::2]):
            b.pix_hash = a.pix_hash
        for cr in papeis["RUIDO_FAMILIA_DISP"]:
            p = self.unif(0.05, 0.18)
            parente = self.comprador_legit()
            ini = cr.inicio_atividade
            for _ in range(max(1, round(cr.n_legit * p / (1 - p)))):
                self.venda(cr, self.dt_entre(ini, FIM), comprador=parente,
                           disp=self.escolha(cr.devices), ip=self.escolha(cr.ips))
        for cr in papeis["RUIDO_CORPORATIVO"]:
            empresa = self.comprador_legit()
            cartao_corp = h("corp", cr.cid)
            ini = cr.inicio_atividade
            for _ in range(round(cr.n_legit * self.unif(0.35, 0.65))):
                self.venda(cr, self.dt_entre(ini, FIM), comprador=empresa, meio="CARTAO",
                           cartao=cartao_corp)

    # ------------------------------------------------------------ camada 5
    def comissoes_e_saques(self) -> list[tuple]:
        self.vendas.sort(key=lambda v: v["ts"])
        comissoes = []
        por_creator: dict[str, list[tuple]] = {}
        for i, v in enumerate(self.vendas):
            v["venda_id"] = f"V{i:07d}"
            valor = round(v["valor"] * v["comissao_pct"], 2)
            lib_prev = v["ts"] + LIB
            st_ts = v["st_ts"]
            if v["status"] != "APROVADA" and st_ts < lib_prev:
                status, lib = "ESTORNADA", None
            elif lib_prev > FIM:
                status, lib = "PENDENTE", None
            elif v["status"] != "APROVADA":
                status, lib = "ESTORNADA", lib_prev  # comissão já tinha saído
            else:
                status, lib = "LIBERADA", lib_prev
            comissoes.append((f"K{i:07d}", v["venda_id"], v["creator_id"], valor, status, f(lib)))
            if lib:
                por_creator.setdefault(v["creator_id"], []).append((lib, valor, st_ts))

        n = 0
        for cr in self.creators:
            coms = sorted(por_creator.get(cr.cid, []))
            if not coms:
                continue
            intervalo = (30, 60) if cr.saque_raro else C.INTERVALO_SAQUE_DIAS
            prev = datetime.min
            cur = coms[0][0] + timedelta(days=self.inteiro(*intervalo))
            limite = FIM - timedelta(days=C.JANELA_SAQUE_PENDENTE_DIAS)
            while cur < limite:
                val = round(sum(v for lib, v, _ in coms if prev < lib <= cur), 2)
                if val >= 10:
                    self.saques.append((f"S{n:06d}", cr.cid, val, cr.pix_hash, f(cur), "APROVADO"))
                    n += 1
                    prev = cur
                cur += timedelta(days=self.inteiro(*intervalo))
            t = self.dt_entre(limite, FIM)
            val = round(sum(v for lib, v, est in coms
                            if prev < lib <= t and (est is None or est > t)), 2)
            if val > 0 or cr.especial:
                self.saques.append((f"S{n:06d}", cr.cid, max(val, 1.0), cr.pix_hash, f(t), "SOLICITADO"))
                n += 1
        return comissoes

    # --------------------------------------------------------------- gravação
    def gravar(self, comissoes: list[tuple]) -> None:
        C.DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        if C.DB_PATH.exists():
            C.DB_PATH.unlink()
        con = sqlite3.connect(C.DB_PATH)
        con.executescript(C.SCHEMA_PATH.read_text(encoding="utf-8"))
        con.executescript(C.VIEWS_PATH.read_text(encoding="utf-8"))
        cur = con.cursor()
        cur.executemany("INSERT INTO produtores VALUES (?,?,?,?)", self.produtores)
        cur.executemany("INSERT INTO produtos VALUES (?,?,?,?,?,?,?)",
                        [(p["id"], p["produtor_id"], p["nome"], p["tipo"], p["preco"],
                          p["comissao_pct"], p["garantia_dias"]) for p in self.produtos])
        cur.executemany("INSERT INTO creators VALUES (?,?,?,?,?,?)",
                        [(cr.cid, self.fake.name(), h("cpf", cr.cid), cr.pix_hash,
                          self.escolha(CANAIS), f(cr.criado_em)) for cr in self.creators])
        self.logins.sort(key=lambda x: x[3])
        cur.executemany("INSERT INTO logins_creator (creator_id, dispositivo_hash, ip_hash, ts) "
                        "VALUES (?,?,?,?)", self.logins)
        cur.executemany("INSERT INTO links VALUES (?,?,?,?)",
                        [(lid, cr.cid, self.produtos[p]["id"], f(lc))
                         for cr in self.creators for lid, p, lc in cr.links])
        self.cliques.sort(key=lambda x: x[1])
        cur.executemany("INSERT INTO cliques (link_id, ts, ip_hash, dispositivo_hash) VALUES (?,?,?,?)",
                        [(l, f(t), ip, d) for l, t, ip, d in self.cliques])
        cur.executemany("INSERT INTO compradores VALUES (?,?,?,?)",
                        [(self.bid(i), h("bcpf", i), h("bemail", i),
                          f(self.dt_entre(FIM - timedelta(days=1100), INICIO)))
                         for i in range(C.N_COMPRADORES)])
        cur.executemany("INSERT INTO vendas VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                        [(v["venda_id"], v["link_id"], v["comprador_id"], f(v["ts"]), v["valor"],
                          v["meio"], v["cartao"], v["disp"], v["ip"], v["status"], f(v["st_ts"]))
                         for v in self.vendas])
        cur.executemany("INSERT INTO comissoes VALUES (?,?,?,?,?,?)", comissoes)
        cur.executemany("INSERT INTO saques VALUES (?,?,?,?,?,?)", self.saques)
        cur.executemany("INSERT INTO gabarito VALUES (?,?,?)",
                        [(cr.cid, cr.tipo, cr.obs) for cr in self.creators])
        con.commit()
        con.execute("VACUUM")
        con.close()

    def rodar(self) -> None:
        t0 = time.time()
        self._init_compradores()
        self.gerar_catalogo()
        self.gerar_creators()
        papeis = self.atribuir_papeis()
        self._preparar_aneis_f2(papeis["F2_REDE_PIX"])  # altera Pix/dispositivos antes dos logins
        self.gerar_logins()
        self.gerar_vendas_legitimas()
        self.f1_autocompra(papeis["F1_AUTOCOMPRA"])
        self._vendas_cruzadas_f2()
        self.f3_compra_estorno(papeis["F3_COMPRA_ESTORNO"])
        self.f4_clique_inflado(papeis["F4_CLIQUE_INFLADO"])
        self.f5_cartao_testado(papeis["F5_CARTAO_TESTADO"])
        self.virais(papeis["LEGITIMO_VIRAL"])
        self.ruido(papeis)
        self.gerar_cliques_sem_conversao()
        comissoes = self.comissoes_e_saques()
        self.gravar(comissoes)
        print(f"youshop.db gerado em {time.time() - t0:.1f}s: {len(self.vendas)} vendas, "
              f"{len(self.cliques)} cliques, {len(self.saques)} saques, "
              f"{C.DB_PATH.stat().st_size / 1e6:.1f} MB")


if __name__ == "__main__":
    Gerador().rodar()
