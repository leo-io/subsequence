"""No message the package prints holds an em dash (#3481).

Simon's rule (#2568): "I do not ever want to see an em dash in the output."  The docstrings
were swept and are guarded (tests/test_docstring_voice.py); the error messages and log lines
were not, and 230 of them printed one, in 19 files.  Subroutine had applied the same words to
everything it prints (#2819).

The first count of them said 83, because it read tokens, and from Python 3.12 an f-string is
tokenised in pieces: every f-string was missed.  This reads the syntax tree instead, where an
f-string's literal parts are strings like any other.
"""

import ast
import pathlib
import typing

import subsequence


PACKAGE = pathlib.Path(subsequence.__file__).resolve().parent

DASH = chr(0x2014)


def _output_strings (source: str) -> typing.List[typing.Tuple[int, str]]:

	"""Every string literal in *source* that can be printed, with its line: not a docstring, not a bare string statement.

	A string standing alone as a statement is a docstring, or the attribute
	note the reference renders beside a constant, and never reaches a
	terminal.  Those are held to the voice by the docstring test.
	"""

	tree = ast.parse(source)
	standalone: typing.Set[int] = set()

	for node in ast.walk(tree):
		if isinstance(node, ast.Expr) and isinstance(node.value, (ast.Constant, ast.JoinedStr)):
			standalone.update(id(inner) for inner in ast.walk(node.value))

	return [
		(node.lineno, node.value)
		for node in ast.walk(tree)
		if isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in standalone
	]


def _package_strings () -> typing.List[typing.Tuple[str, int, str]]:

	found = []

	for path in sorted(PACKAGE.rglob("*.py")):
		for line, text in _output_strings(path.read_text(encoding="utf-8")):
			found.append((f"{path.relative_to(PACKAGE.parent)}:{line}", line, text))

	return found


def test_the_walk_reads_the_whole_package () -> None:

	"""A floor, so a walk that stopped finding strings cannot pass as a clean one."""

	assert len(_package_strings()) > 2000


def test_no_message_the_package_prints_holds_an_em_dash () -> None:

	dashed = [where for where, _, text in _package_strings() if DASH in text]

	assert dashed == [], f"{len(dashed)} strings print an em dash; the dash is a spaced hyphen: {dashed[:10]}"


def test_the_walk_reads_an_f_strings_literal_parts () -> None:

	"""The trap the first count fell into."""

	source = 'def f (n):\n\traise ValueError(f"grid must be at least 1 ' + DASH + ' got {n}")\n'

	assert [text for _, text in _output_strings(source) if DASH in text] == ["grid must be at least 1 " + DASH + " got "]


def test_the_walk_leaves_docstrings_and_bare_strings_alone () -> None:

	"""They are the docstring test's to read, and print nowhere."""

	source = (
		'"""Module ' + DASH + ' docstring."""\n'
		'LIMIT = 4\n'
		'"""A note on LIMIT ' + DASH + ' rendered beside it."""\n'
		'def f ():\n'
		'\t"""Function ' + DASH + ' docstring."""\n'
		'\treturn "printed"\n'
	)

	assert _output_strings(source) == [(6, "printed")]
