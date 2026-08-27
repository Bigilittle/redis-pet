import pytest
from storage import Storage
from errors import WrongType


# ---------------------------------------------------------------- строки

def test_get_missing(store):
    assert store.get(b"k") is None

def test_set_get(store):
    store.set(b"k", b"v")
    assert store.get(b"k") == b"v"

def test_set_overwrites(store):
    store.set(b"k", b"v")
    store.set(b"k", b"w")
    assert store.get(b"k") == b"w"

def test_dunder_get_set_del_contains(store):
    store[b"k"] = b"v"
    assert b"k" in store
    assert store[b"k"] == b"v"
    del store[b"k"]
    assert b"k" not in store
    assert store[b"k"] is None

def test_values_are_binary_safe(store):
    store.set(b"k", b"\x00\r\n\xff")
    assert store.get(b"k") == b"\x00\r\n\xff"

def test_instances_are_independent(clk):
    a, b = Storage(clock=clk), Storage(clock=clk)
    a.set(b"k", b"v")
    assert b.get(b"k") is None


# ---------------------------------------------------------------- delete

def test_delete_returns_count(store):
    store.set(b"k", b"v")
    assert store.delete(b"k") == 1
    assert store.delete(b"k") == 0
    assert store.get(b"k") is None

def test_delete_missing(store):
    assert store.delete(b"ghost") == 0

def test_delete_list(store):
    store.rpush(b"l", b"a")
    assert store.delete(b"l") == 1
    assert store.llen(b"l") == 0


# ---------------------------------------------------------------- update

def test_update_creates_without_ttl(store):
    store.update(b"k", b"1")
    assert store.get(b"k") == b"1"
    assert store.ttl(b"k") == -1

def test_update_keeps_ttl(store, clk):
    store.set(b"k", b"1")
    store.expire(b"k", 10)
    clk.t += 3
    store.update(b"k", b"2")
    assert store.get(b"k") == b"2"
    assert store.ttl(b"k") == 7

def test_update_on_expired_starts_fresh(store, clk):
    store.set(b"k", b"1")
    store.expire(b"k", 10)
    clk.t += 10
    store.update(b"k", b"2")
    assert store.get(b"k") == b"2"
    assert store.ttl(b"k") == -1


# ---------------------------------------------------------------- push / pop / len

def test_rpush_order_and_len(store):
    assert store.rpush(b"l", b"a") == 1
    assert store.rpush(b"l", b"b", b"c") == 3
    assert store.lrange(b"l", 0, -1) == [b"a", b"b", b"c"]

def test_lpush_reverses_and_len(store):
    assert store.lpush(b"l", b"a") == 1
    assert store.lpush(b"l", b"b", b"c") == 3
    assert store.lrange(b"l", 0, -1) == [b"c", b"b", b"a"]

def test_push_without_values_is_programming_error(store):
    with pytest.raises(ValueError):
        store.lpush(b"l")
    with pytest.raises(ValueError):
        store.rpush(b"l")
    assert store.llen(b"l") == 0          # ключ не создан

def test_lpop_rpop(store):
    store.rpush(b"l", b"a", b"b", b"c")
    assert store.lpop(b"l") == b"a"
    assert store.rpop(b"l") == b"c"
    assert store.lrange(b"l", 0, -1) == [b"b"]

def test_pop_missing(store):
    assert store.lpop(b"l") is None
    assert store.rpop(b"l") is None

def test_pop_last_element_removes_key(store):
    store.rpush(b"l", b"only")
    store.expire(b"l", 100)
    assert store.lpop(b"l") == b"only"
    assert b"l" not in store
    assert store.ttl(b"l") == -2
    assert store.llen(b"l") == 0
    assert store.lrange(b"l", 0, -1) == []
    # rpop — симметрично
    store.rpush(b"l", b"only")
    assert store.rpop(b"l") == b"only"
    assert b"l" not in store

def test_llen(store):
    assert store.llen(b"l") == 0
    store.rpush(b"l", b"a", b"b")
    assert store.llen(b"l") == 2

def test_push_values_are_not_copied_or_altered(store):
    store.rpush(b"l", b"", b"\x00\r\n")
    assert store.lrange(b"l", 0, -1) == [b"", b"\x00\r\n"]


# ---------------------------------------------------------------- LRANGE

FIVE = [b"a", b"b", b"c", b"d", b"e"]

