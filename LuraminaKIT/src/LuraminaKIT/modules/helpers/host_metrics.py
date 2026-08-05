#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Best-effort host system metrics for `/status`.

Every reading here degrades to `None`/`[]` rather than raising, on whatever
sensor/vendor combination the machine running LuraminaKIT doesn't have --
`psutil` implements no temperature sensors at all on Windows, a headless
server has no GPU, and this repo's own dev machine has neither. The
`/status` renderer (`status_embed.build_status_embed`) simply omits a
line whose value came back `None`/empty, rather than printing "N/A".

@author: Luraminaki
"""

import functools
import logging

import cpuinfo
import psutil
import pynvml

from pydantic import BaseModel

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# `sensors_temperatures()` keys that carry a CPU package/core temperature,
# across the vendors this has actually been seen on (Intel `coretemp`, AMD
# `k10temp`/`zenpower`). Linux-only -- `psutil` doesn't implement sensor
# readings on Windows at all.
_CPU_TEMP_SENSOR_KEYS = ('coretemp', 'k10temp', 'zenpower')
# Same mechanism, for a discrete AMD GPU's own hwmon entry -- exposed because
# the in-kernel `amdgpu` driver is a well-behaved Linux citizen that publishes
# into the same sysfs tree as CPU sensors. This is the one AMD GPU reading
# available without a vendor-specific dependency: hwmon doesn't expose power
# draw or VRAM usage the way Nvidia's NVML does, only temperature.
_AMD_GPU_TEMP_SENSOR_KEY = 'amdgpu'


class GpuMetrics(BaseModel):
    """One Nvidia GPU's readings, via NVML.

    Attributes:
        name: The GPU's marketing name (e.g. "NVIDIA GeForce RTX 4080 SUPER").
        temp_celsius: Core temperature, or `None` if this specific reading failed.
        power_watts: Current board power draw, or `None` if this specific reading failed.
        vram_used_mb: VRAM currently in use, or `None` if this specific reading failed.
        vram_total_mb: Total VRAM on the card, or `None` if this specific reading failed.
    """

    name: str
    temp_celsius: float | None = None
    power_watts: float | None = None
    vram_used_mb: float | None = None
    vram_total_mb: float | None = None


class HardwareInfo(BaseModel):
    """Static host hardware capabilities -- collected once and cached, since none
    of this changes for the life of the process.

    Attributes:
        cpu_brand: The CPU's marketing name (e.g. "AMD Ryzen 9 5950X 16-Core
            Processor"), or `None` if `py-cpuinfo` couldn't determine it.
        cpu_physical_cores: Physical core count, or `None` if undetermined.
        cpu_logical_cores: Logical core count (threads), or `None` if undetermined.
        cpu_max_ghz: Rated max clock speed in GHz, or `None` if undetermined.
        ram_total_gb: Total installed system RAM, in GiB.
    """

    cpu_brand: str | None = None
    cpu_physical_cores: int | None = None
    cpu_logical_cores: int | None = None
    cpu_max_ghz: float | None = None
    ram_total_gb: float


@functools.lru_cache(maxsize=1)
def static_hardware_info() -> HardwareInfo:
    """Collect this host's static hardware capabilities, cached after the first call.

    None of this (CPU model, core counts, RAM size) changes for the life of
    the process, so there's no reason to re-probe it on every `/status` call
    -- `py-cpuinfo` in particular isn't instant, it parses `/proc/cpuinfo` or
    shells out to `wmic`/`sysctl` depending on the OS.

    Returns:
        Best-effort hardware info -- individual fields are `None` if their
        specific probe failed or isn't supported on this OS; never raises.
    """
    cpu_brand: str | None = None
    try:
        cpu_brand = cpuinfo.get_cpu_info().get('brand_raw')
    except Exception as err:
        # `py-cpuinfo` has no documented exception surface (it shells out to
        # OS-specific tools internally) -- broad on purpose, this must never
        # take `/status` down with it.
        logger.debug("py-cpuinfo probe failed -- %r", err)

    freq = psutil.cpu_freq()
    cpu_max_ghz = (freq.max or freq.current) / 1000 if freq else None

    return HardwareInfo(cpu_brand=cpu_brand,
                        cpu_physical_cores=psutil.cpu_count(logical=False),
                        cpu_logical_cores=psutil.cpu_count(logical=True),
                        cpu_max_ghz=cpu_max_ghz,
                        ram_total_gb=psutil.virtual_memory().total / (1024 ** 3))


def prime_cpu_load() -> None:
    """Discard the meaningless first `cpu_percent()` reading.

    `psutil.cpu_percent(interval=None)` reports usage *since the previous
    call* -- the very first call in a process has nothing to compare against
    and always returns `0.0`. Call this once at startup (`setup_hook`), well
    before `/status` can be invoked, so the first real reading is meaningful.
    """
    _ = psutil.cpu_percent(interval=None)


def cpu_load_percent() -> float:
    """Percent CPU utilization since the last call (or since `prime_cpu_load()`).

    Returns:
        A single float across all cores, 0-100.
    """
    return psutil.cpu_percent(interval=None)


def cpu_temp_celsius() -> float | None:
    """Average CPU package/core temperature.

    Returns:
        The average across whatever sensor entries matched, or `None` if
        `psutil` doesn't support sensor readings on this OS (e.g. Windows) or
        none of the known sensor keys were present.
    """
    sensors_fn = getattr(psutil, 'sensors_temperatures', None)
    if sensors_fn is None:
        return None

    readings = sensors_fn()
    for key in _CPU_TEMP_SENSOR_KEYS:
        entries = readings.get(key)
        if entries:
            return sum(entry.current for entry in entries) / len(entries)

    return None


def amd_gpu_temp_celsius() -> float | None:
    """Average AMD GPU temperature, via the same hwmon mechanism as `cpu_temp_celsius`.

    Returns:
        The average across whatever `amdgpu` sensor entries matched, or
        `None` on any OS other than Linux, or if no AMD GPU is present.
    """
    sensors_fn = getattr(psutil, 'sensors_temperatures', None)
    if sensors_fn is None:
        return None

    entries = sensors_fn().get(_AMD_GPU_TEMP_SENSOR_KEY)
    if not entries:
        return None

    return sum(entry.current for entry in entries) / len(entries)


def nvidia_gpu_metrics() -> list[GpuMetrics]:
    """One `GpuMetrics` per Nvidia GPU detected via NVML.

    Returns:
        `[]` if no Nvidia driver/GPU is present on this machine -- NVML
        initialization failing is the expected, common case on an AMD-only
        or GPU-less system, not something worth logging above debug level.
    """
    try:
        pynvml.nvmlInit()
    except pynvml.NVMLError as err:
        logger.debug("NVML unavailable -- %r", err)
        return []

    try:
        metrics: list[GpuMetrics] = []

        for index in range(pynvml.nvmlDeviceGetCount()):
            handle = pynvml.nvmlDeviceGetHandleByIndex(index)
            name = pynvml.nvmlDeviceGetName(handle)
            if isinstance(name, bytes):
                name = name.decode()

            temp: float | None
            try:
                temp = float(pynvml.nvmlDeviceGetTemperature(handle, pynvml.NVML_TEMPERATURE_GPU))
            except pynvml.NVMLError as err:
                logger.debug("NVML temperature read failed for %s -- %r", name, err)
                temp = None

            power: float | None
            try:
                power = pynvml.nvmlDeviceGetPowerUsage(handle) / 1000  # mW -> W
            except pynvml.NVMLError as err:
                logger.debug("NVML power read failed for %s -- %r", name, err)
                power = None

            vram_used: float | None
            vram_total: float | None
            try:
                mem_info = pynvml.nvmlDeviceGetMemoryInfo(handle)
                # `int(...)` isn't a no-op cast here -- pynvml's `_PrintableStructure`
                # overrides `__getattribute__` to transcode any `bytes` field to `str`
                # for nicer __str__ output, which throws basedpyright's inference off
                # (`.used`/`.total` come back a `bytes | str` union instead of the
                # `c_ulonglong` -> `int` they actually are at runtime).
                vram_used = int(mem_info.used) / (1024 * 1024)
                vram_total = int(mem_info.total) / (1024 * 1024)
            except pynvml.NVMLError as err:
                logger.debug("NVML memory read failed for %s -- %r", name, err)
                vram_used = None
                vram_total = None

            metrics.append(GpuMetrics(name=name, temp_celsius=temp, power_watts=power,
                                      vram_used_mb=vram_used, vram_total_mb=vram_total))

        return metrics
    finally:
        pynvml.nvmlShutdown()
