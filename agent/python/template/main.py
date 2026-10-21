#!/usr/bin/env python3
"""{{ description }}"""

import logging
import signal
import time
from types import FrameType

import zelos_sdk
from zelos_sdk.extensions import load_config
from zelos_sdk.hooks.logging import TraceLoggingHandler

from {{ project_slug }}.extension import SensorMonitor

logger = logging.getLogger(__name__)


if __name__ == "__main__":
    # Configure logging before SDK initialization. UTC ISO 8601 with ms, matching
    # the SDK's Rust tracing lines that share this log stream.
    logging.Formatter.converter = time.gmtime
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s.%(msecs)03dZ %(levelname)5s %(name)s: %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )

    # Initialize SDK (logical extension id: kebab name → snake_case)
    zelos_sdk.init(name="{{ project_slug }}", actions=True)

    # Add trace logging handler to send logs to Zelos
    handler = TraceLoggingHandler("{{ project_slug }}_logger")
    logging.getLogger().addHandler(handler)

    # Load configuration and create sensor monitor
    config = load_config()
    monitor = SensorMonitor(config)

    # Register interactive actions for the Zelos App
    zelos_sdk.actions_registry.register(monitor)

    def shutdown_handler(signum: int, frame: FrameType | None) -> None:
        """Handle graceful shutdown on SIGTERM or SIGINT."""
        logger.info("Shutting down...")
        monitor.stop()

    signal.signal(signal.SIGTERM, shutdown_handler)
    signal.signal(signal.SIGINT, shutdown_handler)

    logger.info("Starting {{ name }}")
    monitor.start()
    monitor.run()
