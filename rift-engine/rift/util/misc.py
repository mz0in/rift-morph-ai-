import contextlib
import contextvars
import logging
import re
from typing import Callable, TypeVar

T = TypeVar("T")

logger = logging.getLogger(__name__)


@contextlib.contextmanager
def set_ctx(context_variable: contextvars.ContextVar[T], value: T):
    """
    Set the given context variable to the provided value.

    Args:
        context_variable (contextvars.ContextVar): The context variable to set.
        value (T): The value to set the context variable to.
    """
    old_value = context_variable.set(value)
    try:
        yield value
    finally:
        context_variable.reset(old_value)


@contextlib.contextmanager
def map_ctx(context_variable: contextvars.ContextVar[T], mapper: Callable[[T], T]):
    """
    Map the value of the given context variable using the provided function.

    Args:
        context_variable (contextvars.ContextVar): The context variable to map.
        mapper (Callable[[T], T]): The function to apply to the context variable value.

    Yields:
        T: The mapped value of the context variable.
    """
    old_value = context_variable.get()
    new_value = mapper(old_value)
    with set_ctx(context_variable, new_value):
        yield new_value
