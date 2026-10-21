"""Plugins: new kinds of musical object that ship with Subsequence and are set apart from its core.

A plugin installs, releases and is documented with Subsequence, and is imported on
its own, so a composition that does not use one never loads it::

	import subsequence.plugins.sequencers as sequencers

**The rule a plugin keeps:** it reaches the core only through public names, the
ones a musician can use too, such as ``p.memory``, ``p.after_build()`` and
``subsequence.catalogue.describe_parameter()``, and the core never names a plugin.
A test fails if a plugin touches a private name of the core.

The plugins:

- ``subsequence.plugins.sequencers``: hardware step sequencers (the Moog 960 and
  962, the ARP 1601) and your own, as models patched together with cables and
  played inside an ordinary pattern.
"""
