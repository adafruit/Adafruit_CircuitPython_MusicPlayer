# SPDX-FileCopyrightText: 2026 Mikey Sklar
# SPDX-License-Identifier: MIT-0
"""Test library.py under CPython on the real card's file list, with a fake vfs.
Run: python3 test_library.py [card-files.tsv]. Not for the board."""

import errno
import io
import os
import sys
import time
import types

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
from adafruit_musicplayer import library, menus  # noqa: E402

TSV = sys.argv[1] if __name__ == "__main__" and len(sys.argv) > 1 else "card-files.tsv"
CUT_OFF = "/NIN-The_Downward_Spiral/01-nine_inch_nails-mr_self_destruct.flac"  # top of card.log
BROKEN = "/Sven Väth"


class FakeFile(io.BytesIO):
    def __init__(self, vfs, path, write, data=b""):
        super().__init__(data)
        self.vfs, self.path, self.writing = vfs, path, write

    def write(self, data):
        return super().write(data.encode() if isinstance(data, str) else data)

    def close(self):
        if self.writing and not self.closed:
            self.vfs.files[self.path] = self.getvalue()
        super().close()


class FakeVfs:
    def __init__(self, paths):
        self.files = {p: b"" for p in paths}
        self.dirs = {}
        for p in paths:
            self._add(p, 0x8000)
        self._add(BROKEN + "/x.mp3", 0x8000)
        self.opens = 0
        self.lists = 0
        self.fail_write = False

    def _add(self, path, kind):
        parts = path.split("/")
        for n in range(1, len(parts)):
            folder = "/".join(parts[:n]) or "/"
            child = (parts[n], 0x4000 if n < len(parts) - 1 else kind)
            self.dirs.setdefault(folder, {})[child[0]] = child[1]

    def ilistdir(self, path):
        self.lists += 1
        if path == BROKEN or path not in self.dirs:
            raise OSError(errno.ENOENT, "No such file/directory")
        return iter([(n, k, 0, 0) for n, k in self.dirs[path].items()])

    def stat(self, path):
        if path not in self.files:
            raise OSError(errno.ENOENT, "No such file/directory")
        return (0, 0, 0, 0, 0, 0, len(self.files[path]), 0, 0, 0)

    def open(self, path, mode):
        if "w" in mode:
            if self.fail_write:
                raise OSError(errno.ENOSPC, "No space")
            return FakeFile(self, path, True)
        if path not in self.files:
            raise OSError(errno.ENOENT, "No such file/directory")
        self.opens += 1
        return FakeFile(self, path, False, self.files[path])

    def rename(self, old, new):
        self.files[new] = self.files.pop(old)

    def remove(self, path):
        del self.files[path]


def load_paths():
    with open(TSV, encoding="utf-8") as f:
        return [line.split("\t")[0] for line in f]


def extras(vfs):
    """What the capture left out: non-music entries that must be ignored."""
    for p in (
        "/MUSIC.LIB",
        "/M3U.LIB",
        "/._NIN",
        "/.Trashes/x.mp3",
        "/ALBUM.PIC/x.mp3",
        "/Pink Floyd/The Wall [Disc 1]/ALBUM.PIC/y.mp3",
        "/Pink Floyd/The Wall [Disc 1]/._1-01 In The Flesh_.mp3",
    ):
        vfs.files[p] = b""
        vfs._add(p, 0x8000)


def tests_names():
    g = library._guess_file
    for stem, want in (
        ("01 Analogue Bubblebath", (0, 1, "Analogue Bubblebath")),
        ("01 - 3rd Planet", (0, 1, "3rd Planet")),
        ("01-title", (0, 1, "title")),
        ("1-01 Cliffs", (1, 1, "Cliffs")),
        ("101-neutral_milk_hotel-the_king", (1, 1, "the king")),
        ("11-aphex_twin-11", (0, 11, "11")),
        ("A1 - About a Girl", (1, 1, "About a Girl")),
        ("02 10", (0, 2, "10")),
        ("13 2 Pi R", (0, 13, "2 Pi R")),
        ("01. Dot", (0, 1, "Dot")),
        ("11 ...And Carrot Rope", (0, 11, "...And Carrot Rope")),
        ("3rd Planet", (0, 0, "3rd Planet")),
        ("4.27 Ambience", (0, 0, "4.27 Ambience")),
        ("1984 - Reckoning", (0, 0, "1984 - Reckoning")),
        ("U2 - Zooropa", (0, 0, "U2 - Zooropa")),
        ("Song", (0, 0, "Song")),
        ("01", (0, 1, "01")),
    ):
        assert g(stem) == want, (stem, g(stem))
    f = library._guess_folder
    for dirs, want in (
        (["Aphex Twin", "_..I Care Because You Do"], ("Aphex Twin", "...I Care Because You Do")),
        (["R.E.M_", "Up"], ("R.E.M", "Up")),
        (["Compilations", "Pi"], ("", "Pi")),
        (["Various Artists", "Goa Spirit 2 [Disc 1]"], ("", "Goa Spirit 2 [Disc 1]")),
        (["NIN-The_Downward_Spiral"], ("NIN", "The Downward Spiral")),
        (["REM - 1998 - Up"], ("REM", "Up")),
        (["REM 1986 - Lifes Rich Pageant"], ("REM", "Lifes Rich Pageant")),
        (["Logic_Bomb-Sonic_Algebra-2007"], ("Logic Bomb", "Sonic Algebra")),
        (["Just An Album"], ("", "Just An Album")),
        ([], ("", "Loose Files")),
        (["Artist", "Album", "CD 2"], ("Artist", "Album CD 2")),
        (["Album", "Disc1"], ("", "Album Disc1")),
        (["Artist", "Box", "Album"], ("Artist", "Album")),
    ):
        assert f(dirs) == want, (dirs, f(dirs))


