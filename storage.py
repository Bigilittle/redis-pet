import time
import heapq
from dataclasses import dataclass
from functools import wraps
import math
from errors import WrongType
from typing import Union
import os

from writer import encode_array

@dataclass
class Entry:
    value: bytes | list[bytes]
    expire_at: float | None = None

class Storage:
    def __init__(self, clock=time.monotonic):
        self.storage: dict[bytes, Entry]        = {} # {key: (value, expire_at)}
        self.heap:    list[tuple[float, bytes]] = [] # [(expire_at, key)....]

        self.clock = clock



    def dump(self) -> tuple[int, bytes | Exception]:
        """
        1 - успех
        0 - успешное сохранение
        """
        
        now_mono = self.clock()
        now_wall = time.time()

        entries = []

        for key, entry in self.storage.items():

            if isinstance(entry.value, list):
                type_value = b"list"
            else:
                type_value = b"str"

            expire_at = None
            if entry.expire_at is not None:
                remaining = entry.expire_at - now_mono
                if remaining <= 0:
                    continue
                expire_at = round(
                    (now_wall + remaining) * 1000
                )

            data = [
                type_value,
                key,
                entry.value,
                expire_at,
            ]

            entries.append(data)

        dump = b"".join(
            encode_array(entry)
            for entry in entries
        )

        return dump


    def _restore(self, key, value, wall_deadline_ms) -> None:
        mono_deadline = None

        if wall_deadline_ms is not None:
            remaining = wall_deadline_ms / 1000 - time.time()

            if remaining <= 0:
                return

            mono_deadline = self.clock() + remaining

        self.storage[key] = Entry(value, mono_deadline)

        if mono_deadline is not None:
            heapq.heappush(self.heap, (mono_deadline, key))

    



                

                






    def _check_ttl(self, key) -> int:
        """1 - валидно 
           0 - мертво 
          -1 - есть, но нет ттл
          -2 - ключа нет
        """
        entry = self.storage.get(key)
        if entry is None: 
            return -2

        if entry.expire_at is None:
            return -1

        return 1 if entry.expire_at > self.clock() else 0

    #########################
    # Вспомогательные функции
    #########################

    def _purge_if_expired(self, key: bytes) -> int:
        """Удаляет ключ если у него просрочен ttl"""
        expired = self._check_ttl(key)
        if expired == 0:
            del self.storage[key]
        return expired

    def _purge_expired(func):
        @wraps(func)
        def wrapper(self, key: bytes, *args, **kwargs):
            self._purge_if_expired(key)
            return func(self, key, *args, **kwargs)

        return wrapper


    @_purge_expired
    def __contains__(self, key: bytes) -> bool:
        return key in self.storage

    ##################
    # Основные функции
    ##################


    @_purge_expired
    def get(self, key: bytes) -> bytes | None:
        entry = self.storage.get(key)

        if entry is None:
            return None
        elif isinstance(entry.value, list):
            raise WrongType
        return entry.value

    
    def __getitem__(self, key: bytes) -> bytes | None:
        return self.get(key)


    def set(self, key: bytes, value: bytes) -> None:
        self.storage[key] = Entry(value=value)


    def __setitem__(self, key: bytes, value: bytes) -> None:
        return self.set(key, value)


    @_purge_expired
    def lpush(self, key: bytes, *values: bytes) -> int:
        if not values:
            raise ValueError("LPUSH requires at least one value")

        entry = self.storage.get(key)
        if entry is None:
            entry = Entry([])
            self.storage[key] = entry 
        elif not isinstance(entry.value, list):
            raise WrongType
        for value in values:
            entry.value.insert(0, value)

        return len(entry.value)


    @_purge_expired
    def rpush(self, key: bytes, *values: bytes) -> int:
        if not values:
            raise ValueError("RPUSH requires at least one value")
        
        entry = self.storage.get(key)
        if entry is None:
            entry = Entry([])
            self.storage[key] = entry 
        elif not isinstance(entry.value, list):
            raise WrongType
        for value in values:
            entry.value.append(value)

        return len(entry.value)


    @_purge_expired
    def lpop(self, key) -> bytes | None:

        entry = self.storage.get(key)
        if entry is None:
            return None
        elif not isinstance(entry.value, list):
            raise WrongType

        value = entry.value.pop(0)
        if len(entry.value) == 0:
            del self.storage[key]

        return value


    @_purge_expired
    def rpop(self, key) -> bytes | None:

        entry = self.storage.get(key)
        if entry is None:
            return None
        elif not isinstance(entry.value, list):
            raise WrongType
        value = entry.value.pop()
        if len(entry.value) == 0:
            del self.storage[key]

        return value


    @_purge_expired
    def llen(self, key) -> int:
        entry = self.storage.get(key)
        if entry is None:
            return 0
        elif not isinstance(entry.value, list):
            raise WrongType
        return len(entry.value)

    @_purge_expired
    def lrange(self, key, start, stop) -> list[bytes]:
        entry = self.storage.get(key)
        if entry is None:
            return []
        elif not isinstance(entry.value, list):
            raise WrongType

        increase = len(entry.value) + 1 if stop < 0 else 1
        stop += increase

        if stop < 0:
            return []

        return entry.value[start:stop]



    @_purge_expired
    def delete(self, key: bytes) -> int:
        if key in self.storage:
            del self.storage[key]
            return 1
        return 0

    def __delitem__(self, key: bytes) -> None:
        self.delete(key)


    @_purge_expired
    def update(self, key: bytes, value: bytes) -> None:
        entry = self.storage.get(key)
        if entry is None:
            self.storage[key] = Entry(value)  
        else:
            entry.value = value  

        
    @_purge_expired
    def expire(self, key: bytes, sec: float) -> bool:
        entry = self.storage.get(key)
        if entry is None:
            return False
        entry.expire_at = sec + self.clock()
        heapq.heappush(self.heap, (entry.expire_at, key))
        return True


    @_purge_expired
    def ttl(self, key: bytes) -> int:
        entry = self.storage.get(key)
        if entry is None:
            return -2
        if entry.expire_at is None:
            return -1
        return math.ceil(entry.expire_at - self.clock())

        
    def next_deadline(self) -> float | None:
        while self.heap:
            expire_at, key = self.heap[0]
            entry = self.storage.get(key)    
            if entry is None or expire_at != entry.expire_at:
                heapq.heappop(self.heap)                  # мусорный будильник
                continue
            return expire_at
        return None
            

    def collect_expired(self) -> None:
        now = self.clock()
        while self.heap and self.heap[0][0] <= now:
            expire_at, key = heapq.heappop(self.heap) 
            entry = self.storage.get(key)    
            if entry is not None and entry.expire_at is not None and entry.expire_at <= now:
                del self.storage[key]
            

    
