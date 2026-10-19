"""Checks the launcher's disc and state logic with tiny synthetic disc images (no game data).
Run:  python3 -m unittest tests/test_launcher.py"""
import os, struct, sys, tempfile, unittest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools", "launcher"))
import p3fes_launcher as L


def make_iso(path, boot, vol_blocks=40, real_blocks=40):
    b = bytearray(real_blocks * 2048)
    pvd = bytearray(2048); pvd[0] = 1; pvd[1:6] = b"CD001"; pvd[6] = 1
    struct.pack_into("<I", pvd, 80, vol_blocks)
    root = bytearray(34); root[0] = 34
    struct.pack_into("<I", root, 2, 20); struct.pack_into("<I", root, 10, 2048); root[25] = 2; root[32] = 1
    pvd[156:190] = root
    b[16 * 2048:17 * 2048] = pvd
    cnf = ("BOOT2 = cdrom0:\\%s;1\nVER = 1.00\n" % boot).encode()
    nm = b"SYSTEM.CNF;1"
    rec = bytearray(33 + len(nm) + (len(nm) % 2 == 0)); rec[0] = len(rec)
    struct.pack_into("<I", rec, 2, 24); struct.pack_into("<I", rec, 10, len(cnf)); rec[32] = len(nm); rec[33:33 + len(nm)] = nm
    b[20 * 2048:20 * 2048 + len(rec)] = rec
    b[24 * 2048:24 * 2048 + len(cnf)] = cnf
    with open(path, "wb") as f:
        f.write(b)


class DiscChecks(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()

    def test_usa_disc_ok(self):
        p = os.path.join(self.d, "a.iso"); make_iso(p, "SLUS_216.21")
        r = L.check_disc(p)
        self.assertEqual((r["region"], r["game_id"], r["contents"]), ("NTSC-U", "SLUS_216.21", "ok"))

    def test_pal_disc_region(self):
        p = os.path.join(self.d, "b.iso"); make_iso(p, "SLES_123.45")
        self.assertEqual(L.check_disc(p)["region"], "PAL")

    def test_short_file(self):
        p = os.path.join(self.d, "c.iso"); make_iso(p, "SLUS_216.21", vol_blocks=100, real_blocks=40)
        self.assertEqual(L.check_disc(p)["contents"], "short")

    def test_not_a_disc(self):
        p = os.path.join(self.d, "d.iso")
        with open(p, "wb") as f:
            f.write(os.urandom(100000))
        self.assertEqual(L.check_disc(p)["contents"], "unreadable")

    def test_modded_name(self):
        p = os.path.join(self.d, "p3fes_modded.iso"); make_iso(p, "SLUS_216.21")
        self.assertEqual(L.check_disc(p)["contents"], "modified")


if __name__ == "__main__":
    unittest.main()
