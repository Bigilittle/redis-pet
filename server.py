import socket, selectors
import os
import time

from config import DBFILE
from errors import ConnectionClosed, ProtocolError, NeedMoreData
from writer import *
from connection import Connection
from snapshots import load
from storage import Storage

MAX_SELECT_TIMEOUT = 3600.0
            
def main(port: int = 9000, dbfile: str = DBFILE):
    store = load(dbfile) if os.path.exists(dbfile) else Storage()
    sel = selectors.DefaultSelector()

    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("0.0.0.0", port))
    srv.listen(128)
    srv.setblocking(False)
    sel.register(srv, selectors.EVENT_READ)
    while True:
        nd = store.next_deadline()
        timeout = None if nd is None else min(MAX_SELECT_TIMEOUT, max(0.0, nd - time.monotonic()))
        for key, events in sel.select(timeout):        # единственное место ожидания
            sock = key.fileobj
            if sock is srv:                      # готов слушающий = accept не заблокирует
                client_sock, addr = srv.accept()
                client_sock.setblocking(False)
                sel.register(client_sock, selectors.EVENT_READ, data=Connection(sel=sel, sock=client_sock, store=store))
            else:
                conn = key.data
                if events & selectors.EVENT_READ and not conn.closed:
                    conn.on_readable()
                if events & selectors.EVENT_WRITE and not conn.closed:
                    conn.on_writable()
        store.collect_expired() 


if __name__ == "__main__":
    main(9000)