import os, sys, tempfile
here = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(here, "..", "tools"))
import p3fes_subs as S

def test_moved_movies_follow():
    S.movies = lambda iso: [("A", 100, 10), ("B", 110, 20), ("A", 500, 5)]
    d = tempfile.mkdtemp()
    open(os.path.join(d, "active.movies"), "w").write("B 110 9000 25\nbad line\n")
    moved, text = S.read_moved(os.path.join(d, "active.movies"))
    assert moved == {("B", 110): (9000, 25)}
    S.write_movies("x", d, moved)
    rows = open(os.path.join(d, "movies.txt")).read().split("\n")[:-1]
    assert rows == ["A 100 10", "A 500 5", "B 9000 25"]
    assert S.read_moved(os.path.join(d, "none")) == ({}, "")
    S.write_movies("x", d)
    assert "B 110 20" in open(os.path.join(d, "movies.txt")).read()

if __name__ == "__main__":
    test_moved_movies_follow(); print("ok")
