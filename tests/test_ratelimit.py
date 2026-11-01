"""Janela de tokens por minuto: espera quando o orcamento acaba e libera quando a janela desliza."""

from app.ratelimit import TokenWindow


class Clock:
    def __init__(self):
        self.now = 0.0
        self.slept = 0.0

    def __call__(self):
        return self.now

    def sleep(self, s):
        self.now += s
        self.slept += s


def test_reserve_waits_until_window_frees():
    clock = Clock()
    w = TokenWindow(1000, clock=clock, sleep=clock.sleep)
    assert w.reserve(600) == 0 and w.reserve(300) == 0
    waited = w.reserve(500)  # 900 usados: so cabe depois de 60 s da primeira reserva
    assert waited > 0 and clock.now >= 60 and w.waits == 1
    assert w.reserve(100) == 0


def test_oversized_call_passes_when_window_empty():
    clock = Clock()
    w = TokenWindow(100, clock=clock, sleep=clock.sleep)
    assert w.reserve(5000) == 0 and w.waits == 0
