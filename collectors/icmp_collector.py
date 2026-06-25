from icmplib import ping as icmp_ping, SocketPermissionError
from typing import Optional
import asyncio


def ping_host(ip: str, count: int = 3, timeout: float = 1.0) -> dict:
    """
    Ping a single IP address.
    Returns a dict with: alive, min_rtt, avg_rtt, max_rtt, packet_loss, ip
    Safe — never raises, always returns a result.
    """
    try:
        result = icmp_ping(ip, count=count, timeout=timeout, privileged=False)
        return {
            "ip": ip,
            "alive": result.is_alive,
            "min_rtt": round(result.min_rtt, 2) if result.is_alive else None,
            "avg_rtt": round(result.avg_rtt, 2) if result.is_alive else None,
            "max_rtt": round(result.max_rtt, 2) if result.is_alive else None,
            "packet_loss": round(result.packet_loss * 100, 1),
            "packets_sent": count,
            "packets_received": result.packets_received,
        }
    except SocketPermissionError:
        return {
            "ip": ip, "alive": False,
            "min_rtt": None, "avg_rtt": None, "max_rtt": None,
            "packet_loss": 100.0, "packets_sent": count, "packets_received": 0,
            "error": "Permission denied — try: sudo sysctl -w net.ipv4.ping_group_range='0 2147483647'"
        }
    except Exception as e:
        return {
            "ip": ip, "alive": False,
            "min_rtt": None, "avg_rtt": None, "max_rtt": None,
            "packet_loss": 100.0, "packets_sent": count, "packets_received": 0,
            "error": str(e)
        }


async def ping_host_async(ip: str, count: int = 3, timeout: float = 1.0) -> dict:
    """Async wrapper — runs ping in a thread so it doesn't block the event loop."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, ping_host, ip, count, timeout)


async def ping_all_devices(ips: list, count: int = 2, timeout: float = 1.0) -> dict:
    """
    Ping multiple IPs concurrently.
    Returns a dict keyed by IP: { ip: ping_result }
    Much faster than pinging sequentially.
    """
    tasks = [ping_host_async(ip, count, timeout) for ip in ips]
    results = await asyncio.gather(*tasks)
    return {r["ip"]: r for r in results}


def format_ping_output(result: dict) -> str:
    """Format a ping result as CLI-friendly text."""
    ip = result["ip"]
    if result.get("error") and "Permission" in result.get("error", ""):
        return (
            f"Ping to {ip} failed: permission denied.\n"
            f"Fix: sudo sysctl -w net.ipv4.ping_group_range='0 2147483647'"
        )
    if not result["alive"]:
        return (
            f"Ping {ip} — Host unreachable\n"
            f"Packets: sent={result['packets_sent']} received={result['packets_received']} "
            f"loss={result['packet_loss']}%"
        )
    return (
        f"Ping {ip} — Host alive ✓\n"
        f"RTT: min={result['min_rtt']}ms  avg={result['avg_rtt']}ms  max={result['max_rtt']}ms\n"
        f"Packets: sent={result['packets_sent']} received={result['packets_received']} "
        f"loss={result['packet_loss']}%"
    )