def fragile_index_tests(paths):
    """Every way of cutting the index must rebuild, never give a short library."""
    vfs = FakeVfs(paths)
    lib = library.Library(vfs)
    good = vfs.files[library.INDEX]
    total = len(lib.tracks)
    n = 0
    for cut in list(range(0, len(good), max(1, len(good) // 400))) + [
        len(good) - k for k in range(1, 40)
    ]:
        vfs.files[library.INDEX] = good[:cut]
        assert len(library.Library(vfs).tracks) == total, cut
        assert vfs.files[library.INDEX] == good, cut
        n += 1
    # a cut exactly at a line ending, the old format, a bad count, bad UTF-8, zeros
    lines = good.split(b"\n")
    for bad in (
        b"\n".join(lines[:100]) + b"\n",
        b"\n".join(lines[:-2]) + b"\n",
        b"\n".join(lines[:-2]) + b"\n#END\t5\n",
        good.replace(b"Pixies", b"\xff\xff", 1),
        good[:1000] + bytes(len(good) - 1000),
    ):
        vfs.files[library.INDEX] = bad
        assert len(library.Library(vfs).tracks) == total
    # a rebuild cut off by power: TEMP left over, the old INDEX still good
    vfs.files[library._TEMP] = good[:5000]
    vfs.files[library.INDEX] = good
    opens = vfs.opens
    assert len(library.Library(vfs).tracks) == total
    assert vfs.opens == opens + 2  # only INDEX, read then kept open
    # a full card keeps the library in RAM for this boot
    vfs = FakeVfs(paths)
    vfs.fail_write = True
    assert len(library.Library(vfs).tracks) == total
    assert library.INDEX not in vfs.files
    return n


def tag_tests():
    """Same tags in two folders stay two albums; mixed artists in one stay one."""
    tags = {
        "/A/X/01 a.flac": {"ARTIST": "A", "ALBUM": "Same", "TITLE": "a1", "TRACKNUMBER": "1"},
        "/A/Y/01 a.flac": {"ARTIST": "A", "ALBUM": "Same", "TITLE": "b1", "TRACKNUMBER": "1"},
        "/A/Y/02 a.flac": {"ARTIST": "A", "ALBUM": "Same", "TITLE": "b2", "TRACKNUMBER": "2/9"},
        "/Mix/101-a.flac": {"ARTIST": "One", "ALBUM": "Mix", "TITLE": "c1", "TRACKNUMBER": "1"},
        "/Mix/201-a.flac": {"ARTIST": "Two", "ALBUM": "Mix", "TITLE": "c2", "TRACKNUMBER": "1"},
        "/Mix/102-a.flac": {"ARTIST": "Thr\nee", "ALBUM": "Mix", "TITLE": "c3", "TRACKNUMBER": "2"},
    }
    vfs = FakeVfs(list(tags))
    for path in tags:  # really go through read_tags, on a built file  # noqa: PLC0206
        body = (0).to_bytes(4, "little")
        kv = [("%s=%s" % kv).encode() for kv in tags[path].items()]
        body += len(kv).to_bytes(4, "little")
        for c in kv:
            body += len(c).to_bytes(4, "little") + c
        vfs.files[path] = b"fLaC" + bytes([0x84]) + len(body).to_bytes(3, "big") + body
    lib = library.Library(vfs)
    got = [(a[0], a[1], [lib.tracks[i][3] for i in a[2]]) for a in lib.albums]
    assert got == [
        ("A", "Same", ["a1"]),
        ("A", "Same", ["b1", "b2"]),
        ("", "Mix", ["c1", "c3", "c2"]),
    ], got
    assert lib.tracks[lib.albums[2][2][1]][1] == "Thr ee"


class Player:
    current = None
    paused = playing = False
    skipped = False
    db = 0

    def play(self, queue, n, skip=False):
        self.current = queue[n]
        return True

    format = ""

    def position(self):  # noqa: PLR6301
        return 1, 1


def main():
    tests_names()
    tag_tests()
    paths = load_paths()
    print("tsv lines", len(paths))
    if CUT_OFF not in paths:
        paths.append(CUT_OFF)
    vfs = FakeVfs(paths)
    extras(vfs)

    t0 = time.perf_counter()
    lib = library.Library(vfs)
    t1 = time.perf_counter()
    size = len(vfs.files[library.INDEX])
    opens, lists = vfs.opens, vfs.lists
    lib2 = library.Library(vfs)
    t2 = time.perf_counter()
    assert list(lib2.tracks) == list(lib.tracks) and lib2.albums == lib.albums

    print("tracks", len(lib.tracks), "albums", len(lib.albums), "index bytes", size)
    print(
        "build %.0f ms, load %.0f ms (CPython on this Mac, says nothing about the board)"
        % ((t1 - t0) * 1e3, (t2 - t1) * 1e3)
    )
    print("build: folders listed", lists, "files opened", opens - 1, "(+1 index re-read)")

    got = {t[0] for t in lib.tracks}
    assert got == set(paths), "lost %r gained %r" % (set(paths) - got, got - set(paths))
    assert len(lib.tracks) == len(paths)
    assert opens - 2 == sum(p.endswith(".flac") for p in paths)  # no MP3 was opened
    folders = {p[: p.rfind("/")] for p in paths}
    assert len(lib.albums) == len(folders)
    seen = []
    for a in lib.albums:
        fs = {lib.tracks[i][0].rsplit("/", 1)[0] for i in a[2]}
        assert len(fs) == 1
        seen.append(fs.pop())
    assert sorted(seen) == sorted(folders)
    assert [i for a in lib.albums for i in a[2]] == list(range(len(lib.tracks)))

    # the menus still work on it
    ui = menus.Menus(lib, Player())
    artists = {a[0].lower() for a in lib.albums if a[0]}
    assert ui.top.title == "ARTISTS  %d" % (len(artists) + 1)  # + the Various row
    assert ui.top.items[0][1] == "Various"
    # albums sort so that menus finds each artist's in one range of lib.albums
    for item in ui.top.items[1:]:
        _, first, end = item[2]
        key = item[1].lower()
        assert not [a for a in lib.albums[:first] + lib.albums[end:] if a[0].lower() == key]
        assert not [a for a in lib.albums[first:end] if a[0] and a[0].lower() != key]
    no_artist = [i for i, a in enumerate(lib.albums) if not a[0]]
    ui.handle("button", "select")  # Various
    assert len(ui.top.items) == len(no_artist)
    ui.view()
    ui.handle("button", "select")  # its first album
    ui.view()
    ui.handle("button", "select")  # its first track
    ui.view()
    assert ui.player.current == lib.albums[no_artist[0]][2][0]

    print("cuts of the index that rebuilt:", fragile_index_tests(paths))

    # parse failures and things to look at
    empty = [t[0] for t in lib.tracks if not t[3] or not t[2]]
    nonum = [t[0] for t in lib.tracks if not t[4]]
    print("empty title or album", len(empty), empty[:5])
    print("no track number", len(nonum))
    for p in nonum:
        print("   ", p)
    names = {}
    for a, s in zip(lib.albums, seen):
        names.setdefault((a[0].lower(), a[1].lower()), []).append(s)
    print("albums shown under the same name:")
    for k, v in names.items():
        if len(v) > 1:
            print("   ", k, v)
    dups = []
    for a, s in zip(lib.albums, seen):
        nums = {}
        for i in a[2]:
            t = lib.tracks[i]
            stem = t[0].rsplit("/", 1)[1]
            key = library._guess_file(stem[: stem.rfind(".")])[:2]
            nums[key] = nums.get(key, 0) + 1
        d = [k for k, v in nums.items() if v > 1]
        if d:
            dups.append((s, len(d)))
    print("repeated numbers in a folder:", dups)
    print("first 6 albums:", [(a[0], a[1]) for a in lib.albums[:6]])
    print("no artist:", sum(1 for a in lib.albums if not a[0]))
    print(
        "one track:",
        [
            s
            for a, s in zip(lib.albums, seen)
            if len(a[2]) == 1 and not s.startswith(("/REM", "/REDM"))
        ],
    )
    print("ok")


def test_names():
    tests_names()


def test_tags():
    tag_tests()


if __name__ == "__main__":
    main()  # with a file listing a whole card, one "path<tab>size" a line


def test_tracks_read_from_the_index_file():
    index = b"/A/1.flac\tA\tAl\tone\t1\n/A/2.flac\tA\tAl\ttw\xc3\xb6\t2\n/B/1.mp3\tB\tBe\tx\t0\n#END\t3\n"  # noqa: E501
    vfs = types.SimpleNamespace(
        stat=lambda path: (0, 0, 0, 0, 0, 0, len(index)),
        open=lambda path, mode: io.BytesIO(index),
    )
    lib = library.Library(vfs)
    assert len(lib.tracks) == 3
    assert lib.tracks[1] == ("/A/2.flac", "A", "Al", "twö", 2)
    assert lib.tracks._raw is None
    assert [list(a[2]) for a in lib.albums] == [[0, 1], [2]]
    assert lib.albums[0][:2] == ("A", "Al")
