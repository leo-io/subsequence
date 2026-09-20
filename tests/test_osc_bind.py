"""OSC listens on this machine unless it is asked not to (#3045).

`Composition.osc()` defaulted `receive_host="0.0.0.0"` — every interface —
while `web_ui()` and `live()` bind localhost. An OSC sender is not a passive
observer: it can change tempo, mute parts and write data, and a future-dated
bundle used to freeze the clock outright (#3001).

Decision 15 of #2991: default to `127.0.0.1`, let `"0.0.0.0"` opt in, and say
in the startup log which of the two it chose.
"""

import inspect

import pytest

import subsequence
import subsequence.osc


# ---------------------------------------------------------------------------
# #3045 — OSC listens on this machine unless asked otherwise
# ---------------------------------------------------------------------------

def test_osc_listens_on_localhost_by_default () -> None:

	"""The finding: it was 0.0.0.0, alone among the three servers."""

	default = inspect.signature(subsequence.Composition.osc).parameters["receive_host"].default

	assert default == "127.0.0.1", f"osc() still opens on {default!r} by default"


def test_the_osc_server_itself_defaults_the_same_way () -> None:

	"""Constructed directly, not only through Composition.osc()."""

	default = inspect.signature(subsequence.osc.OscServer.__init__).parameters["receive_host"].default

	assert default == "127.0.0.1"


def test_osc_agrees_with_the_other_two_servers () -> None:

	"""The point is that one of three was different; say so mechanically."""

	web_ui = inspect.signature(subsequence.Composition.web_ui).parameters

	assert web_ui["http_host"].default == "127.0.0.1"
	assert web_ui["ws_host"].default == "127.0.0.1"

	osc = inspect.signature(subsequence.Composition.osc).parameters

	assert osc["receive_host"].default == web_ui["http_host"].default


def test_the_lan_is_still_available_to_anybody_who_asks (patch_midi: None) -> None:

	"""The control. A default is not a prohibition."""

	composition = subsequence.Composition(bpm = 120)
	composition.osc(receive_host = "0.0.0.0")

	assert composition._osc_server is not None
	assert composition._osc_server._receive_host == "0.0.0.0"


@pytest.mark.parametrize(
	("host", "expected"),
	[("127.0.0.1", "this machine only"), ("0.0.0.0", "the network")],
)
def test_the_startup_line_says_how_far_it_can_be_reached (
	host: str,
	expected: str,
	caplog: pytest.LogCaptureFixture,
	patch_midi: None,
) -> None:

	"""A musician who has just opened their piece to the network should read that.

	Reading the SOURCE of start() would pass either way — the old version
	mentions `_receive_host` too, because it has to bind something. What
	changed is the line it writes, so that is what this reads.
	"""

	import asyncio
	import logging

	composition = subsequence.Composition(bpm = 120)
	composition.osc(receive_port = 0, send_port = 0, receive_host = host)

	server = composition._osc_server
	assert server is not None

	async def start_and_stop () -> None:
		await server.start()
		await server.stop()

	with caplog.at_level(logging.INFO, logger = "subsequence.osc"):
		asyncio.run(start_and_stop())

	said = " ".join(record.getMessage() for record in caplog.records)

	assert host in said, f"the startup line does not name the interface: {said!r}"
	assert expected in said, f"the startup line does not say how far it reaches: {said!r}"
