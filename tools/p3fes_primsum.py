"""List the biggest shapes in a PS2_TRACE_PRIM file with their real screen boxes. Numbers only, no game content.
Usage: python3 p3fes_primsum.py prim25077.txt [--top 30] [--tme 0|1|any] [--ctx 0|1|any] [--min-area 100] [--detail N,N,..] [--range A,B] [--hist]
Needs a trace made with ps2run_trace_patch6.py (the version that prints ofx and ofy).
Each output line: order number, type, ctx, tme, blend (alpha), test, colour of the first corner, screen box x0,y0-x1,y1, box area, frame buffer (frame), zbuf.
"""
import re, sys

HDR = re.compile(r'^\[prim\] f(\d+) type=(\d+) iip=(\d+) tme=(\d+) fge=(\d+) abe=(\d+) fst=(\d+) ctx=(\d+) tbp=(\w+) psm=(\w+) .*?alpha=(\w+) test=(\w+) clamp=(\w+) frame=(\w+) zbuf=(\w+)(?: ofx=(\d+) ofy=(\d+))?')
VTX = re.compile(r'^\[prim\]\s+v(\d+) x=(\d+) y=(\d+) z=(\d+) rgba=([0-9A-Fa-f]{8})')


def parse(lines):
    """Return a list of dicts, one per shape, in the order they were drawn."""
    prims, cur = [], None
    for ln in lines:
        m = HDR.match(ln)
        if m:
            cur = dict(n=len(prims), frame_no=int(m[1]), type=int(m[2]), iip=int(m[3]), tme=int(m[4]), fge=int(m[5]), abe=int(m[6]), ctx=int(m[8]), tbp=m[9], psm=m[10],
                       alpha=m[11], test=m[12], clamp=m[13], fb=m[14], zbuf=m[15], ofx=int(m[16] or 0), ofy=int(m[17] or 0), v=[], raw=ln)
            prims.append(cur)
            continue
        m = VTX.match(ln)
        if m and cur is not None:
            cur['v'].append((int(m[2]), int(m[3]), int(m[4]), m[5].upper()))
    return prims


def box(p):
    """Screen box (x0, y0, x1, y1) in pixels after removing the GS offset; None when there are no corners."""
    if not p['v']:
        return None
    xs = [(v[0] - p['ofx']) / 16.0 for v in p['v']]
    ys = [(v[1] - p['ofy']) / 16.0 for v in p['v']]
    return min(xs), min(ys), max(xs), max(ys)


def area(b):
    return (b[2] - b[0]) * (b[3] - b[1])


def select(prims, tme='any', ctx='any', min_area=0.0):
    out = []
    for p in prims:
        b = box(p)
        if b is None:
            continue
        if tme != 'any' and p['tme'] != int(tme):
            continue
        if ctx != 'any' and p['ctx'] != int(ctx):
            continue
        a = area(b)
        if a < min_area:
            continue
        out.append((a, p, b))
    out.sort(key=lambda t: -t[0])
    return out


def main(argv):
    if not argv or argv[0].startswith('--'):
        print(__doc__); return 1
    path, top, tme, ctx, mn, detail = argv[0], 30, '0', 'any', 100.0, []
    rng = None
    hist = False
    top_hist = 25
    if '--hist' in argv:
        hist = True
        argv = [a for a in argv if a != '--hist']
    i = 1
    while i < len(argv) - 1:
        k, val = argv[i], argv[i + 1]
        if k == '--top': top = int(val); top_hist = val
        elif k == '--tme': tme = val
        elif k == '--ctx': ctx = val
        elif k == '--min-area': mn = float(val)
        elif k == '--range': rng = [int(x) for x in val.split(',')]
        elif k == '--detail': detail = [int(x) for x in val.split(',')]
        i += 2
    prims = parse(open(path, errors='replace').read().splitlines())
    if hist:
        groups = {}
        for q in prims:
            b = box(q)
            a = area(b) if b else 0.0
            key = (q['type'], q['tme'], q['ctx'], q['abe'], q['fb'], q['tbp'] if q['tme'] else '-')
            g = groups.setdefault(key, [0, 0.0, 0.0])
            g[0] += 1
            g[1] += a
            g[2] = max(g[2], a)
        total = sum(g[1] for g in groups.values()) or 1.0
        print("%d shapes, bounding-box area sum %.0f pixels (a 640x448 screen is 286720)" % (len(prims), total))
        rows = sorted(groups.items(), key=lambda kv: -kv[1][1])
        for key, g in rows[:int(top_hist)]:
            print("type=%d tme=%d ctx=%d abe=%d fb=%s tbp=%s  count=%d  area_sum=%.0f (%.1f%%)  biggest=%.0f" % (
                key[0], key[1], key[2], key[3], key[4], key[5], g[0], g[1], 100.0 * g[1] / total, g[2]))
        return 0
    if rng:
        for p in prims[rng[0]:rng[1]]:
            b = box(p)
            bs = "%d,%d-%d,%d" % b if b else "-"
            print("#%d t%d c%d tme%d abe%d tbp=%s alpha=%s test=%s fb=%s zmsk=%d box=%s col=%s" % (
                p['n'], p['type'], p['ctx'], p['tme'], p['abe'], p['tbp'] if p['tme'] else '-', p['alpha'], p['test'], p['fb'],
                (int(p['zbuf'], 16) >> 32) & 1, bs, p['v'][0][3] if p['v'] else '-'))
        return 0
    if detail:
        for n in detail:
            if 0 <= n < len(prims):
                p = prims[n]
                print("#%d type=%d iip=%d tme=%d fge=%d abe=%d ctx=%d alpha=%s test=%s clamp=%s fb=%s zbuf=%s offset=%d,%d" % (
                    n, p['type'], p['iip'], p['tme'], p['fge'], p['abe'], p['ctx'], p['alpha'], p['test'], p['clamp'], p['fb'], p['zbuf'], p['ofx'], p['ofy']))
                tail = p['raw'].find(' pmc=')
                if tail >= 0:
                    print("    switches:" + p['raw'][tail:].rstrip())
                for i, v in enumerate(p['v']):
                    print("    corner %d: screen %.1f,%.1f z=%d rgba=%s" % (i, (v[0] - p['ofx']) / 16.0, (v[1] - p['ofy']) / 16.0, v[2], v[3]))
        return 0
    print("%d shapes in file; ofx/ofy present: %s" % (len(prims), any(p['ofx'] or p['ofy'] for p in prims)))
    rows = select(prims, tme, ctx, mn)
    print("showing the %d biggest of %d (tme=%s ctx=%s min-area=%g)" % (min(top, len(rows)), len(rows), tme, ctx, mn))
    for a, p, b in rows[:top]:
        col = p['v'][0][3] if p['v'] else '-'
        print("#%d type=%d ctx=%d tme=%d abe=%d alpha=%s test=%s rgba=%s box=%d,%d-%d,%d area=%d fb=%s zbuf=%s" % (
            p['n'], p['type'], p['ctx'], p['tme'], p['abe'], p['alpha'], p['test'], col, b[0], b[1], b[2], b[3], a, p['fb'], p['zbuf']))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