@pytest.mark.parametrize("start, stop, expected", [
    ( 0,  -1, FIVE),                     # весь список
    ( 0,   4, FIVE),                     # точные границы
    ( 0,   0, [b"a"]),                   # один первый
    (-1,  -1, [b"e"]),                   # один последний
    (-2,  -1, [b"d", b"e"]),             # хвост
    ( 1,   3, [b"b", b"c", b"d"]),       # середина
    ( 2,  -2, [b"c", b"d"]),             # смешанные знаки
    ( 0, 100, FIVE),                     # stop за концом — клампится
    (-100, 1, [b"a", b"b"]),             # start за началом — клампится в 0
    (-100, -1, FIVE),                    # оба за пределами слева/справа
    ( 3,   1, []),                       # start > stop
    ( 5,  10, []),                       # start == len
    ( 6,  10, []),                       # start > len
    ( 0,  -6, []),                       # stop уходит за начало (-6+5 = -1 < 0)
    ( 0,  -7, []),                       # полоса -(len+2)..-2len: срез [0:-1] дал бы 4 элемента
    ( 0, -10, []),                       # нижний край полосы
    ( 2,  -8, []),                       # та же полоса с ненулевым start
    (-100, -6, []),                      # start→0, stop→-1 → start > stop
    (-1,   0, []),                       # start=4 > stop=0
    ( 4,  -1, [b"e"]),                   # последний через положительный start
    (-5,   0, [b"a"]),                   # start == -len
    (-6,   0, [b"a"]),                   # start < -len → 0
], ids=lambda v: repr(v) if isinstance(v, int) else None)
def test_lrange_zoo(store, start, stop, expected):
    store.rpush(b"l", *FIVE)
    assert store.lrange(b"l", start, stop) == expected

def test_lrange_missing(store):
    assert store.lrange(b"l", 0, -1) == []
    assert store.lrange(b"l", -100, 100) == []

def test_lrange_single_element(store):
    store.rpush(b"l", b"x")
    assert store.lrange(b"l", 0, -1) == [b"x"]
    assert store.lrange(b"l", -1, -1) == [b"x"]
    assert store.lrange(b"l", 1, -1) == []
    assert store.lrange(b"l", 0, -2) == []

def test_lrange_returns_copy(store):
    store.rpush(b"l", b"a")
    out = store.lrange(b"l", 0, -1)
    out.append(b"zzz")
    assert store.llen(b"l") == 1


# ---------------------------------------------------------------- типы

@pytest.mark.parametrize("op", [
    lambda s: s.get(b"k"),
    lambda s: s[b"k"],
], ids=["get", "getitem"])
def test_string_ops_on_list_raise(store, op):
    store.rpush(b"k", b"a")
    with pytest.raises(WrongType):
        op(store)

@pytest.mark.parametrize("op", [
    lambda s: s.lpush(b"k", b"a"),
    lambda s: s.rpush(b"k", b"a"),
    lambda s: s.lpop(b"k"),
    lambda s: s.rpop(b"k"),
    lambda s: s.llen(b"k"),
    lambda s: s.lrange(b"k", 0, -1),
], ids=["lpush", "rpush", "lpop", "rpop", "llen", "lrange"])
def test_list_ops_on_string_raise(store, op):
    store.set(b"k", b"v")
    with pytest.raises(WrongType):
        op(store)
    assert store.get(b"k") == b"v"        
def test_set_replaces_list(store):
    store.rpush(b"k", b"a")
    store.set(b"k", b"v")
    assert store.get(b"k") == b"v"
    with pytest.raises(WrongType):
        store.llen(b"k")

def test_set_over_list_drops_ttl(store):
    store.rpush(b"k", b"a")
    store.expire(b"k", 10)
    store.set(b"k", b"v")
    assert store.ttl(b"k") == -1

def test_type_agnostic_ops_on_list(store):
    store.rpush(b"k", b"a")
    assert b"k" in store
    assert store.ttl(b"k") == -1
    assert store.expire(b"k", 10) is True
    assert store.ttl(b"k") == 10
    assert store.delete(b"k") == 1


# ---------------------------------------------------------------- EXPIRE / TTL: ленивая очистка

def test_ttl_missing(store):
    assert store.ttl(b"k") == -2

def test_ttl_persistent(store):
    store.set(b"k", b"v")
    assert store.ttl(b"k") == -1

def test_expire_returns_bool(store):
    assert store.expire(b"ghost", 10) is False
    store.set(b"k", b"v")
    assert store.expire(b"k", 10) is True

