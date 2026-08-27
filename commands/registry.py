import re
import inspect
import logging
from typing import Callable
from dataclasses import dataclass

from errors import NotInteger, RedisError, WrongArity
from storage import Storage
from writer import encode_error


log = logging.getLogger(__name__)


@dataclass(frozen=True)
class Cmd:
    fn: Callable[..., bytes]
    arity: int
    wants_store: bool

COMMANDS: dict[bytes, Cmd] = {}
INT_RE = re.compile(rb"^-?\d+$")

def command(name: str, arity: int):
    def deco(fn):
        params = list(inspect.signature(fn).parameters)
        COMMANDS[name.encode()] = Cmd(fn, arity, bool(params) and params[0] == "store")
        return fn
    return deco

def parse_int(raw: bytes) -> int:
    if not INT_RE.match(raw):
        raise NotInteger
    return int(raw)


def dispatch(frame: list[bytes], store: Storage) -> bytes:
    if not isinstance(frame, list) or not frame or not all(isinstance(x, bytes) for x in frame):
        return encode_error(b"ERR malformed request")
    command = frame[0].upper()

    try:
        cmd = COMMANDS.get(command)
        if cmd is None:
            raise RedisError(b"ERR unknown command '" + command + b"'")

        n = len(frame)

        if (cmd.arity > 0 and n != cmd.arity) or (cmd.arity < 0 and n < -cmd.arity):
            raise WrongArity(command)

        args = frame[1:]
        return cmd.fn(store, *args) if cmd.wants_store else cmd.fn(*args)
    
    except RedisError as exc:
        return encode_error(exc.msg)
    except Exception:
        log.exception("handler crashed on frame %r", frame)
        return encode_error(b"ERR internal error")
