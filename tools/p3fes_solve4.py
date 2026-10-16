#!/usr/bin/env python3
"""Work out how the pixels inside one 32x16 block of a 4-bit texture are ordered in the stream.

Input: cost.txt from `p3fes_rmd.py textures FILE.rws -o DIR --cost NAME,NAME` (numbers only).
It tries to place the 512 stream positions on a 32x16 grid so that grid neighbours are positions
whose values were alike in the same blocks. Prints the grid and compares it with the standard GS layout.
"""
import random, sys, math

W, H = 32, 16


def load(path):
    cost = {}
    with open(path) as fh:
        head = fh.readline().split()
        block = int(head[1])
        for line in fh:
            f = line.split()
            p = int(f[0])
            cost[p] = {int(a.split(":")[0]): float(a.split(":")[1]) for a in f[1:]}
    return block, cost


def solve(block, cost, iters=400000, seed=1, w=W, h=H):
    rnd = random.Random(seed)
    big = max(c for d in cost.values() for c in d.values()) * 1.5 + 1

    def c(p, q):
        a = cost[p].get(q)
        b = cost[q].get(p)
        if a is None and b is None:
            return big
        return min(x for x in (a, b) if x is not None)
    cells = list(range(block))
    rnd.shuffle(cells)                      # cells[pos] = stream position at grid pos
    where = {p: i for i, p in enumerate(cells)}

    def nbrs(i):
        x, y = i % w, i // w
        if x > 0: yield i - 1
        if x < w - 1: yield i + 1
        if y > 0: yield i - w
        if y < h - 1: yield i + w

    def local(i, p):
        return sum(c(p, cells[j]) for j in nbrs(i))
    t0 = typical = sum(min(d.values()) for d in cost.values()) / len(cost) * 3 + 1e-3
    for it in range(iters):
        T = t0 * (0.02 ** (it / iters))
        i, j = rnd.randrange(block), rnd.randrange(block)
        if i == j:
            continue
        pi, pj = cells[i], cells[j]
        before = local(i, pi) + local(j, pj)
        cells[i], cells[j] = pj, pi
        after = local(i, pj) + local(j, pi)
        d = after - before
        if d > 0 and rnd.random() >= math.exp(-d / T):
            cells[i], cells[j] = pi, pj
    total = sum(c(cells[i], cells[j]) for i in range(block) for j in nbrs(i) if j > i)
    return cells, total


def standard():
    """Stream position -> grid position for the standard GS 4-bit block (x 0-31, y 0-15)."""
    import p3fes_rmd as R
    m = {}
    for y in range(16):
        for x in range(32):
            m[R.t4_index(x, y, 4) % 512] = y * W + x
    return m


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return
    block, cost = load(sys.argv[1])
    best = None
    for seed in range(1, 6):
        cells, total = solve(block, cost, seed=seed)
        print("seed %d: total neighbour cost %.1f" % (seed, total))
        if best is None or total < best[1]:
            best = (cells, total)
    cells, total = best
    print("\nGrid (each number is the stream position that lands there), 32 across, 16 down:")
    for y in range(H):
        print(" ".join("%3d" % cells[y * W + x] for x in range(W)))
    print("\nstream position -> (x, y) up to flips/mirror of the grid:")
    pos = {p: (i % W, i // W) for i, p in enumerate(cells)}
    print(" ".join("%d:(%d,%d)" % (p, *pos[p]) for p in range(0, block)))
    try:
        std = standard()
        best_match = 0
        for fx in (0, 1):
            for fy in (0, 1):
                n = 0
                for p in range(block):
                    x, y = pos[p]
                    x = W - 1 - x if fx else x
                    y = H - 1 - y if fy else y
                    n += (y * W + x) == std[p]
                best_match = max(best_match, n)
        print("\nmatches with the standard GS block layout: %d of %d positions" % (best_match, block))
    except Exception as e:
        print("(could not compare with the standard layout: %s)" % e)


if __name__ == "__main__":
    main()
