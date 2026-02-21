"""Network discovery for Novastar H series processors."""

from __future__ import annotations

import asyncio
import logging
import socket
from dataclasses import dataclass

import aiohttp

from .const import DEFAULT_PORT

_LOGGER = logging.getLogger(__name__)

# Timeout for individual connection attempts (seconds)
PROBE_TIMEOUT = 2.0

# Maximum concurrent probes
MAX_CONCURRENT_PROBES = 50


@dataclass
class DiscoveredDevice:
    """Represents a discovered Novastar device."""

    host: str
    port: int
    name: str
    model: str
    serial: str


def get_local_network_range() -> list[str]:
    """Get list of IP addresses to scan on the local network."""
    try:
        # Get local IP address
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()

        # Extract network prefix (assumes /24 subnet)
        prefix = ".".join(local_ip.split(".")[:-1])

        # Generate all IPs in the /24 range (excluding .0 and .255)
        return [f"{prefix}.{i}" for i in range(1, 255)]
    except Exception as err:
        _LOGGER.error("Failed to determine local network range: %s", err)
        return []


async def probe_host(host: str, port: int = DEFAULT_PORT) -> DiscoveredDevice | None:
    """Probe a single host to check if it's a Novastar device."""
    try:
        # Quick TCP connect check first
        try:
            _, writer = await asyncio.wait_for(
                asyncio.open_connection(host, port),
                timeout=PROBE_TIMEOUT,
            )
            writer.close()
            await writer.wait_closed()
        except (asyncio.TimeoutError, OSError, ConnectionRefusedError):
            return None

        # Port is open, check if it responds like a Novastar device
        # Try HTTP request and look for gunicorn server header
        try:
            async with aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=PROBE_TIMEOUT)
            ) as session:
                async with session.get(f"http://{host}:{port}/") as response:
                    server = response.headers.get("Server", "")
                    # Novastar devices use gunicorn
                    if "gunicorn" in server.lower():
                        return DiscoveredDevice(
                            host=host,
                            port=port,
                            name=f"Novastar @ {host}",
                            model="",
                            serial="",
                        )
        except Exception:
            pass

        # If HTTP check failed, still return as potential device on port 8000
        # Since port 8000 with TCP open is unusual
        return DiscoveredDevice(
            host=host,
            port=port,
            name=f"Novastar @ {host}",
            model="",
            serial="",
        )
    except Exception:
        pass

    return None


async def scan_network(
    hosts: list[str] | None = None,
    port: int = DEFAULT_PORT,
) -> list[DiscoveredDevice]:
    """Scan the network for Novastar devices.

    Args:
        hosts: List of IP addresses to scan. If None, scans local /24 network.
        port: Port to probe (default: 8000)

    Returns:
        List of discovered Novastar devices.
    """
    if hosts is None:
        hosts = get_local_network_range()

    if not hosts:
        return []

    _LOGGER.info("Scanning %d hosts for Novastar devices on port %d", len(hosts), port)

    discovered: list[DiscoveredDevice] = []
    semaphore = asyncio.Semaphore(MAX_CONCURRENT_PROBES)

    async def probe_with_semaphore(host: str) -> DiscoveredDevice | None:
        async with semaphore:
            return await probe_host(host, port)

    # Run all probes concurrently with rate limiting
    tasks = [probe_with_semaphore(host) for host in hosts]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    for result in results:
        if isinstance(result, DiscoveredDevice):
            _LOGGER.info("Found Novastar device: %s at %s", result.name, result.host)
            discovered.append(result)

    _LOGGER.info("Network scan complete. Found %d Novastar device(s)", len(discovered))
    return discovered
