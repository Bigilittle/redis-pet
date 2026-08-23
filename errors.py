from dataclasses import dataclass


@dataclass
class RespError:
    message: bytes

class ProtocolError(Exception):
    """Битый кадр / рассинхрон. Лечится только закрытием соединения."""


class ConnectionClosed(Exception):
    """Пир закрыл соединение: recv вернул b""."""

class NeedMoreData(Exception):
    """Нехватка данных в буфере"""

class WrongType(Exception):
    """Операция над неправильным типом данных"""