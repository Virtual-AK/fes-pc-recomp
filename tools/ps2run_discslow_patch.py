"""Slow-disc experiment for the PS2 Web Recomp runtime (research tool, see docs/known-issues.md).

The simulated disc finishes a read after 0.4 ms plus 0.2 to 0.25 ms per sector (the game's own reads go through cdvdfsv.cpp) and has no seek time, much faster than a console's disc drive.
With PS2_DISC_SLOW=N (every read takes N times as long per sector) and PS2_DISC_SEEK_MS=M (M extra milliseconds per read) in
~/.p3fes-window-env the reads take longer, like a real drive. Without the variables nothing changes. Used to find out whether a game step
that runs in a different order than on a console depends on how fast loads finish.

Run in the ps2-web-recomp folder:  python3 ps2run_discslow_patch.py [folder]
(patches runtime/src/iop/cdvd.cpp and cdvdfsv.cpp; idempotent; refuses unknown source)
"""
import sys

root = sys.argv[1] if len(sys.argv) > 1 else '.'

SLOW_CODE = """    // ps2run_discslow_patch.py: PS2_DISC_SLOW (times longer per sector) and PS2_DISC_SEEK_MS (extra milliseconds per read)
    static double slow = -1.0, seek_ms = 0.0;
    if (slow < 0.0) {
        const char *s = std::getenv("PS2_DISC_SLOW");
        const char *k = std::getenv("PS2_DISC_SEEK_MS");
        slow = (s && *s) ? std::atof(s) : 1.0;
        if (slow < 1.0) slow = 1.0;
        seek_ms = (k && *k) ? std::atof(k) : 0.0;
        if (seek_ms < 0.0) seek_ms = 0.0;
        if (slow != 1.0 || seek_ms > 0.0) std::fprintf(stderr, "[disc] slow disc (%s): x%g per sector, +%g ms per read\\n", "FILE", slow, seek_ms);
    }
    return usec_to_cycles(400 + static_cast<std::uint64_t>(seek_ms * 1000.0)) +
           static_cast<std::uint64_t>(sectors) * usec_to_cycles(static_cast<std::uint64_t>(PER * slow));
"""
FILES = [
    ('runtime/src/iop/cdvd.cpp', '#include <cstdio>\n', '#include <cstdio>\n#include <cstdlib>\n',
     'std::uint64_t read_cycles(std::uint32_t sectors) {\n    return usec_to_cycles(400) + static_cast<std::uint64_t>(sectors) * usec_to_cycles(250);\n}\n',
     'std::uint64_t read_cycles(std::uint32_t sectors) {\n', '250.0', 'cdvd'),
    ('runtime/src/iop/cdvdfsv.cpp', '#include <cstdio>\n', '#include <cstdio>\n#include <cstdlib>\n',
     'std::uint64_t delay(std::uint32_t sectors) { return usec_to_cycles(400) + static_cast<std::uint64_t>(sectors) * usec_to_cycles(200); }\n',
     'std::uint64_t delay(std::uint32_t sectors) {\n', '200.0', 'cdvdfsv'),
]

done, texts = 0, {}
for rel, inc_old, inc_new, fn_old, fn_head, per, tag in FILES:
    try:
        with open(root + '/' + rel, newline='') as fh:
            text = fh.read()
    except OSError:
        print("PATCH NOT APPLIED: cannot read " + rel)
        raise SystemExit(1)
    crlf = '\r\n' in text
    t = text.replace('\r\n', '\n')
    if 'PS2_DISC_SLOW' in t:
        continue
    for old in (inc_old, fn_old):
        if t.count(old) != 1:
            print("PATCH NOT APPLIED: %s does not look like the expected source (cannot find: %s)" % (rel, old.strip().splitlines()[0][:60]))
            raise SystemExit(1)
    t = t.replace(inc_old, inc_new)
    t = t.replace(fn_old, fn_head + SLOW_CODE.replace('FILE', tag).replace('PER', per) + '}\n')
    texts[rel] = (t, crlf)
    done += 1
if not done:
    print("already patched")
    raise SystemExit
for rel, (t, crlf) in texts.items():
    with open(root + '/' + rel, 'w', newline='') as fh:
        fh.write(t.replace('\n', '\r\n') if crlf else t)
print("patched (%d files)" % done)
