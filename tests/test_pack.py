import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools"))
import p3fes_modmap as M

# neighbouring free extents join, the smallest file goes first, the biggest are the ones left out
# 100..200 holds 100 sectors, 300..320 holds 20: b (20) -> smallest extent that fits = 300..320, d (45), c (50) -> 100..200, a (60) does not fit
placed, out = M.pack_extents([(100, 150), (150, 200), (300, 320)], [("a", 60, None), ("b", 20, None), ("c", 50, None), ("d", 45, None)])
assert placed == {"b": 300, "d": 100, "c": 145}, placed
assert out == ["a"], out
# nothing may end after its limit
placed, out = M.pack_extents([(0, 1000)], [("x", 100, 150), ("y", 100, 90), ("z", 10, 5000)])
assert placed == {"z": 0, "x": 10} and out == ["y"], (placed, out)
# files fill an extent without overlapping
placed, out = M.pack_extents([(0, 100)], [(i, 10, None) for i in range(10)])
assert sorted(placed.values()) == list(range(0, 100, 10)) and not out

# plan_moves: a moved file may take the room an earlier moved file leaves, and the limit of its CVM is respected
S = 2048
base = 1000
A = {"move": True, "rec": (0, base * S), "offset": (base + 10) * S, "orig": 30 * S, "data": b"x" * (35 * S)}    # grows: its own room is too small
B = {"move": True, "rec": (0, base * S), "offset": (base + 40) * S, "orig": 30 * S, "data": b"y" * (20 * S)}    # shrinks: fits in the room of A or B
placed = M.plan_moves([A, B], None, (base + 100) * S)
assert id(B) in placed and id(A) in placed
a0, b0 = placed[id(A)], placed[id(B)]
assert not (a0 < b0 + 20 and b0 < a0 + 35), "overlap"
assert min(a0, b0) < base + 100, "the room of the old copies is used before the end of the image"
M.LIMIT_SECTORS, keep = 50, M.LIMIT_SECTORS      # nothing may end beyond sector 50 of its CVM (base + 50)
placed = M.plan_moves([A, B], None, (base + 100) * S)
assert id(A) not in placed, "too big for the limit"
M.LIMIT_SECTORS = keep
print("ok pack: files go into the room their old copies leave, biggest left out first, the CVM limit holds")
