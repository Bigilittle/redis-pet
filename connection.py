import socket, selectors
from selectors import EVENT_READ, EVENT_WRITE
from reader import Reader
from writer import *
from errors import NeedMoreData, ConnectionClosed, ProtocolError
from commands.registry import dispatch
from storage import storage
import logging



log = logging.getLogger(__name__)


class Connection:
    def __init__(
        self,
        sock: socket.socket,
        sel: selectors.BaseSelector,
        step: int = 64 * 1024,
    ):
        self.sel     = sel
        self.socet   = sock
        self.reader  = Reader()
        self.out_buf = bytearray()
        self.step    = step
        self.closed   = False

    def close(self) -> None:
        self.sel.unregister(self.socet)
        self.socet.close()
        self.closed = True



    def on_readable(self):
        try:
            self.reader.feed(self.socet.recv(self.step))
        except (ConnectionClosed, ConnectionError):   # FIN или RST при чтении
            self.close()
            return
        while True:
            try:
                frame = self.reader.read_frame()
            except NeedMoreData:
                break
            except ProtocolError:
                self.close()
                return

            try:
                response = dispatch(frame, storage)
            except Exception:
                log.exception("handler crashed on frame %r", frame)
                response = encode_error(b"ERR internal error")
            self.out_buf += response
            
        if self.out_buf and not self.closed:
            self.sel.modify(
                self.socet,
                EVENT_READ | EVENT_WRITE,
                data=self
            )

    def on_writable(self):
        try:
            n = self.socet.send(self.out_buf)     
        except ConnectionError: 
            self.close()
            return

        del self.out_buf[:n]

        if not self.out_buf and not self.closed:
            self.sel.modify(
                self.socet,
                EVENT_READ,
                data=self
            )
        
    
