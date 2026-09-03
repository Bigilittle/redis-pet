import socket, selectors
from selectors import EVENT_READ, EVENT_WRITE
from reader import Reader
from writer import *
from errors import NeedMoreData, ConnectionClosed, ProtocolError
from commands.registry import dispatch
from storage import Storage
import logging



log = logging.getLogger(__name__)


class Connection:
    def __init__(
        self,
        sock: socket.socket,
        sel: selectors.BaseSelector,
        store: Storage,
        step: int = 64 * 1024,
    ):
        self.sel     = sel
        self.store   = store
        self.sock    = sock
        self.reader  = Reader()
        self.out_buf = bytearray()
        self.step    = step
        self.closed  = False

    def close(self) -> None:
        self.sel.unregister(self.sock)
        self.sock.close()
        self.closed = True



    def on_readable(self):
        try:
            self.reader.feed(self.sock.recv(self.step))
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
                response = dispatch(frame, self.store)
            except Exception:
                log.exception("handler crashed on frame %r", frame)
                response = encode_error(b"ERR internal error")
            self.out_buf += response
            
        if self.out_buf and not self.closed:
            self.sel.modify(
                self.sock,
                EVENT_READ | EVENT_WRITE,
                data=self
            )

    def on_writable(self):
        try:
            n = self.sock.send(self.out_buf)     
        except ConnectionError: 
            self.close()
            return

        del self.out_buf[:n]

        if not self.out_buf and not self.closed:
            self.sel.modify(
                self.sock,
                EVENT_READ,
                data=self
            )
        
    
