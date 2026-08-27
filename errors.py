import dataclasses


@dataclasses.dataclass
class RespError:
    message: bytes

class ProtocolError(Exception):
    """Битый кадр / рассинхрон. Лечится только закрытием соединения."""

class ConnectionClosed(Exception):
    """Пир закрыл соединение: recv вернул b""."""

class NeedMoreData(Exception):
    """Нехватка данных в буфере"""


class RedisError(Exception):
    msg: bytes = b"ERR unknown error"
    def __init__(self, msg: bytes | None = None):
        self.msg = msg or type(self).msg

class WrongType(RedisError):
    msg = b"WRONGTYPE Operation against a key holding the wrong kind of value"

class NotInteger(RedisError):
    msg = b"ERR value is not an integer or out of range"

class WrongArity(RedisError):
    def __init__(self, cmd: bytes):
        super().__init__(
            b"ERR wrong number of arguments for '" 
            + cmd.lower() 
            + b"' command"
        )