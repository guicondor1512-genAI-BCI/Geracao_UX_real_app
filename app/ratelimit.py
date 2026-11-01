"""Orcamento de tokens por minuto compartilhado por todos os agentes do processo (D12).

A OpenAI limita gpt-6-luna a 2M tokens/min por organizacao; varios angular_coder em paralelo, cada um lendo spec e HTML
do Stitch, estouram isso e o SDK desiste apos os retries. Este middleware estima os tokens de cada chamada antes de
envia-la e espera o tempo necessario para a janela de 60 s caber em TPM_BUDGET (default 1,5M), registrando as esperas.
"""

import asyncio
import os
import threading
import time
from collections import deque

from langchain.agents.middleware import AgentMiddleware

WINDOW_S = 60.0
CHARS_PER_TOKEN = 4
TOOLS_OVERHEAD = 3000


def budget() -> int:
    return int(os.getenv("TPM_BUDGET", "1500000"))


class TokenWindow:
    """Tokens consumidos nos ultimos 60 s; `reserve` bloqueia ate caber mais `tokens` no orcamento."""

    def __init__(self, limit: int, clock=time.monotonic, sleep=time.sleep):
        self.limit = limit
        self.clock = clock
        self.sleep = sleep
        self.used: deque[tuple[float, int]] = deque()
        self.lock = threading.Lock()
        self.waits = 0
        self.waited_s = 0.0

    def _in_window(self, now: float) -> int:
        while self.used and now - self.used[0][0] > WINDOW_S:
            self.used.popleft()
        return sum(t for _, t in self.used)

    def reserve(self, tokens: int) -> float:
        """Espera ate caber `tokens` na janela (uma chamada maior que o limite passa sozinha) e os registra."""
        waited = 0.0
        while True:
            with self.lock:
                now = self.clock()
                used = self._in_window(now)
                if used + tokens <= self.limit or not self.used:
                    self.used.append((now, tokens))
                    if waited:
                        self.waits += 1
                        self.waited_s += waited
                    return waited
                free_at = self.used[0][0] + WINDOW_S
            pause = max(0.2, min(free_at - now, 5.0))
            self.sleep(pause)
            waited += pause

    def record(self, extra: int) -> None:
        """Acrescenta tokens reais alem da estimativa (ex.: saida gerada)."""
        with self.lock:
            self.used.append((self.clock(), extra))


WINDOW = TokenWindow(budget())


def estimate(request) -> int:
    """Tokens de entrada estimados pelo tamanho das mensagens (4 chars por token) mais as tools."""
    chars = sum(len(str(getattr(m, "content", m))) for m in request.messages)
    if request.system_message is not None:
        chars += len(str(request.system_message.content))
    return chars // CHARS_PER_TOKEN + TOOLS_OVERHEAD


def output_tokens(response) -> int:
    usage = getattr(
        getattr(response, "result", [None])[-1] if getattr(response, "result", None) else None, "usage_metadata", None
    )
    return int(usage.get("output_tokens", 0)) if usage else 0


class TokenBudgetMiddleware(AgentMiddleware):
    """Reserva os tokens estimados de cada chamada de modelo na janela compartilhada antes de chamar o provedor."""

    def __init__(self, window: TokenWindow = WINDOW):
        self.window = window

    def wrap_model_call(self, request, handler):
        self.window.reserve(estimate(request))
        response = handler(request)
        self.window.record(output_tokens(response))
        return response

    async def awrap_model_call(self, request, handler):
        await asyncio.to_thread(self.window.reserve, estimate(request))
        response = await handler(request)
        self.window.record(output_tokens(response))
        return response


def stats() -> dict:
    return {
        "rate_limit_waits": WINDOW.waits,
        "rate_limit_waited_s": round(WINDOW.waited_s, 1),
        "tpm_budget": WINDOW.limit,
    }
