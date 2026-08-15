from writer import *
from storage import storage


def err_len_args(command: bytes) -> bytes:
    return encode_error(b"ERR wrong number of arguments for '" + command.lower() + b"' command")    

def dispatch(frame: bytes| list[bytes]) -> bytes:
    if not isinstance(frame, list) or not frame or not all(isinstance(x, bytes) for x in frame):
        for x in frame:
            print(type(x))
            print(x)
            print("-"*10)
        return encode_error(b"ERR malformed request")
    command = frame[0].upper()
    len_frame = len(frame)
    match command:
        case b"PING":
            return encode_simple_string(b"PONG")
        case b"ECHO":
            if len_frame != 2: return err_len_args(command)
            return encode_bulk_string(frame[1])
        case b"SET":
            if len_frame != 3: return err_len_args(command)
            storage[frame[1]] = frame[2]
            return encode_simple_string(b"OK")
        case b"GET":
            if len_frame != 2: return err_len_args(command)
            val = storage.get(frame[1])
            if val is None: 
                return encode_null()
            return encode_bulk_string(val)
        case b"DEL":
            if len_frame == 1: return err_len_args(command)
            count_del = 0
            for key in frame[1:]: 
                if key in storage: 
                    del storage[key]
                    count_del += 1
            return (encode_integer(count_del))
        case b"COMMAND":
            return encode_array([])
        case b"CLIENT":
            return encode_simple_string(b"OK")
        case _:
            return encode_error(b"ERR unknown command '" + command + b"'")