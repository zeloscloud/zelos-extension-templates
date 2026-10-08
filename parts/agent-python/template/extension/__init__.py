"""The {{ name }} agent runtime.

Streams example sensor data to Zelos and exposes actions.
"""

from .extension import SensorMonitor

__all__: list[str] = [
    "SensorMonitor",
]
