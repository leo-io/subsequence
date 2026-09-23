"""A docstring is published text, so it is held to the site's voice here, before a re-pin finds it.

subsystem.co generates Subsequence's API reference from the docstrings of everything in
`subsequence.__all__`, and the cheat sheet from their first lines.  The site never prints an em
dash: the dash is a spaced hyphen (#2568).  Its check runs only when the site pins a new commit,
long after the docstring was written - 978 had accumulated by the time it first ran - so this
reads every docstring in the package, published or not, on every run of the suite.
"""

import ast
import pathlib
import typing

import subsequence


PACKAGE = pathlib.Path(subsequence.__file__).resolve().parent


def _docstrings () -> typing.List[typing.Tuple[str, str]]:

	"""Every module, class and function docstring in the package, with the line it starts on."""

	found: typing.List[typing.Tuple[str, str]] = []

	for path in sorted(PACKAGE.rglob("*.py")):

		tree = ast.parse(path.read_text(encoding="utf-8"))

		for node in ast.walk(tree):

			if not isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
				continue

			docstring = ast.get_docstring(node, clean=False)

			if docstring:
				found.append((f"{path.relative_to(PACKAGE.parent)}:{node.body[0].lineno}", docstring))

	return found


def test_the_walk_reads_the_whole_package () -> None:

	"""A walk that found nothing would pass every check below, so it must find the package first."""

	where = [location for location, _ in _docstrings()]

	assert len(where) > 1000
	assert any(location.startswith("subsequence/composition.py:") for location in where)
	assert any(location.startswith("subsequence/constants/") for location in where)


def test_no_docstring_prints_an_em_dash () -> None:

	"""The site never prints an em dash, and a docstring is what it prints (#2568)."""

	offenders = [location for location, text in _docstrings() if "\u2014" in text]

	assert offenders == []
