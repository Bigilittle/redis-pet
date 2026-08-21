from writer import *
from storage import storage
import re

INT_RE = re.compile(rb"^-?\d+$")

def err_len_args(command: bytes) -> bytes:
    return encode_error(b"ERR wrong number of arguments for '" + command.lower() + b"' command")    

def _change_by(key: bytes, step: int) -> bytes:
    val = storage.get(key)
    if val is None: 
        val = b"0"
    if not INT_RE.match(val): 
        return encode_error(b"ERR value is not an integer or out of range")
    elif not (-(2**63) <= int(val) + step <= 2**63 - 1):
        return encode_error(b"ERR value is not an integer or out of range")
    else:
        new_val = int(val) + step 
    storage.update(key, str(new_val).encode())
    return encode_integer(new_val) 


def dispatch(frame: bytes| list[bytes]) -> bytes:
    if not isinstance(frame, list) or not frame or not all(isinstance(x, bytes) for x in frame):
        return encode_error(b"ERR malformed request")
    command = frame[0].upper()
    len_frame = len(frame)
    match command:
        case b"PING":
            return encode_simple_string(b"PONG")


        case b"ECHO":
            if len_frame != 2:
                return err_len_args(command)

            return encode_bulk_string(frame[1])


        case b"SET":
            if len_frame != 3:
                return err_len_args(command)

            storage[frame[1]] = frame[2]
            return encode_simple_string(b"OK")

        case b"GET":
            if len_frame != 2:
                return err_len_args(command)

            val = storage.get(frame[1])
            if val is None: 
                return encode_null()

            return encode_bulk_string(val)


        case b"DEL":
            if len_frame == 1:
                return err_len_args(command)

            count_del = 0
            for key in frame[1:]: 
                count_del += storage.delete(key)

            return (encode_integer(count_del))

        case b"EXPIRE":
            if len_frame != 3:
                return err_len_args(command)
            elif not INT_RE.match(frame[2]): 
                return encode_error(b"ERR value is not an integer or out of range") 

            ok = storage.expire(frame[1], int(frame[2]))
            return encode_integer(1 if ok else 0)


        case b"INCR":
            if len_frame != 2:
                return err_len_args(command)

            return _change_by(frame[1], 1)


        case b"DECR":
            if len_frame != 2:
                return err_len_args(command)

            return _change_by(frame[1], -1)


        case b"INCRBY":
            if len_frame != 3:
                return err_len_args(command)
            elif not INT_RE.match(frame[2]): 
                return encode_error(b"ERR value is not an integer or out of range") # редис тоже возращает так

            return _change_by(frame[1], int(frame[2]))


        case b"DECRBY":
            if len_frame != 3:
                return err_len_args(command)
            elif not INT_RE.match(frame[2]): 
                return encode_error(b"ERR value is not an integer or out of range") 

            return _change_by(frame[1], -int(frame[2]))

        case b"TTL":                      
            if len_frame != 2: return err_len_args(command)
            return encode_integer(storage.ttl(frame[1])) 


        case b"COMMAND":
            return encode_array([])


        case b"CLIENT":
            return encode_simple_string(b"OK")


        case _:
            return encode_error(b"ERR unknown command '" + command + b"'")