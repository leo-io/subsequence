"""Every README section the package or its examples point to exists (#2801).

The README was cut down to a summary, and docstrings went on naming sections
it no longer has, so a reader following one found nothing.  A reference names
its section in quotes (the README "Performance" section, or "Performance"
section of the README) or as the README's Performance section.
"""

import pathlib
import re
import typing

ROOT = pathlib.Path(__file__).resolve().parent.parent
HEADINGS = {line.lstrip("#").strip() for line in (ROOT / "README.md").read_text().splitlines() if line.startswith("#")}
NAMED = re.compile(r'README(?:\'s)?\s+"?(?P<after>[A-Z][^"().,;]*?)"?\s+section|"(?P<before>[^"]+)"\s+section\s+of\s+the\s+README')


def _references (text: str) -> typing.List[typing.Tuple[str, typing.Optional[str]]]:

	"""Each README mention in *text*, with the section it names, or None when it names none."""

	flat = " ".join(text.split())
	phrases = [(match.start(), match.end(), (match.group("after") or match.group("before")).strip()) for match in NAMED.finditer(flat)]
	found = []

	for mention in re.finditer(r"README(?!\.md|-|\w)", flat):
		window = flat[max(0, mention.start() - 60):mention.end() + 60]
		name = next((named for start, end, named in phrases if start <= mention.start() < end), None)
		found.append((window, name))

	return found


def test_the_reader_finds_both_spellings_and_an_unnamed_reference () -> None:

	"""So the next test's silence means every reference was read, not that none matched."""

	sample = 'see the README "MIDI mirroring" section. The "Live coding" section of the README. (see the README\'s\n\tPerformance section). See README for more.'

	assert [name for _, name in _references(sample)] == ["MIDI mirroring", "Live coding", "Performance", None]


def test_every_readme_section_named_in_code_exists () -> None:

	"""A reference that names no section, or one the README lacks, fails with its context."""

	files = sorted(ROOT.glob("subsequence/**/*.py")) + sorted(ROOT.glob("examples/*.py"))
	references = [(path.relative_to(ROOT), window, name) for path in files for window, name in _references(path.read_text())]

	assert len(files) > 50 and references
	assert [(str(path), window) for path, window, name in references if name not in HEADINGS] == []
