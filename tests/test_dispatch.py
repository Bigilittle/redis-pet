import pytest


PONG      = b"+PONG\r\n"
OK        = b"+OK\r\n"
NIL       = b"$-1\r\n"
EMPTY_ARR = b"*0\r\n"
WRONGTYPE = b"-WRONGTYPE Operation against a key holding the wrong kind of value\r\n"
ERR_VALUE = b"-ERR value is not an integer or out of range\r\n"
ERR_OVER  = b"-ERR increment or decrement would overflow\r\n"
ERR_MALF  = b"-ERR malformed request\r\n"

def INT(n):  return b":%d\r\n" % n
def BULK(s): return b"$%d\r\n%s\r\n" % (len(s), s)
def ARR(*items): return b"*%d\r\n" % len(items) + b"".join(BULK(i) for i in items)
def ERR_LEN(cmd): return b"-ERR wrong number of arguments for '%s' command\r\n" % cmd.lower()


# ---------------------------------------------------------------- базовые

def test_ping(d):
    assert d([b"PING"]) == PONG

def test_ping_low(d):
    assert d([b"ping"]) == PONG

def test_echo(d):
    assert d([b"ECHO", b"hello"]) == BULK(b"hello")

def test_echo_empty_string(d):
    assert d([b"ECHO", b""]) == BULK(b"")

def test_unknown(d):
    assert d([b"WAT"]) == b"-ERR unknown command 'WAT'\r\n"

@pytest.mark.parametrize("frame", [
    b"PING",            # не список
    [],                 # пустой
    [b"SET", "k", b"v"] # не-bytes элемент
], ids=["not-list", "empty", "non-bytes-item"])
def test_malformed(d, frame):
    assert d(frame) == ERR_MALF

def test_command_stub(d):
    assert d([b"COMMAND"]) == EMPTY_ARR

def test_client_stub(d):
    assert d([b"CLIENT", b"SETNAME", b"x"]) == OK


# ---------------------------------------------------------------- строки

def test_set(d):
    assert d([b"SET", b"k", b"val"]) == OK

def test_set_get(d):
    d([b"SET", b"k", b"val"])
    assert d([b"GET", b"k"]) == BULK(b"val")

def test_rewriting_set(d):
    d([b"SET", b"k", b"val"])
    d([b"SET", b"k", b"value"])
    assert d([b"GET", b"k"]) == BULK(b"value")

def test_nil_get(d):
    assert d([b"GET", b"k"]) == NIL

def test_get_binary_safe(d):
    d([b"SET", b"k", b"a\r\nb\x00"])
    assert d([b"GET", b"k"]) == BULK(b"a\r\nb\x00")


# ---------------------------------------------------------------- INCR-семья

def test_incr_creates(d):
    assert d([b"INCR", b"c"]) == INT(1)

def test_incr_counts(d):
    d([b"INCR", b"c"])
    assert d([b"INCR", b"c"]) == INT(2)

def test_incr_is_visible_to_get(d):
    d([b"INCR", b"c"])
    assert d([b"GET", b"c"]) == BULK(b"1")

def test_decr_below_zero(d):
    assert d([b"DECR", b"c"]) == INT(-1)

def test_decr_from_value(d):
    d([b"SET", b"c", b"10"])
    assert d([b"DECR", b"c"]) == INT(9)

def test_incrby_step(d):
    d([b"SET", b"c", b"5"])
    assert d([b"INCRBY", b"c", b"7"]) == INT(12)

def test_decrby_step(d):
    d([b"SET", b"c", b"5"])
    assert d([b"DECRBY", b"c", b"7"]) == INT(-2)

def test_incrby_negative_step(d):
    assert d([b"INCRBY", b"c", b"-3"]) == INT(-3)

@pytest.mark.parametrize("value", [b"abc", b" 11 ", b"2_1", b"1.5", b"", b"+1"],
                        ids=["text", "spaces", "underscore", "float", "empty", "plus"])
def test_incr_non_integer_value(d, value):
    d([b"SET", b"c", value])
    assert d([b"INCR", b"c"]) == ERR_VALUE

def test_incr_error_does_not_touch_value(d):
    d([b"SET", b"c", b"abc"])
    d([b"INCR", b"c"])
    assert d([b"GET", b"c"]) == BULK(b"abc")

@pytest.mark.parametrize("step", [b"x", b" 1", b"1_0", b"1.0", b""],
                        ids=["text", "space", "underscore", "float", "empty"])
