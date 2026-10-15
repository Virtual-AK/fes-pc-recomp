# Contributing

Thank you for helping. You do not need to be a programmer: testing and reporting are some of the most useful things you can do.

## The one rule
**Never upload anything that comes from the game.** That means no disc images, no extracted files, no converted textures, audio or video, no executable or BIOS, no save files, and no long text or code dumps from the game. This applies to commits, pull requests, issues, comments and screenshots of large amounts of game content.

What you *can* share:
- Reports written by our tools (file names, sizes, short header samples). Attach these to issues when asked.
- Short quotes of a few bytes or a file name when explaining a finding.
- Notes about formats, in your own words.
- Your own code.

If you are unsure, ask in an issue before posting.

## Ways to help
1. **Test the tools** on your own dump. Follow [docs/qa-guide.md](docs/qa-guide.md) and open an issue with the results. Reports from other regions (PAL, Japanese) and from other dumps are especially valuable.
2. **Check converted output** (pictures, audio) and report anything that looks or sounds wrong, without attaching the files themselves.
3. **Document a format.** Add to [docs/formats.md](docs/formats.md) what you learned, and say how you checked it.
4. **Write or improve a tool.** Tools are single Python files that use only the standard library, so anyone can run them without installing anything. Keep them read-only with respect to the disc image, and keep every output inside the folder the user chose.
5. **Work on the port itself.** See [docs/roadmap.md](docs/roadmap.md). Please open an issue first so we can agree on an approach.

## Code guidelines
- Python 3.8 or later, standard library only, one file per tool.
- Tools must never write outside the output folder they were given, must never modify the input, and must handle damaged or unexpected files by reporting them instead of crashing.
- Print a short summary and a plain-language message for every error, because most users are not developers.
- Add a test when you add a tool or a format. Either extend `tests/make_test_disc.py` and `tests/run_tests.py`, or add a self-contained `tests/test_<name>.py` that builds its own synthetic data and prints `ok   ...` as its last line (`run_tests.py` runs every `tests/test_*.py` automatically). Tests must contain no game data. Run them with `python tests/run_tests.py`.
- A tool may write a new disc image only to a path the user gives (as `p3fes_patch.py` does) and must never change the original.
- Document what you learn in `docs/formats.md`, and say what was verified and how. Mark guesses as guesses.
- Do not copy code from projects whose licenses do not allow it. Say where an idea or a formula came from.

## Pull requests
Keep them focused, describe what you tested, and tick the checklist in the template. By contributing you agree your work is released under the MIT license.

## If a rights holder contacts the project
Maintainers will respond promptly and in good faith. This project aims to work only with data from discs that people own, and to respect the rights of the game's creators.
