#!/usr/bin/env python3
"""
p3fes_textsurvey.py - find out how the game stores its text (step 1 of a text tool).

Run this on the folder that p3fes_unpack.py made. It only READS. It looks at every
file whose name ends in .BMD (the game's message files) plus any file whose first
bytes say "MSG1", and writes a report with:
  - how many there are, their sizes, and which header "magic" words they use
  - the first 96 bytes of a few samples (as hex), so the layout can be worked out
  - which byte values the text seems to use (to guess the character encoding)
The report contains only short technical snippets of the game's data (hex numbers),
no readable story text, so it is safe to attach to a GitHub issue.

Usage (from a Command Prompt in the folder that holds this script):
    py p3fes_textsurvey.py "C:\\p3fes\\extracted"
Standard library only, Python 3.8+.
"""
import argparse, collections, json, os, sys, time


def main():
    ap = argparse.ArgumentParser(description="Survey the game's message (.BMD) files.")
    ap.add_argument("folder")
    ap.add_argument("-o", "--out", help="report file (default: text.survey.json next to this script)")
    ap.add_argument("--samples", type=int, default=6, help="samples to keep per kind (default 6)")
    args = ap.parse_args()
    root = os.path.abspath(args.folder)
    if not os.path.isdir(root):
        sys.exit(f"Error: {root} is not a folder.")
    t0 = time.time()
    exts = collections.Counter()
    found = []
    seen = 0
    print("Scanning... (this prints a count every 500 files; it can take a minute or two)")
    for dp, _, names in os.walk(root):
        for n in names:
            seen += 1
            if seen % 500 == 0:
                sys.stderr.write("\r  %d files checked, %d message files found" % (seen, len(found)))
                sys.stderr.flush()
            ext = os.path.splitext(n)[1].lower() or "(none)"
            exts[ext] += 1
            p = os.path.join(dp, n)
            is_bmd = ext == ".bmd"
            if not is_bmd and ext in (".tmx", ".adx", ".afs", ".sfd", ".pss", ".pss", ".png", ".wav"):
                continue
            try:
                with open(p, "rb") as fh:
                    head = fh.read(96)
                size = os.path.getsize(p)
            except OSError:
                continue
            msg = b"MSG1" in head[:32]
            if is_bmd or msg:
                found.append((os.path.relpath(p, root), size, head, p))
    sys.stderr.write("\r" + " " * 70 + "\r")
    kinds = collections.Counter()
    samples = collections.defaultdict(list)
    for rel, size, head, p in found:
        key = "magic@8=%s" % head[8:12].decode("ascii", "replace") if len(head) >= 12 else "short"
        kinds[key] += 1
        if len(samples[key]) < args.samples:
            samples[key].append({"file": rel, "size": size, "head96": head.hex(" ")})
    # byte histogram over a sample of files: which values appear in the data parts
    hist = collections.Counter()
    for rel, size, head, p in found[:300]:
        try:
            with open(p, "rb") as fh:
                data = fh.read(65536)
        except OSError:
            continue
        hist.update(data[64:])
    top = [(b, c) for b, c in hist.most_common(40)]
    report = {
        "files_scanned_extensions": dict(exts.most_common()),
        "message_files": len(found),
        "kinds": dict(kinds),
        "total_bytes": sum(f[1] for f in found),
        "samples": samples,
        "top_byte_values_in_data": [["%02X" % b, c] for b, c in top],
    }
    out = args.out or "text.survey.json"
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=1)
    print("=" * 60)
    print(f"Found {len(found)} message files in {time.time() - t0:.0f}s")
    for k, v in kinds.most_common():
        print(f"  {k}: {v}")
    print("Report written to: " + os.path.abspath(out))
    print("Attach that file to your reply. It holds only technical hex snippets.")

if __name__ == "__main__":
    main()