def test_incrby_bad_step(d, step):
    assert d([b"INCRBY", b"c", step]) == ERR_VALUE
    assert d([b"DECRBY", b"c", step]) == ERR_VALUE

def test_incrby_overflow(d):
    d([b"SET", b"c", b"9223372036854775807"])
    assert d([b"INCRBY", b"c", b"1"]) == ERR_OVER
    assert d([b"GET", b"c"]) == BULK(b"9223372036854775807")

def test_decrby_underflow(d):
    d([b"SET", b"c", b"-9223372036854775808"])
    assert d([b"DECR", b"c"]) == ERR_OVER


# ---------------------------------------------------------------- DEL

def test_del_mixed(d):
    d([b"SET", b"a", b"1"])
    assert d([b"DEL", b"a", b"ghost"]) == INT(1)
    assert d([b"GET", b"a"]) == NIL

def test_del_many(d):
    d([b"SET", b"a", b"1"])
    d([b"SET", b"b", b"2"])
    assert d([b"DEL", b"a", b"b"]) == INT(2)

def test_del_missing(d):
    assert d([b"DEL", b"ghost"]) == INT(0)


# ---------------------------------------------------------------- EXPIRE / TTL

def test_ttl_missing(d):
    assert d([b"TTL", b"k"]) == INT(-2)

def test_ttl_persistent(d):
    d([b"SET", b"k", b"v"])
    assert d([b"TTL", b"k"]) == INT(-1)

def test_expire_sets_ttl(d):
    d([b"SET", b"k", b"v"])
    assert d([b"EXPIRE", b"k", b"10"]) == INT(1)
    assert d([b"TTL", b"k"]) == INT(10)

def test_expire_missing(d):
    assert d([b"EXPIRE", b"ghost", b"10"]) == INT(0)

def test_ttl_counts_down(d, clk):
    d([b"SET", b"k", b"v"])
    d([b"EXPIRE", b"k", b"10"])
    clk.t += 4
    assert d([b"TTL", b"k"]) == INT(6)
    assert d([b"GET", b"k"]) == BULK(b"v")

def test_ttl_fractional_rounds_up(d, clk):
    d([b"SET", b"k", b"v"])
    d([b"EXPIRE", b"k", b"10"])
    clk.t += 3.5
    assert d([b"TTL", b"k"]) == INT(7)

def test_expired_key_is_gone(d, clk):
    d([b"SET", b"k", b"v"])
    d([b"EXPIRE", b"k", b"10"])
    clk.t += 11
    assert d([b"GET", b"k"]) == NIL
    assert d([b"TTL", b"k"]) == INT(-2)
    assert d([b"DEL", b"k"]) == INT(0)

def test_expire_on_expired_key(d, clk):
    d([b"SET", b"k", b"v"])
    d([b"EXPIRE", b"k", b"10"])
    clk.t += 11
    assert d([b"EXPIRE", b"k", b"10"]) == INT(0)

def test_expire_overrides_previous(d, clk):
    d([b"SET", b"k", b"v"])
    d([b"EXPIRE", b"k", b"10"])
    d([b"EXPIRE", b"k", b"100"])
    clk.t += 50
    assert d([b"GET", b"k"]) == BULK(b"v")
    assert d([b"TTL", b"k"]) == INT(50)

def test_expire_non_positive_deletes_now(d):
    d([b"SET", b"k", b"v"])
    assert d([b"EXPIRE", b"k", b"0"]) == INT(1)
    assert d([b"GET", b"k"]) == NIL
    d([b"SET", b"k", b"v"])
    assert d([b"EXPIRE", b"k", b"-5"]) == INT(1)
    assert d([b"GET", b"k"]) == NIL

def test_set_removes_ttl(d):
    d([b"SET", b"k", b"v"])
    d([b"EXPIRE", b"k", b"10"])
    d([b"SET", b"k", b"w"])
    assert d([b"TTL", b"k"]) == INT(-1)

def test_incr_keeps_ttl(d, clk):
    d([b"SET", b"k", b"1"])
    d([b"EXPIRE", b"k", b"10"])
    clk.t += 3
    assert d([b"INCR", b"k"]) == INT(2)
    assert d([b"TTL", b"k"]) == INT(7)

def test_incr_on_expired_starts_fresh(d, clk):
    d([b"SET", b"k", b"41"])
    d([b"EXPIRE", b"k", b"10"])
    clk.t += 11
    assert d([b"INCR", b"k"]) == INT(1)
    assert d([b"TTL", b"k"]) == INT(-1)

