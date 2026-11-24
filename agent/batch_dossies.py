"""Gera os dossiês de todos os alertas ALTO, em lote e offline (correção 8 do plano).

Idempotente: por padrão pula alertas que já têm dossiê, então dá para interromper
(Ctrl+C) ou esbarrar na cota diária do Gemini e continuar depois do ponto em que parou.

Uso:
  python -m agent.batch_dossies                 # todos os ALTO sem dossiê
  python -m agent.batch_dossies --limite 3      # só os 3 de maior score (bom para testar)
  python -m agent.batch_dossies --alerta 42     # um alerta específico (refaz se já existir)
  python -m agent.batch_dossies --refazer       # refaz todos
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
import time

import config as C
from agent.graph import investigar
from agent.llm import GeminiLLM


def pendentes(refazer: bool, limite: int | None) -> list[tuple[int, str, float]]:
    con = sqlite3.connect(C.DB_PATH)
    # dossiê em fallback (API falhou) conta como pendente: é refeito na próxima rodada
    filtro = "" if refazer else """AND NOT EXISTS (SELECT 1 FROM dossies d WHERE d.alerta_id = a.alerta_id
                                     AND COALESCE(json_extract(d.detalhes, '$.fallback'), 0) = 0)"""
    rows = con.execute(f"""SELECT a.alerta_id, a.creator_id, a.score_final FROM alertas a
                           WHERE a.faixa_risco = 'ALTO' {filtro} ORDER BY a.score_final DESC""").fetchall()
    con.close()
    return rows[:limite] if limite else rows


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limite", type=int)
    ap.add_argument("--alerta", type=int)
    ap.add_argument("--refazer", action="store_true")
    args = ap.parse_args()

    llm = GeminiLLM()
    fila = [(args.alerta, "?", 0.0)] if args.alerta else pendentes(args.refazer, args.limite)
    print(f"Modelo: {llm.nome} · {len(fila)} alertas na fila")
    t0, falhas_seguidas = time.monotonic(), 0
    for i, (aid, cid, score) in enumerate(fila, 1):
        try:
            s = investigar(aid, llm)
        except KeyboardInterrupt:
            print("\nInterrompido. Rode de novo para continuar de onde parou.")
            sys.exit(1)
        flag = " FALLBACK" if s["fallback"] else (" NÚMERO NÃO CONFIRMADO" if s["numero_inventado"] else "")
        print(f"[{i}/{len(fila)}] alerta {aid} {s['alerta']['creator_id']} score={s['alerta']['score_final']:.2f} → "
              f"{s['recomendacao']} / {s['confianca']} · {s['duracao_seg']:.0f}s · "
              f"{s['chamadas_llm']} chamadas · {s['profundidade']}{flag}")
        if s["fallback"]:
            print(f"    motivo: {str(s.get('falha'))[:200]}")
            falhas_seguidas += 1
            if falhas_seguidas >= 3:
                print("3 falhas seguidas da API (cota diária?). Parando. Rode de novo mais tarde para continuar;"
                      " os fallbacks gravados serão refeitos com --alerta ou --refazer.")
                break
        else:
            falhas_seguidas = 0
    print(f"Total: {time.monotonic() - t0:.0f}s · {llm.chamadas} chamadas ao LLM")


if __name__ == "__main__":
    main()
