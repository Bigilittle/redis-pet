from .registry import command, parse_int
from storage import Storage
from writer import (
    encode_array,
    encode_bulk_string,
    encode_null,
    encode_integer,
)


@command("LPUSH", -3)
def lpush(store: Storage, key: bytes, *values: bytes) -> bytes:
    return encode_integer(store.lpush(key, *values))


@command("RPUSH", -3)
def rpush(store: Storage, key: bytes, *values: bytes) -> bytes:
    return encode_integer(store.rpush(key, *values))


@command("LPOP", 2)
def lpop(store: Storage, key: bytes) -> bytes:
    value = store.lpop(key)
    if value is None:
        return encode_null()
    return encode_bulk_string(value)


@command("RPOP", 2)
def rpop(store: Storage, key: bytes) -> bytes:
    value = store.rpop(key)
    if value is None:
        return encode_null()
    return encode_bulk_string(value)


@command("LLEN", 2)
def llen(store: Storage, key: bytes) -> bytes:
    return encode_integer(store.llen(key))


@command("LRANGE", 4)
def lrange(store: Storage, key: bytes, start: bytes, stop: bytes) -> bytes:
    return encode_array(store.lrange(key, parse_int(start), parse_int(stop)))
