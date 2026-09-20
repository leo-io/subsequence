"""A definitions file's numbers mean what they look like (#3046).

`definitions.py` read its files with PyYAML, which implements YAML **1.1** —
where a leading zero means octal and a colon means sexagesimal. A drum map
lining numbers up in a column read `kick: 036` as **30**, a different drum,
silently; a cue written `1:30` became **90**.

Decision 18 of #2991: YAML 1.2 number rules, in Subsequence and Subsample
alike. The Subsample half is its own ticket.
"""

import pathlib

import pytest
import yaml

import subsequence
import subsequence.definitions


# ---------------------------------------------------------------------------
# #3046 — definitions files read as YAML 1.2
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
	("written", "means"),
	[
		("036",     36),		# 1.1 read this as 30 — octal
		("012345",  12345),		# 1.1 read this as 5349
		("38",      38),
		("0o42",    34),		# 1.1 left this a string
		("0x2A",    42),
		("-7",      -7),
		("0",       0),
	],
)
def test_a_number_means_what_it_looks_like (written: str, means: int) -> None:

	"""The heart of it: a leading zero is how people line a column up."""

	loaded = yaml.load(f"value: {written}", Loader = subsequence.definitions._Yaml12Loader)

	assert loaded["value"] == means
	assert isinstance(loaded["value"], int), f"{written} came back as {type(loaded['value']).__name__}"


def test_a_colon_stays_text () -> None:

	"""`1:30` is a time somebody wrote, not 1*60 + 30."""

	loaded = yaml.load("cue: 1:30", Loader = subsequence.definitions._Yaml12Loader)

	assert loaded["cue"] == "1:30"


def test_a_real_float_is_still_a_float () -> None:

	"""The float resolver was rewritten too; it must not have eaten the floats."""

	loaded = yaml.load(
		"a: 2.5\nb: 1e3\nc: .inf\nd: -0.25",
		Loader = subsequence.definitions._Yaml12Loader,
	)

	assert loaded["a"] == pytest.approx(2.5)
	assert loaded["b"] == pytest.approx(1000.0)
	assert loaded["c"] == float("inf")
	assert loaded["d"] == pytest.approx(-0.25)


def test_a_plain_integer_is_not_quietly_a_float () -> None:

	"""The first version of the float pattern matched a bare "38", so it was 38.0.

	A MIDI note number is not a float, and nothing downstream would have said
	so — the sections validate range, not type.
	"""

	loaded = yaml.load("snare: 38", Loader = subsequence.definitions._Yaml12Loader)

	assert isinstance(loaded["snare"], int)
	assert not isinstance(loaded["snare"], bool)


def test_the_rest_of_pyyaml_is_left_alone () -> None:

	"""The resolvers are copied onto a private loader, not edited in place.

	Editing yaml.SafeLoader would change how every other library in the
	process reads YAML, which is not ours to do.
	"""

	# Checking a VALUE is not enough: the value is decided by the constructor,
	# and sharing the resolver table would leave 036 reading 30 anyway. The
	# sexagesimal reading is resolver-only, so it is the one that moves.
	assert yaml.safe_load("value: 036")["value"] == 30
	assert yaml.safe_load("cue: 1:30")["cue"] == 90

	assert (
		yaml.SafeLoader.yaml_implicit_resolvers
		is not subsequence.definitions._Yaml12Loader.yaml_implicit_resolvers
	), "the private loader shares PyYAML's own resolver table"


def test_a_definitions_file_reads_its_numbers_correctly (tmp_path: pathlib.Path) -> None:

	"""End to end, through the public loader a musician actually calls."""

	path = tmp_path / "project.yaml"
	path.write_text(
		"notes:\n"
		"  kick: 036\n"
		"  snare: 38\n"
		"  hat: 042\n"
		"channels:\n"
		"  kit: 010\n"
	)

	defs = subsequence.load_definitions(str(path))

	assert defs.notes["kick"] == 36, "a leading zero is still being read as octal"
	assert defs.notes["snare"] == 38
	assert defs.notes["hat"] == 42
	assert defs.channels["kit"] == 10
