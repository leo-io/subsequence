"""
Entry point for ``python -m subsequence`` - confirms the install and points to the docs.
"""

import logging


# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def main () -> None:

	"""
	Main entry point for the subsequence module.
	"""

	logger.info("Subsequence module loaded.")
	logger.info("To make your first sound, follow the guide: https://subsystem.co/subsequence/guide/install-and-connect/")


if __name__ == "__main__":
	main()
