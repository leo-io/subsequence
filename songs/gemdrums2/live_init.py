

import pathlib

import subsequence


LIVE_FILE = pathlib.Path(__file__).parent / "live_patterns.py"


composition = subsequence.Composition(bpm=117)


# Watch the live file - changes are picked up on save.
composition.watch(LIVE_FILE)


if __name__ == "__main__":
	composition.display(grid=True)

	composition.play()
