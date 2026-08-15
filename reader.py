import socket
from dataclasses import dataclass
from errors import ProtocolError, ConnectionClosed, NeedMoreData


@dataclass
class RespError:
    message: bytes

class Reader:
    MAX_LINE = 64 * 1024  # предохранитель: заголовок длиннее — мусор или злодей

    def __init__(self):
        self.buf = bytearray()
        self.pos = 0

    def feed(self, chunk: bytes) -> None:
        """Дозабрать данныe в буфер"""
        if not chunk:
            raise ConnectionClosed
        self.buf += chunk


    def _read_line(self) -> bytes:
        """Прочитать до \\r\\n, вернуть без разделителя."""
        end = self.buf.find(b"\r\n", self.pos)
        if end == -1:
            if len(self.buf) - self.pos > self.MAX_LINE:
                raise ProtocolError("line too long")
            raise NeedMoreData
        line = bytes(self.buf[self.pos:end])
        self.pos = end + 2 
        return line


    def _read_length(self) -> int:
        """Число после $ или *."""
        line = self._read_line()
        try:
            return int(line)
        except ValueError as e:
            raise ProtocolError(f"bad length: {line!r}") from e

    def read_exactly(self, n: int) -> bytes:
        """Прочитать и отдать ровно n первых байт."""
        while len(self.buf) - self.pos < n:
            raise NeedMoreData
        out = bytes(self.buf[self.pos:self.pos + n],)
        self.pos += n
        return out

    def read_frame(self) -> bytes | None:
        start = self.pos
        try:
            frame = self._read_frame()
        except NeedMoreData:
            self.pos = start
            raise
        del self.buf[:self.pos]
        self.pos = 0
        return frame

    def _read_frame(self) -> bytes | None:
        while self.buf[self.pos:self.pos + 2] == b"\r\n":   # пустая inline-строка: молча пропустить
            self.pos += 2

        frame_type = self.read_exactly(1)
        match frame_type:
            case b"+":
                return self._read_line()
            
            case b"-":
                return RespError(self._read_line())

            case b":":
                return self._read_length()
                

            case b"$":
                n = self._read_length()
                if n == -1:
                    return None                     
                if n < -1:
                    raise ProtocolError(f"invalid bulk length: {n}")
                payload = self.read_exactly(n + 2)
                if payload[-2:] != b"\r\n":
                    raise ProtocolError("missing trailing CRLF: desync")
                return payload[:-2]
            
            case b"*":
                n = self._read_length()
                if n == -1:
                    return None  
                if n < -1:
                    raise ProtocolError(f"invalid multibulk length: {n}")
                resp = []
                for _ in range(n):
                    resp.append(self._read_frame())
                return resp
                
            case _:
                raise ProtocolError(f"unknown frame type: {frame_type!r}")