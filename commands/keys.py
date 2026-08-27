from .registry import command, parse_int
from storage import Storage
from writer import encode_integer


@command("DEL", -2)
def del_(store: Storage, *keys: bytes) -> bytes:
    return encode_integer(sum(store.delete(key) for key in keys))


@command("EXPIRE", 3)
def expire(store: Storage, key: bytes, sec: bytes) -> bytes:
    return encode_integer(1 if store.expire(key, parse_int(sec)) else 0)


@command("TTL", 2)
def ttl(store: Storage, key: bytes) -> bytes:
    return encode_integer(store.ttl(key))