def test_expire_then_ttl(store):
    store.set(b"k", b"v")
    store.expire(b"k", 10)
    assert store.ttl(b"k") == 10

def test_ttl_counts_down(store, clk):
    store.set(b"k", b"v")
    store.expire(b"k", 10)
    clk.t += 4
    assert store.ttl(b"k") == 6

def test_ttl_rounds_up_on_fraction(store, clk):
    store.set(b"k", b"v")
    store.expire(b"k", 10)
    clk.t += 3.5
    assert store.ttl(b"k") == 7
    clk.t += 6.4                           
    assert store.ttl(b"k") == 1
    assert store.get(b"k") == b"v"

def test_key_alive_just_before_deadline(store, clk):
    store.set(b"k", b"v")
    store.expire(b"k", 10)
    clk.t += 9.999
    assert store.get(b"k") == b"v"
    assert b"k" in store

def test_key_dead_exactly_at_deadline(store, clk):
    store.set(b"k", b"v")
    store.expire(b"k", 10)
    clk.t += 10
    assert store.get(b"k") is None
    assert store.ttl(b"k") == -2

def test_expired_is_gone_everywhere(store, clk):
    store.set(b"k", b"v")
    store.expire(b"k", 10)
    clk.t += 11
    assert store.get(b"k") is None
    assert b"k" not in store
    assert store.ttl(b"k") == -2
    assert store.delete(b"k") == 0
    assert store.expire(b"k", 10) is False

def test_lazy_purge_actually_removes_entry(store, clk):
    store.set(b"k", b"v")
    store.expire(b"k", 10)
    clk.t += 11
    assert b"k" in store.storage          
    store.get(b"k")
    assert b"k" not in store.storage      

def test_expired_list_is_gone(store, clk):
    store.rpush(b"l", b"a")
    store.expire(b"l", 10)
    clk.t += 11
    assert store.llen(b"l") == 0
    assert store.lrange(b"l", 0, -1) == []
    assert store.lpop(b"l") is None
    assert store.rpush(b"l", b"b") == 1     
    assert store.lrange(b"l", 0, -1) == [b"b"]
    assert store.ttl(b"l") == -1

def test_expire_overrides(store, clk):
    store.set(b"k", b"v")
    store.expire(b"k", 10)
    store.expire(b"k", 100)
    clk.t += 50
    assert store.get(b"k") == b"v"
    assert store.ttl(b"k") == 50

def test_expire_shortens(store, clk):
    store.set(b"k", b"v")
    store.expire(b"k", 100)
    store.expire(b"k", 10)
    clk.t += 11
    assert store.get(b"k") is None

def test_expire_zero_and_negative_kill_now(store):
    store.set(b"k", b"v")
    assert store.expire(b"k", 0) is True
    assert store.get(b"k") is None
    store.set(b"k", b"v")
    assert store.expire(b"k", -5) is True
    assert store.get(b"k") is None

def test_set_removes_ttl(store, clk):
    store.set(b"k", b"v")
    store.expire(b"k", 10)
    store.set(b"k", b"w")
    assert store.ttl(b"k") == -1
    clk.t += 100
    assert store.get(b"k") == b"w"

def test_push_keeps_ttl(store, clk):
    store.rpush(b"l", b"a")
    store.expire(b"l", 10)
    clk.t += 3
    store.rpush(b"l", b"b")
    store.lpush(b"l", b"z")
    assert store.ttl(b"l") == 7

def test_pop_keeps_ttl_while_nonempty(store, clk):
    store.rpush(b"l", b"a", b"b")
    store.expire(b"l", 10)
    clk.t += 3
    store.lpop(b"l")
    assert store.ttl(b"l") == 7

def test_ttl_does_not_depend_on_clock_start(clk):
    clk.t = 1_000_000.5
    s = Storage(clock=clk)
    s.set(b"k", b"v")
    s.expire(b"k", 10)
    clk.t += 4
    assert s.ttl(b"k") == 6


# ---------------------------------------------------------------- next_deadline

def test_next_deadline_empty(store):
    assert store.next_deadline() is None

def test_next_deadline_no_ttl_keys(store):
    store.set(b"k", b"v")
    assert store.next_deadline() is None

def test_next_deadline_is_earliest(store, clk):
    clk.t = 100
    store.set(b"a", b"1"); store.expire(b"a", 30)
    store.set(b"b", b"1"); store.expire(b"b", 10)
    store.set(b"c", b"1"); store.expire(b"c", 20)
    assert store.next_deadline() == 110

