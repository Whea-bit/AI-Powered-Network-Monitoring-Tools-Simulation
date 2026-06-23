"""
Collector interface — the most important architectural piece.

A Collector is anything that can produce a list of Device objects. The API
layer never knows or cares whether the data came from a simulator or a real
SNMP poll. This is the seam that lets you develop against fakes today and
swap in real hardware later by changing ONE line in server.py.

To add real device support, subclass BaseCollector and implement collect().
See collectors/snmp_collector.py for a worked stub.
"""

from abc import ABC, abstractmethod
from typing import List
from models import Device


class BaseCollector(ABC):
    """All data sources implement this single method."""

    name: str = "base"

    @abstractmethod
    async def collect(self) -> List[Device]:
        """Return the current state of all monitored devices."""
        raise NotImplementedError

    async def startup(self) -> None:
        """Optional: open SSH/SNMP sessions, load config, etc."""
        pass

    async def shutdown(self) -> None:
        """Optional: clean up sessions on server stop."""
        pass
