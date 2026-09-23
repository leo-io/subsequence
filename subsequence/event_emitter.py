import asyncio
import inspect
import logging
import typing


logger = logging.getLogger(__name__)

CallbackType = typing.Callable[..., typing.Any]


class EventEmitter:

	"""
	A simple event emitter supporting sync and async callbacks.
	"""

	#: Events delivered with :meth:`emit_sync`, on the clock itself, rather
	#: than with :meth:`emit_async`.
	#:
	#: A listener for one of these must be an ordinary function, because the
	#: caller is mid-pulse and cannot wait for a coroutine.  Registering an
	#: ``async def`` for one is refused in :meth:`on`, where the author can
	#: see it — not at the first boundary, halfway through a performance.
	SYNCHRONOUS_EVENTS = frozenset({"section"})

	def __init__ (self) -> None:

		"""
		Initialise an empty event registry.
		"""

		self._listeners: typing.Dict[str, typing.List[CallbackType]] = {}


	def on (self, event_name: str, callback: CallbackType) -> None:

		"""
		Register a callback for an event name.

		Raises ``ValueError`` when an ``async def`` is registered for one of
		:data:`SYNCHRONOUS_EVENTS`, which are delivered on the clock.
		"""

		if event_name in self.SYNCHRONOUS_EVENTS and inspect.iscoroutinefunction(callback):
			name = getattr(callback, "__name__", repr(callback))
			raise ValueError(
				f"{name}() is an async function, and {event_name!r} is announced from the "
				f"clock, which cannot wait for one. Make it an ordinary 'def'. To start "
				f"async work from it, hand it to asyncio.get_running_loop().create_task()."
			)

		if event_name not in self._listeners:
			self._listeners[event_name] = []

		self._listeners[event_name].append(callback)

	def off (self, event_name: str, callback: CallbackType) -> None:

		"""
		Unregister a previously registered callback.

		Raises ``ValueError`` if the callback is not registered for the event.
		"""

		if event_name not in self._listeners or callback not in self._listeners[event_name]:
			raise ValueError(f"Callback not registered for event {event_name!r}")

		self._listeners[event_name].remove(callback)


	def emit_sync (self, event_name: str, *args: typing.Any, **kwargs: typing.Any) -> None:

		"""
		Emit an event and call non-async listeners immediately.

		One raising listener never silences the others, as in
		:meth:`emit_async`: the failure is logged and the remaining listeners
		still run.  A listener that stops the music is worse than a listener
		that does not run, and the piece is playing.
		"""

		if event_name not in self._listeners:
			return

		for callback in self._listeners[event_name]:

			try:
				result = callback(*args, **kwargs)
			except Exception:
				logger.exception("Listener for %r raised - continuing with remaining listeners", event_name)
				continue

			# An async-callable object (async ``__call__``) passes the
			# iscoroutinefunction check that :meth:`on` makes, so it can only
			# be caught here, by what it returned.  Nothing can await it.
			if inspect.isawaitable(result):
				typing.cast(typing.Coroutine, result).close()
				logger.error(
					"Listener for %r returned an awaitable, which cannot be awaited from "
					"the clock - it did not run. Make it an ordinary callable.",
					event_name,
				)


	async def emit_async (self, event_name: str, *args: typing.Any, **kwargs: typing.Any) -> None:

		"""
		Emit an event, awaiting async listeners.

		One raising listener never silences the others: sync exceptions are
		logged and the remaining listeners still run, and async listeners are
		gathered with their exceptions logged individually.
		"""

		if event_name not in self._listeners:
			return

		tasks: typing.List[typing.Awaitable[typing.Any]] = []

		for callback in self._listeners[event_name]:

			# Calling first and checking the RESULT handles both coroutine
			# functions and async-callable objects (async __call__), which
			# iscoroutinefunction misses.
			try:
				result = callback(*args, **kwargs)
			except Exception:
				logger.exception("Listener for %r raised - continuing with remaining listeners", event_name)
				continue

			if inspect.isawaitable(result):
				tasks.append(result)

		if tasks:
			results = await asyncio.gather(*tasks, return_exceptions=True)

			for outcome in results:
				if isinstance(outcome, BaseException):
					logger.error("Async listener for %r raised", event_name, exc_info=outcome)
