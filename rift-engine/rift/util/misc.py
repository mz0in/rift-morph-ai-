import contextvars
import contextlib
from typing import (
    Callable,
    TypeVar,
)
import contextvars
import contextlib

T = TypeVar("T")


@contextlib.contextmanager
def set_ctx(v: contextvars.ContextVar[T], t: T):
    x = v.set(t)
    try:
        yield t
    finally:
        v.reset(x)


@contextlib.contextmanager
def map_ctx(v: contextvars.ContextVar[T], f: Callable[[T], T]):
    x = v.get()
    x2 = f(x)
    with set_ctx(v, x2):
        yield x2
