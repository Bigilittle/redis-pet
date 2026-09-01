from collections.abc import Sequence

from errors import ProtocolError, RespError

def encode_simple_string(s: bytes) -> bytes:
    if b"\r" in s or b"\n" in s:
        raise ProtocolError(f"CR/LF inside line frame: {s!r}")
    return b"+" + s + b"\r\n"

def encode_error(msg: bytes) -> bytes:
    if b"\r" in msg or b"\n" in msg:
        raise ProtocolError(f"CR/LF inside line frame: {msg!r}")
    return b"-" + msg + b"\r\n"

def encode_integer(n: int) -> bytes:
    try:
        n = int(n)
    except ValueError as e:
        raise ValueError("cant convert {n} to integer")
    return b":" + str(n).encode() + b"\r\n"

def encode_bulk_string(s: bytes) -> bytes:
    len_s = len(s)
    return b"$" + str(len_s).encode() + b"\r\n" + s + b"\r\n"

def encode_null():
    return b"$" + str(-1).encode() + b"\r\n"


RespValue = bytes | int | None | list["RespValue"] | RespError
def encode_array(arr: Sequence[RespValue]) -> bytes:
    parts = [
        b"*",
        str(len(arr)).encode(),
        b"\r\n",
    ]
    for value in arr:
        match value:
            case bytes():
                parts.append(encode_bulk_string(value))

            case int():
                parts.append(encode_integer(value))

            case None:
                parts.append(encode_null())

            case list():
                parts.append(encode_array(value))

            case RespError(message=msg):
                parts.append(encode_error(msg))

            case _:
                raise TypeError(f"cannot encode {type(value).__name__} in array")
            

    return b"".join(parts)