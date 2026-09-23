"""Nothing Subsequence ships points at subsequence.live, which subsystem.co replaced (#3487).

8976864 moved the README's links to subsystem.co, and ``python -m subsequence`` went on
sending a musician's first question to the retired Cookbook for four more days.
"""

import pathlib
import typing


ROOT = pathlib.Path(__file__).resolve().parent.parent


def _shipped () -> typing.List[pathlib.Path]:

	"""The package, the examples and the README: everything a musician reads."""

	files = sorted((ROOT / "subsequence").rglob("*.py")) + sorted((ROOT / "examples").rglob("*.py")) + [ROOT / "README.md"]

	assert len(files) > 50, "the sweep found almost nothing to read"

	return files


def test_nothing_shipped_links_to_the_retired_site () -> None:

	"""Its address may still be named in prose about it; never linked to."""

	linked = [
		f"{path.relative_to(ROOT)}:{number}"
		for path in _shipped()
		for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1)
		if "://subsequence.live" in line
	]

	assert linked == []
