from .registry import command
from storage import Storage
from snapshots import save
from config import DBFILE
from writer import (
    encode_simple_string,
    encode_array,
    encode_bulk_string,
    encode_error
)
from errors import SaveDB

@command("PING", 1)
def ping() -> bytes:
    return encode_simple_string(b"PONG")


@command("ECHO", 2)
def echo(value: bytes) ->bytes:
    return encode_bulk_string(value)


@command("COMMAND", -1)
def command_(*args: bytes) -> bytes:
    return encode_array([])

     
@command("CLIENT", -2)
def client(*args: bytes) -> bytes:
    return encode_simple_string(b"OK")


@command("SAVE", 1)
def _save(store: Storage):
    try:
        save(store, DBFILE)
        return encode_simple_string(b"OK")
    except Exception as exp:
        raise SaveDB
