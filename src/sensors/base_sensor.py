from abc import ABC, abstractmethod


class BaseSensor(ABC):
    """
    Abstract base class for all sensors.

    Every sensor must implement connect(), disconnect(), start(), stop(), and read().
    read() must return a dict. The key "timestamp" will be added by the data logger.

    Sensors should raise RuntimeError for recoverable hardware errors so the main
    loop can catch them, log them, and retry without crashing the whole program.
    """

    def __init__(self, name: str):
        self.name = name
        self._connected = False
        self._measuring = False

    @abstractmethod
    def connect(self) -> None:
        """Establish connection to sensor hardware. Raises RuntimeError on failure."""
        pass

    @abstractmethod
    def disconnect(self) -> None:
        """Disconnect and release all hardware resources."""
        pass

    @abstractmethod
    def start(self) -> None:
        """Begin measurement. Must call connect() first."""
        pass

    @abstractmethod
    def stop(self) -> None:
        """Stop measurement."""
        pass

    @abstractmethod
    def read(self) -> dict:
        """
        Read one sample from the sensor.

        Returns:
            dict with sensor-specific keys and numeric values.
            Do NOT include "timestamp" or "sensor_name" — the logger adds those.

        Raises:
            RuntimeError: if the sensor is not connected or not measuring.
        """
        pass

    @property
    def is_connected(self) -> bool:
        return self._connected

    @property
    def is_measuring(self) -> bool:
        return self._measuring

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.disconnect()
