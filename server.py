import socket, selectors
import os
import time

from config import DBFILE, SAVE_INTERVAL
from errors import ConnectionClosed, ProtocolError, NeedMoreData
from writer import *
from connection import Connection
from snapshots import load, save
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

    next_save_at = time.monotonic() + SAVE_INTERVAL

    while True:
        now = time.monotonic()
        deadlines = [d for d in (store.next_deadline(), next_save_at) if d is not None]
        timeout = max(0.0, min(min(deadlines) - now, MAX_SELECT_TIMEOUT)) if deadlines else None


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

        if time.monotonic() >= next_save_at:                
            if store.dirty:
                try:
                    save(store, dbfile)
                except OSError:
                    print("autosave failed")
            next_save_at = time.monotonic() + SAVE_INTERVAL


if __name__ == "__main__":
    main(9000)