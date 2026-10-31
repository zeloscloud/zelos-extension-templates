"""Entry point of the {{ name }} agent runtime."""

import logging
import signal
from types import FrameType

import zelos_sdk
from zelos_sdk.extensions import load_config
from zelos_sdk.hooks.logging import TraceLoggingHandler

from {{ project_slug }}.extension import SensorMonitor

logger = logging.getLogger(__name__)


if __name__ == "__main__":
    # Configure logging before SDK initialization
    logging.basicConfig(level=logging.INFO)

    # The name must equal `name` in extension.toml: the app and the packager address actions by it
    zelos_sdk.init(name="{{ name | replace('-', ' ') | title }}", actions=True)

    # Load configuration and create sensor monitor
    config = load_config()
    monitor = SensorMonitor(config)

    # Send logs to Zelos as a log event of the sensor's own trace source
    logging.getLogger().addHandler(TraceLoggingHandler(monitor.source))

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
