from .registry import command, parse_int
from errors import RedisError
from storage import Storage
from writer import (
    encode_simple_string,
    encode_array,
    encode_bulk_string,
    encode_null,
    encode_integer
)


def _change_by(store: Storage, key: bytes, step: int) -> bytes:
    val = store.get(key)
    new = (0 if val is None else parse_int(val)) + step
    if not -(2**63) <= new <= 2**63 - 1:
        raise RedisError(b"ERR increment or decrement would overflow")
    store.update(key, str(new).encode())
    return encode_integer(new)


@command("GET", 2)
def get(store: Storage, key: bytes) -> bytes:
    val = store.get(key)
    if val is None: 
        return encode_null()
    return encode_bulk_string(val)


@command("SET", 3)
def set_(store: Storage, key: bytes, value: bytes) -> bytes:
    store[key] = value
    return encode_simple_string(b"OK")


@command("INCR", 2)
def incr(store: Storage, key: bytes) -> bytes:
    return _change_by(store, key, 1)


@command("INCRBY", 3)
def incrby(store: Storage, key: bytes, step: bytes) -> bytes:
    return _change_by(store, key, parse_int(step))


@command("DECR", 2)
def decr(store: Storage, key: bytes) -> bytes:
    return _change_by(store, key, -1)


@command("DECRBY", 3)
def decrby(store: Storage, key: bytes, step: bytes) -> bytes:
    return _change_by(store, key, -parse_int(step))
