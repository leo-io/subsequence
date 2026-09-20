"""A tag proves what a merge proves, before anything reaches PyPI (#3040).

`publish.yml` fires on `push: tags: v*` and used to go straight to build and
`twine check` — no tests, no mypy, no cheat-sheet check — while `tests.yml` ran
only on pushes to `main` and on pull requests. So a tag placed on a commit that
had never been tested, or whose tests had gone red, uploaded to PyPI anyway.
Trusted Publishing means there is no token to fumble and no second pair of
hands in the loop: the tag IS the release, so the gate is all there is.

CI configuration is not executed by this suite, so these are the guard — the
same reason `tests/test_cheatsheet.py` exists for a check that used to live
only in CI (#2593).
"""

import pathlib
import typing

import pytest
import yaml


WORKFLOWS = pathlib.Path(__file__).resolve().parent.parent / ".github" / "workflows"


def _workflow (name: str) -> typing.Dict[str, typing.Any]:

	path = WORKFLOWS / name

	assert path.exists(), f"{name} is gone — the release flow has moved and this test has not"

	loaded = yaml.safe_load(path.read_text())

	assert isinstance(loaded, dict), f"{name} did not parse as a mapping"

	return loaded


def _triggers (workflow: typing.Dict[str, typing.Any]) -> typing.Dict[str, typing.Any]:

	"""The `on:` block.

	YAML 1.1 reads a bare `on` as the BOOLEAN True, which is why this is not
	just `workflow["on"]` — the same 1.1 quirk that turns `kick: 036` into 30
	in a definitions file.
	"""

	for key in ("on", True):
		if key in workflow:
			return typing.cast(typing.Dict[str, typing.Any], workflow[key])

	pytest.fail(f"no `on:` trigger block: keys were {sorted(map(str, workflow))}")


def _steps_run (workflow: typing.Dict[str, typing.Any], job: str) -> str:

	"""Everything the named job's steps actually run, as one blob."""

	steps = workflow["jobs"][job].get("steps", [])

	return "\n".join(str(step.get("run", "")) for step in steps)


# ---------------------------------------------------------------------------
# Publishing is gated
# ---------------------------------------------------------------------------

def test_publishing_waits_for_the_tests () -> None:

	"""The finding itself: nothing is built for PyPI until the tests have run."""

	publish = _workflow("publish.yml")
	jobs = publish["jobs"]

	assert "build" in jobs, f"publish.yml has no build job: {sorted(jobs)}"

	needs = jobs["build"].get("needs")
	needs = [needs] if isinstance(needs, str) else (needs or [])

	assert needs, "the build job depends on nothing — a tag on a red commit still ships"

	for gate in needs:
		assert gate in jobs, f"build needs {gate!r}, which publish.yml does not define"


def test_the_gate_is_the_same_workflow_that_guards_main () -> None:

	"""Two definitions of green drift apart; one cannot."""

	publish = _workflow("publish.yml")

	needs = publish["jobs"]["build"].get("needs")
	needs = [needs] if isinstance(needs, str) else (needs or [])

	reused = [
		publish["jobs"][gate].get("uses", "")
		for gate in needs
	]

	assert any("tests.yml" in str(u) for u in reused), \
		f"the publish gate does not reuse tests.yml: {reused}"


def test_the_test_workflow_can_be_called () -> None:

	"""`uses:` only works against a workflow that offers `workflow_call`."""

	triggers = _triggers(_workflow("tests.yml"))

	assert "workflow_call" in triggers, \
		f"tests.yml cannot be reused by publish.yml: triggers were {sorted(map(str, triggers))}"


def test_publishing_still_fires_on_a_version_tag () -> None:

	"""The control. A gate that never runs would pass every test above."""

	triggers = _triggers(_workflow("publish.yml"))

	assert "push" in triggers, f"publish.yml no longer fires on a push: {sorted(map(str, triggers))}"
	assert "v*" in triggers["push"]["tags"]


# ---------------------------------------------------------------------------
# The gate is all four gates
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
	("gate", "fragment"),
	[
		("the tests",          "pytest"),
		("mypy",               "mypy"),
		("docstring markup",   "check_docstring_markup.py"),
		("the cheat sheet",    "generate_cheatsheet.py --check"),
	],
)
def test_ci_runs_every_gate_that_runs_here (gate: str, fragment: str) -> None:

	"""Four gates run before every commit in this repo; CI had three.

	mypy was the missing one, on either interpreter, so a type error reached
	main and waited for somebody to run it by hand.
	"""

	runs = _steps_run(_workflow("tests.yml"), "pytest")

	assert fragment in runs, f"CI no longer runs {gate}"


def test_ci_still_tests_both_ends_of_the_supported_range () -> None:

	"""3.10 and 3.14 — testing one of them tested neither, and both have caught things."""

	versions = _workflow("tests.yml")["jobs"]["pytest"]["strategy"]["matrix"]["python-version"]

	assert "3.10" in [str(v) for v in versions], versions
	assert len(versions) >= 2, f"only one interpreter is tested: {versions}"
