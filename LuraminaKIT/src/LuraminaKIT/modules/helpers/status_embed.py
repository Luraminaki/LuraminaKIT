#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""`/status` reply rendering, kept separate from Discord API glue -- see
`LuraminaKIT/HOWTO.md`. Independent of command discovery/dispatch/help -- this
module only turns bot/host metrics into a `discord.Embed`.
"""

import discord

from LuraminaKIT.modules.helpers.host_metrics import GpuMetrics, HardwareInfo


def _format_uptime(seconds: float) -> str:
    """Render a duration as a compact `1d 2h 3m` string.

    Args:
        seconds: Duration in seconds.

    Returns:
        The formatted duration, always including minutes even if `0m` (so a
        freshly-started bot doesn't report a blank uptime).
    """
    total = int(seconds)
    days, remainder = divmod(total, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, _ = divmod(remainder, 60)

    parts = []
    if days:
        parts.append(f"{days}d")
    if hours or days:
        parts.append(f"{hours}h")
    parts.append(f"{minutes}m")

    return ' '.join(parts)


def build_status_embed(guild_count: int, commands_run: int, uptime_seconds: float, memory_mb: float,
                       hardware: HardwareInfo, cpu_percent: float, cpu_temp_celsius: float | None,
                       amd_gpu_temp_celsius: float | None, gpu_metrics: list[GpuMetrics]) -> discord.Embed:
    """Build the `/status` reply as a Discord embed, grouped into Bot/CPU/RAM/GPU fields.

    Every host-metrics line is best-effort and omitted entirely when
    unavailable (`None`/empty), rather than printed as "N/A" -- see
    `host_metrics`'s module docstring for why (Windows has no sensor
    readings at all, a headless box has no GPU, etc.).

    Args:
        guild_count: Number of guilds the bot is currently in.
        commands_run: Number of module commands successfully dispatched since startup.
        uptime_seconds: Seconds since the bot's `setup_hook` ran.
        memory_mb: The bot process's own resident memory, in MiB -- not the
            modulesKIT services it talks to, which run as separate processes.
        hardware: Static host hardware capabilities, from `host_metrics.static_hardware_info`.
        cpu_percent: Host-wide CPU utilization, from `host_metrics.cpu_load_percent`.
        cpu_temp_celsius: Host CPU temperature, or `None` if unavailable.
        amd_gpu_temp_celsius: Host AMD GPU temperature, or `None` if unavailable.
        gpu_metrics: One entry per Nvidia GPU detected via NVML, `[]` if none.

    Returns:
        A ready-to-send `discord.Embed`.
    """
    embed = discord.Embed(title="LuraminaKIT status", color=discord.Color.blurple(),
                          timestamp=discord.utils.utcnow())

    _ = embed.add_field(name="Bot",
                        value='\n'.join([f"Uptime: {_format_uptime(uptime_seconds)}",
                                         f"Commands run: {commands_run}",
                                         f"Servers: {guild_count}",
                                         f"Memory: {memory_mb:.1f} MB"]),
                        inline=True)

    cpu_lines: list[str] = []
    if hardware.cpu_brand:
        cpu_lines.append(hardware.cpu_brand)
    if hardware.cpu_physical_cores and hardware.cpu_logical_cores:
        cpu_lines.append(f"{hardware.cpu_physical_cores} cores / {hardware.cpu_logical_cores} threads")
    if hardware.cpu_max_ghz:
        cpu_lines.append(f"Up to {hardware.cpu_max_ghz:.2f} GHz")
    cpu_lines.append(f"Load: {cpu_percent:.1f}%")
    if cpu_temp_celsius is not None:
        cpu_lines.append(f"Temp: {cpu_temp_celsius:.1f}°C")
    _ = embed.add_field(name="CPU", value='\n'.join(cpu_lines), inline=True)

    _ = embed.add_field(name="RAM", value=f"{hardware.ram_total_gb:.1f} GB total", inline=True)

    for index, gpu in enumerate(gpu_metrics, start=1):
        field_name = "GPU" if len(gpu_metrics) == 1 else f"GPU {index}"

        header = gpu.name
        if gpu.vram_total_mb is not None:
            header += f" -- {gpu.vram_total_mb / 1024:.1f} GB VRAM"

        details: list[str] = []
        if gpu.temp_celsius is not None:
            details.append(f"{gpu.temp_celsius:.0f}°C")
        if gpu.power_watts is not None:
            details.append(f"{gpu.power_watts:.0f}W")
        if gpu.vram_used_mb is not None and gpu.vram_total_mb is not None:
            details.append(f"{gpu.vram_used_mb / 1024:.1f}/{gpu.vram_total_mb / 1024:.1f} GB used")

        value = header + ('\n' + ' · '.join(details) if details else '')
        _ = embed.add_field(name=field_name, value=value, inline=False)

    if amd_gpu_temp_celsius is not None:
        _ = embed.add_field(name="GPU temp (AMD)", value=f"{amd_gpu_temp_celsius:.1f}°C", inline=True)

    return embed
