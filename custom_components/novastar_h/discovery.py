"""Network discovery for Novastar H series processors."""

from __future__ import annotations

import asyncio
import logging
import socket
from dataclasses import dataclass
from ipaddress import ip_address

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
    """Get a best-effort list of host IPs to scan.

    Uses multiple sources so discovery keeps working in containerized setups:
    - Local interface IPv4 addresses
    - ARP table entries from /proc/net/arp
    """

    def _is_private_ipv4(host: str) -> bool:
        try:
            ip = ip_address(host)
            return ip.version == 4 and ip.is_private and not ip.is_loopback
        except ValueError:
            return False

    prefixes: set[str] = set()
    arp_hosts: set[str] = set()

    try:
        # Primary guess: OS-selected source IP
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("8.8.8.8", 80))
            local_ip = sock.getsockname()[0]
            if _is_private_ipv4(local_ip):
                prefixes.add(".".join(local_ip.split(".")[:-1]))
    except Exception:
        pass

    try:
        # Additional local interface addresses
        host_name = socket.gethostname()
        for _name, _alias, addresses in socket.gethostbyname_ex(host_name):
            for addr in addresses:
                if _is_private_ipv4(addr):
                    prefixes.add(".".join(addr.split(".")[:-1]))
    except Exception:
        pass

    try:
        # ARP neighbors (Linux / HA OS)
        with open("/proc/net/arp", encoding="utf-8") as arp_file:
            # Skip header
            next(arp_file, None)
            for line in arp_file:
                parts = line.split()
                if not parts:
                    continue
                host = parts[0]
                if _is_private_ipv4(host):
                    arp_hosts.add(host)
                    prefixes.add(".".join(host.split(".")[:-1]))
    except Exception:
        pass

    hosts: list[str] = []
    for prefix in sorted(prefixes):
        hosts.extend(f"{prefix}.{i}" for i in range(1, 255))

    # Include ARP-discovered hosts directly and de-duplicate while preserving order
    ordered: list[str] = []
    seen: set[str] = set()
    for host in list(arp_hosts) + hosts:
        if host not in seen:
            seen.add(host)
            ordered.append(host)

    return ordered


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

        # Port is open, check Novastar API signature response shape first
        try:
            async with aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=PROBE_TIMEOUT)
            ) as session:
                probe_body = {
                    "body": {"deviceId": 0},
                    "sign": "",
                    "pId": "",
                    "timeStamp": "0",
                }
                async with session.post(
                    f"http://{host}:{port}/open/api/device/readDetail",
                    json=probe_body,
                ) as response:
                    data = await response.json(content_type=None)
                    if isinstance(data, dict) and (
                        "status" in data or "msg" in data or "body" in data
                    ):
                        return DiscoveredDevice(
                            host=host,
                            port=port,
                            name=f"Novastar @ {host}",
                            model="",
                            serial="",
                        )
        except Exception:
            pass

        # Fallback heuristic: base endpoint often reports gunicorn on Novastar.
        try:
            async with aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=PROBE_TIMEOUT)
            ) as session:
                async with session.get(f"http://{host}:{port}/") as response:
                    server = response.headers.get("Server", "")
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