@pytest.mark.parametrize("sec", [b"abc", b"1.5", b" 1", b"", b"1_0"],
                         ids=["text", "float", "space", "empty", "underscore"])
def test_expire_bad_seconds(d, sec):
    d([b"SET", b"k", b"v"])
    assert d([b"EXPIRE", b"k", sec]) == ERR_VALUE
    assert d([b"TTL", b"k"]) == INT(-1)


# ---------------------------------------------------------------- списки

def test_rpush_returns_len(d):
    assert d([b"RPUSH", b"l", b"a", b"b", b"c"]) == INT(3)

def test_rpush_accumulates(d):
    d([b"RPUSH", b"l", b"a"])
    assert d([b"RPUSH", b"l", b"b", b"c"]) == INT(3)

def test_rpush_order(d):
    d([b"RPUSH", b"l", b"a", b"b", b"c"])
    assert d([b"LRANGE", b"l", b"0", b"-1"]) == ARR(b"a", b"b", b"c")

def test_lpush_multi_reverses(d):
    assert d([b"LPUSH", b"l", b"x", b"y"]) == INT(2)
    assert d([b"LRANGE", b"l", b"0", b"-1"]) == ARR(b"y", b"x")

def test_lpush_then_rpush(d):
    d([b"LPUSH", b"l", b"b", b"a"])
    d([b"RPUSH", b"l", b"c"])
    assert d([b"LRANGE", b"l", b"0", b"-1"]) == ARR(b"a", b"b", b"c")

def test_lpop_value(d):
    d([b"RPUSH", b"l", b"a", b"b"])
    assert d([b"LPOP", b"l"]) == BULK(b"a")
    assert d([b"LRANGE", b"l", b"0", b"-1"]) == ARR(b"b")

def test_rpop_value(d):
    d([b"RPUSH", b"l", b"a", b"b"])
    assert d([b"RPOP", b"l"]) == BULK(b"b")
    assert d([b"LRANGE", b"l", b"0", b"-1"]) == ARR(b"a")

def test_lpop_missing(d):
    assert d([b"LPOP", b"l"]) == NIL

def test_rpop_missing(d):
    assert d([b"RPOP", b"l"]) == NIL

def test_llen(d):
    d([b"RPUSH", b"l", b"a", b"b"])
    assert d([b"LLEN", b"l"]) == INT(2)

def test_llen_missing(d):
    assert d([b"LLEN", b"l"]) == INT(0)

def test_lrange_full(d):
    d([b"RPUSH", b"l", b"a", b"b", b"c"])
    assert d([b"LRANGE", b"l", b"0", b"-1"]) == ARR(b"a", b"b", b"c")

def test_lrange_sub(d):
    d([b"RPUSH", b"l", b"a", b"b", b"c"])
    assert d([b"LRANGE", b"l", b"1", b"1"]) == ARR(b"b")

def test_lrange_missing(d):
    assert d([b"LRANGE", b"l", b"0", b"-1"]) == EMPTY_ARR

def test_lrange_negative_index_is_valid(d):
    d([b"RPUSH", b"l", b"a", b"b", b"c"])
    assert d([b"LRANGE", b"l", b"-2", b"-1"]) == ARR(b"b", b"c")

@pytest.mark.parametrize("start, stop", [
    (b"x", b"-1"), (b"0", b"x"), (b"1.0", b"-1"), (b"0", b""), (b" 0", b"-1"),
], ids=["start-text", "stop-text", "start-float", "stop-empty", "start-space"])
def test_lrange_bad_index(d, start, stop):
    d([b"RPUSH", b"l", b"a"])
    assert d([b"LRANGE", b"l", start, stop]) == ERR_VALUE

def test_empty_list_dies_wire_level(d):
    d([b"RPUSH", b"l", b"only"])
    assert d([b"EXPIRE", b"l", b"100"]) == INT(1)
    assert d([b"LPOP", b"l"]) == BULK(b"only")
    assert d([b"TTL", b"l"]) == INT(-2)
    assert d([b"LLEN", b"l"]) == INT(0)
    assert d([b"LPOP", b"l"]) == NIL

def test_list_expires(d, clk):
    d([b"RPUSH", b"l", b"a"])
    d([b"EXPIRE", b"l", b"10"])
    clk.t += 11
    assert d([b"LLEN", b"l"]) == INT(0)
    assert d([b"LRANGE", b"l", b"0", b"-1"]) == EMPTY_ARR
    assert d([b"RPUSH", b"l", b"b"]) == INT(1)


