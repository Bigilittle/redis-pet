import pytest
import commands                      
from commands.registry import dispatch
from storage import Storage


class FakeClock:
    def __init__(self): self.t = 0.0
    def __call__(self): return self.t


@pytest.fixture
def clk():
    return FakeClock()


@pytest.fixture
def store(clk):
    return Storage(clock=clk)


@pytest.fixture
def d(store):
    def dispatch_(frame):
        return dispatch(frame, store)
    return dispatch_
