import os
import time

from storage import Storage
from reader import Reader
from errors import NeedMoreData, ProtocolError


def save(store: Storage, path: str) -> None:
    tmp = path + ".tmp"
    with open(tmp, "wb") as f:
        f.write(store.dump())
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)

def load(path: str, clock=time.monotonic) -> Storage:
    store = Storage(clock=clock)
    reader = Reader()

    with open(path, "rb") as f:
        while chunk := f.read(64 * 1024):
            reader.feed(chunk)
            while True:
                try:
                    frame = reader.read_frame()
                except NeedMoreData:
                    break
                _type, key, val, wall_deadline = frame
                store._restore(key, val, wall_deadline)

    if reader.buf:
        raise ProtocolError(f"truncated snapshot: {len(reader.buf)} trailing bytes")

    return store