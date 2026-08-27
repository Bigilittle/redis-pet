from .registry import command
from writer import (
    encode_simple_string,
    encode_array,
    encode_bulk_string,
)

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