def test_next_deadline_skips_deleted_key(store):
    store.set(b"a", b"1"); store.expire(b"a", 10)
    store.set(b"b", b"1"); store.expire(b"b", 20)
    store.delete(b"a")
    assert store.next_deadline() == 20

def test_next_deadline_skips_overridden_expire(store):
    store.set(b"a", b"1"); store.expire(b"a", 10)
    store.expire(b"a", 50)
    assert store.next_deadline() == 50     

def test_next_deadline_skips_key_reset_to_persistent(store):
    store.set(b"a", b"1"); store.expire(b"a", 10)
    store.set(b"a", b"2")                  
    assert store.next_deadline() is None

def test_next_deadline_survives_update(store):
    store.set(b"a", b"1"); store.expire(b"a", 10)
    store.update(b"a", b"2")             
    assert store.next_deadline() == 10

def test_next_deadline_is_idempotent(store):
    store.set(b"a", b"1"); store.expire(b"a", 10)
    assert store.next_deadline() == 10
    assert store.next_deadline() == 10

def test_next_deadline_drops_garbage_from_heap(store):
    store.set(b"a", b"1")
    store.expire(b"a", 10)
    store.expire(b"a", 20)
    store.expire(b"a", 30)
    store.delete(b"a")
    assert store.next_deadline() is None
    assert store.heap == []                # мусор реально выброшен, а не пропущен


# ---------------------------------------------------------------- collect_expired

def test_collect_empty_is_noop(store):
    store.collect_expired()
    assert store.next_deadline() is None

def test_collect_removes_due_keys(store, clk):
    store.set(b"a", b"1"); store.expire(b"a", 10)
    store.set(b"b", b"1"); store.expire(b"b", 20)
    store.set(b"c", b"1")                  # вечный
    clk.t = 15
    store.collect_expired()
    assert b"a" not in store.storage       # удалён физически, без касания
    assert b"b" in store.storage
    assert b"c" in store.storage
    assert store.next_deadline() == 20

def test_collect_at_exact_deadline(store, clk):
    store.set(b"a", b"1"); store.expire(b"a", 10)
    clk.t = 10
    store.collect_expired()
    assert b"a" not in store.storage

def test_collect_just_before_deadline_keeps(store, clk):
    store.set(b"a", b"1"); store.expire(b"a", 10)
    clk.t = 9.999
    store.collect_expired()
    assert b"a" in store.storage
    assert store.next_deadline() == 10

def test_collect_does_not_kill_key_reset_after_old_alarm(store, clk):
    store.set(b"k", b"old"); store.expire(b"k", 5)
    store.set(b"k", b"new")
    clk.t = 6
    store.collect_expired()
    assert store.get(b"k") == b"new"

def test_collect_does_not_kill_key_with_extended_expire(store, clk):
    store.set(b"k", b"v"); store.expire(b"k", 5)
    store.expire(b"k", 100)
    clk.t = 6
    store.collect_expired()
    assert store.get(b"k") == b"v"
    assert store.ttl(b"k") == 94

def test_collect_does_not_kill_new_key_with_same_name(store, clk):
    store.set(b"k", b"old"); store.expire(b"k", 5)
    clk.t = 6
    store.get(b"k")                        # ленивая чистка унесла старый
    store.set(b"k", b"new"); store.expire(b"k", 100)
    store.collect_expired()                # старый будильник (5) всё ещё в куче
    assert store.get(b"k") == b"new"

def test_collect_handles_lazily_purged_key(store, clk):
    store.set(b"k", b"v"); store.expire(b"k", 5)
    clk.t = 6
    assert store.get(b"k") is None         # унесено лениво
    store.collect_expired()              
    assert store.next_deadline() is None

def test_collect_many_due_at_once(store, clk):
    for i in range(50):
        k = b"k%d" % i
        store.set(k, b"v"); store.expire(k, i + 1)
    clk.t = 25
    store.collect_expired()
    assert len(store.storage) == 25
    assert store.next_deadline() == 26

def test_collect_then_lazy_agree(store, clk):
    store.set(b"a", b"1"); store.expire(b"a", 10)
    clk.t = 11
    store.collect_expired()
    assert store.ttl(b"a") == -2
    assert store.expire(b"a", 10) is False
    assert store.delete(b"a") == 0

def test_collect_list_key(store, clk):
    store.rpush(b"l", b"a"); store.expire(b"l", 10)
    clk.t = 11
    store.collect_expired()
    assert b"l" not in store.storage
