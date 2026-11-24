"""Camada do LLM: uma interface mínima com duas implementações.

  LLM.estruturado(Schema, prompt) -> instância de Schema (pydantic)

- GeminiLLM: o real, via langchain-google-genai, com "structured output" (o modelo é
  obrigado a responder num JSON que segue o schema, então não precisamos fazer parse de texto livre).
  Tem throttle simples para respeitar o limite de requisições por minuto do free tier.
- FakeLLM: respostas roteirizadas, para testes sem rede e sem custo.

Essa separação é o padrão "injeção de dependência": o grafo não sabe qual LLM está usando.
"""
from __future__ import annotations

import os
import threading
import time
import warnings
from typing import Callable, Protocol, TypeVar

from pydantic import BaseModel

import config as C

T = TypeVar("T", bound=BaseModel)
# modelos "lite" ignoram temperature; o aviso é inofensivo
warnings.filterwarnings("ignore", message=".*uses fixed sampling defaults.*")


class LLM(Protocol):
    nome: str
    chamadas: int

    def estruturado(self, schema: type[T], prompt: str) -> T: ...


class GeminiLLM:
    def __init__(self, model: str | None = None, min_intervalo_seg: float | None = None) -> None:
        from dotenv import load_dotenv
        from langchain_google_genai import ChatGoogleGenerativeAI

        load_dotenv(C.ROOT / ".env")
        if not os.getenv("GOOGLE_API_KEY"):
            raise RuntimeError("GOOGLE_API_KEY não definida (crie o arquivo .env na raiz do projeto)")
        self.nome = model or os.getenv("GEMINI_MODEL", C.GEMINI_MODEL)
        self._chat = ChatGoogleGenerativeAI(model=self.nome, temperature=0, max_retries=3, timeout=90)
        self._min = float(min_intervalo_seg if min_intervalo_seg is not None
                          else os.getenv("GEMINI_MIN_INTERVALO_SEG", "4"))
        self._ultimo = 0.0
        self._lock = threading.Lock()
        self.chamadas = 0

    def estruturado(self, schema: type[T], prompt: str) -> T:
        with self._lock:  # throttle: no máximo 1 chamada a cada _min segundos
            espera = self._ultimo + self._min - time.monotonic()
            if espera > 0:
                time.sleep(espera)
            self._ultimo = time.monotonic()
        # Cota por minuto (429) ou pico de demanda (503) costumam passar sozinhos: espera e tenta de novo.
        # Se a cota DIÁRIA acabou, as 3 tentativas falham e o grafo cai no fallback.
        for tentativa, espera in enumerate([0, 20, 60]):
            if espera:
                time.sleep(espera)
            self.chamadas += 1
            try:
                out = self._chat.with_structured_output(schema).invoke(prompt)
                if out is None:
                    raise RuntimeError("LLM devolveu resposta vazia")
                return out if isinstance(out, schema) else schema.model_validate(out)
            except Exception as e:  # noqa: BLE001
                transitorio = any(t in str(e) for t in ("429", "RESOURCE_EXHAUSTED", "503", "UNAVAILABLE"))
                if not transitorio or tentativa == 2:
                    raise
        raise RuntimeError("inalcançável")


class FakeLLM:
    """roteiro: {NomeDoSchema: [resposta1, resposta2, ...]} — cada resposta é um objeto,
    um dict, uma função(prompt) -> objeto, ou uma Exception (para simular falha da API)."""

    def __init__(self, roteiro: dict[str, list]) -> None:
        self.nome = "fake"
        self.roteiro = {k: list(v) for k, v in roteiro.items()}
        self.chamadas = 0
        self.prompts: list[tuple[str, str]] = []

    def estruturado(self, schema: type[T], prompt: str) -> T:
        self.chamadas += 1
        self.prompts.append((schema.__name__, prompt))
        fila = self.roteiro.get(schema.__name__)
        if not fila:
            raise RuntimeError(f"FakeLLM sem resposta para {schema.__name__}")
        r = fila.pop(0) if len(fila) > 1 else fila[0]
        if isinstance(r, Exception):
            raise r
        if isinstance(r, Callable) and not isinstance(r, type):
            r = r(prompt)
        return r if isinstance(r, schema) else schema.model_validate(r)