# ---------------------------------------------------------------- арность

@pytest.mark.parametrize("frame", [
    [b"ECHO"], [b"ECHO", b"a", b"b"],
    [b"SET"], [b"SET", b"k"],
    [b"GET"], [b"GET", b"k", b"x"],
    [b"INCR"], [b"INCR", b"k", b"1"],
    [b"DECR"], [b"DECR", b"k", b"1"],
    [b"INCRBY"], [b"INCRBY", b"k"], [b"INCRBY", b"k", b"1", b"2"],
    [b"DECRBY"], [b"DECRBY", b"k"], [b"DECRBY", b"k", b"1", b"2"],
    [b"DEL"],
    [b"EXPIRE"], [b"EXPIRE", b"k"], [b"EXPIRE", b"k", b"1", b"2"],
    [b"TTL"], [b"TTL", b"k", b"x"],
    [b"LPUSH"], [b"LPUSH", b"k"],
    [b"RPUSH"], [b"RPUSH", b"k"],
    [b"LPOP"], [b"LPOP", b"k", b"x"],
    [b"RPOP"], [b"RPOP", b"k", b"x"],
    [b"LLEN"], [b"LLEN", b"k", b"x"],
    [b"LRANGE"], [b"LRANGE", b"k"], [b"LRANGE", b"k", b"0"], [b"LRANGE", b"k", b"0", b"1", b"2"],
], ids=lambda f: b" ".join(f).decode())
def test_arity(d, frame):
    assert d(frame) == ERR_LEN(frame[0])

def test_arity_is_case_insensitive_in_name(d):
    assert d([b"Echo"]) == ERR_LEN(b"echo")

def test_arity_error_has_no_side_effect(d):
    d([b"SET", b"k"])
    assert d([b"GET", b"k"]) == NIL


# ---------------------------------------------------------------- WRONGTYPE

AS_LIST = [b"RPUSH", b"k", b"a"]
AS_STR  = [b"SET",   b"k", b"v"]

@pytest.mark.parametrize("setup, frame", [
    (AS_LIST, [b"GET",    b"k"]),
    (AS_LIST, [b"INCR",   b"k"]),
    (AS_LIST, [b"DECR",   b"k"]),
    (AS_LIST, [b"INCRBY", b"k", b"1"]),
    (AS_LIST, [b"DECRBY", b"k", b"1"]),
    (AS_STR,  [b"LPUSH",  b"k", b"a"]),
    (AS_STR,  [b"RPUSH",  b"k", b"a"]),
    (AS_STR,  [b"LPOP",   b"k"]),
    (AS_STR,  [b"RPOP",   b"k"]),
    (AS_STR,  [b"LLEN",   b"k"]),
    (AS_STR,  [b"LRANGE", b"k", b"0", b"-1"]),
], ids=["GET-on-list", "INCR-on-list", "DECR-on-list", "INCRBY-on-list", "DECRBY-on-list",
        "LPUSH-on-str", "RPUSH-on-str", "LPOP-on-str", "RPOP-on-str", "LLEN-on-str", "LRANGE-on-str"])
def test_wrongtype(d, setup, frame):
    d(setup)
    assert d(frame) == WRONGTYPE

def test_wrongtype_does_not_destroy_value(d):
    d(AS_LIST)
    d([b"INCR", b"k"])
    assert d([b"LRANGE", b"k", b"0", b"-1"]) == ARR(b"a")
    d([b"DEL", b"k"])
    d(AS_STR)
    d([b"LPUSH", b"k", b"x"])
    assert d([b"GET", b"k"]) == BULK(b"v")



def test_set_over_list_is_ok(d):
    d(AS_LIST)
    assert d([b"SET", b"k", b"v"]) == OK
    assert d([b"GET", b"k"]) == BULK(b"v")
    assert d([b"LLEN", b"k"]) == WRONGTYPE

def test_ttl_expire_del_on_list(d):
    d(AS_LIST)
    assert d([b"TTL", b"k"]) == INT(-1)
    assert d([b"EXPIRE", b"k", b"10"]) == INT(1)
    assert d([b"TTL", b"k"]) == INT(10)
    assert d([b"DEL", b"k"]) == INT(1)
    assert d([b"LLEN", b"k"]) == INT(0)
