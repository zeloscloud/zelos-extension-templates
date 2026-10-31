"""Example Sensor monitoring implementation."""

import logging
import random
import time
from typing import Any

import zelos_sdk

logger = logging.getLogger(__name__)


class SensorMonitor:
    """Monitors sensor data and streams to Zelos."""

    STATUS = {
        0: "OK",
        1: "WARNING",
        2: "ERROR",
    }

    def __init__(self, config: dict[str, Any]) -> None:
        """Initialize the sensor monitor.

        :param config: Configuration from load_config()
        """
        self.config = config
        self.running = False

        self.source = zelos_sdk.TraceSourceCacheLast("{{ project_slug }}")
        self._define_schema()

    def start(self) -> None:
        """Start monitoring."""
        logger.info(f"Starting {self.config.get('sensor_name', 'sensor')}")
        self.running = True

    def stop(self) -> None:
        """Stop monitoring."""
        logger.info("Stopping monitor")
        self.running = False

    def run(self) -> None:
        """Main monitoring loop."""
        loop_count = 0
        while self.running:
            # Simulate sensor readings
            temp = 20.0 + random.uniform(-5, 5)
            pressure = 1013.25 + random.uniform(-10, 10)
            voltage = 12.0 + random.uniform(-0.5, 0.5)
            current = 2.5 + random.uniform(-0.3, 0.3)

            # Determine status based on cached temperature
            status = 0  # OK
            last_temp = self.source.environmental.temperature.get()
            if last_temp is not None:
                if last_temp > 30:
                    status = 2  # ERROR
                elif last_temp > 25:
                    status = 1  # WARNING

            self.source.environmental.log(
                temperature=temp,
                pressure=pressure,
                status=status,
            )

            self.source.power.log(
                voltage=voltage,
                current=current,
            )

            loop_count += 1
            if loop_count % 10 == 0:
                logger.info(
                    "temp=%.1f°C, pressure=%.1fhPa, voltage=%.1fV, current=%.1fA, status=%s",
                    temp,
                    pressure,
                    voltage,
                    current,
                    self.STATUS[status],
                )

            time.sleep(self.config.get("interval_ms", 100) / 1000)

    @zelos_sdk.action("Set Interval", "Change sample rate")
    @zelos_sdk.action.integer(
        "interval_ms",
        minimum=1,
        maximum=1000,
        default=100,
        title="Interval (ms)",
        description="Time between samples, from 1 ms (1 kHz) to 1000 ms (1 Hz)",
        widget="range",
    )
    def set_interval(self, interval_ms: int) -> dict[str, Any]:
        """Update the sample interval.

        :param interval_ms: New interval in milliseconds (1 to 1000)
        :return: Confirmation dictionary with keys:
            - message (str): Success message
            - interval_ms (int): The new interval value
        """
        self.config["interval_ms"] = interval_ms
        return {"message": f"Interval set to {interval_ms} ms", "interval_ms": interval_ms}

    @zelos_sdk.action("Get Status", "Get current sensor status", read_only=True, hidden=True)
    def get_status(self) -> dict[str, Any]:
        """Get current sensor status.

        :return: Status dictionary with current values
        """
        return {
            "running": self.running,
            "interval_ms": self.config.get("interval_ms", 100),
            "temperature": self.source.environmental.temperature.get(),
            "pressure": self.source.environmental.pressure.get(),
            "voltage": self.source.power.voltage.get(),
            "current": self.source.power.current.get(),
            # None until the first sample is logged.
            "status": self.STATUS.get(self.source.environmental.status.get()),
        }

    def _define_schema(self) -> None:
        """Define trace schema."""
        self.source.add_event(
            "environmental",
            [
                zelos_sdk.TraceEventFieldMetadata("temperature", zelos_sdk.DataType.Float32, "°C"),
                zelos_sdk.TraceEventFieldMetadata("pressure", zelos_sdk.DataType.Float32, "hPa"),
                zelos_sdk.TraceEventFieldMetadata("status", zelos_sdk.DataType.UInt8),
            ],
        )

        self.source.add_event(
            "power",
            [
                zelos_sdk.TraceEventFieldMetadata("voltage", zelos_sdk.DataType.Float32, "V"),
                zelos_sdk.TraceEventFieldMetadata("current", zelos_sdk.DataType.Float32, "A"),
            ],
        )

        # Value table for status field
        self.source.add_value_table("environmental", "status", self.STATUS)
