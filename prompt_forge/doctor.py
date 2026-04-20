"""Hardware detection: RAM, VRAM, CPU, disk → recommend a safe runner+model.

Uses stdlib-only methods first (shutil, platform, subprocess) and falls back
to psutil/py3nvml if they happen to be installed. Works on Windows, Linux, macOS.
"""
import os
import platform
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass, asdict
from typing import Optional, List


@dataclass
class HardwareProfile:
    os: str
    arch: str
    cpu_name: str
    cpu_cores: int
    ram_gb: float
    free_ram_gb: float
    gpu_name: Optional[str]
    vram_gb: float
    has_dedicated_gpu: bool
    free_disk_gb: float
    has_internet: bool

    def to_dict(self) -> dict:
        return asdict(self)


# ---------------------------------------------------------------------------
# RAM detection
# ---------------------------------------------------------------------------

def _ram_gb() -> tuple[float, float]:
    """Return (total_ram_gb, available_ram_gb). Uses stdlib on each OS."""
    # Preferred: psutil if installed
    try:
        import psutil
        vm = psutil.virtual_memory()
        return (vm.total / (1024**3), vm.available / (1024**3))
    except ImportError:
        pass

    system = platform.system()
    if system == "Linux":
        try:
            with open("/proc/meminfo") as f:
                info = f.read()
            total_kb = int(re.search(r"MemTotal:\s+(\d+)", info).group(1))
            avail_kb = int(re.search(r"MemAvailable:\s+(\d+)", info).group(1))
            return (total_kb / (1024**2), avail_kb / (1024**2))
        except Exception:
            return (0.0, 0.0)

    if system == "Darwin":
        try:
            total = int(subprocess.check_output(
                ["sysctl", "-n", "hw.memsize"], text=True).strip())
            # Available: rough approximation via vm_stat
            try:
                vm = subprocess.check_output(["vm_stat"], text=True)
                free_pages = int(re.search(r"Pages free:\s+(\d+)", vm).group(1))
                inactive = int(re.search(r"Pages inactive:\s+(\d+)", vm).group(1))
                avail_bytes = (free_pages + inactive) * 4096
            except Exception:
                avail_bytes = total // 2
            return (total / (1024**3), avail_bytes / (1024**3))
        except Exception:
            return (0.0, 0.0)

    if system == "Windows":
        try:
            # wmic is deprecated on Win11 but still works; fallback to ctypes
            import ctypes

            class MEMORYSTATUSEX(ctypes.Structure):
                _fields_ = [
                    ("dwLength", ctypes.c_ulong),
                    ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong),
                    ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong),
                    ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong),
                    ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("sullAvailExtendedVirtual", ctypes.c_ulonglong),
                ]

            stat = MEMORYSTATUSEX()
            stat.dwLength = ctypes.sizeof(stat)
            ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat))
            return (stat.ullTotalPhys / (1024**3),
                    stat.ullAvailPhys / (1024**3))
        except Exception:
            return (0.0, 0.0)

    return (0.0, 0.0)


# ---------------------------------------------------------------------------
# GPU / VRAM detection
# ---------------------------------------------------------------------------

def _gpu_info() -> tuple[Optional[str], float, bool]:
    """Return (gpu_name, vram_gb, is_dedicated)."""
    # 1. NVIDIA via nvidia-smi (most reliable when present)
    if shutil.which("nvidia-smi"):
        try:
            out = subprocess.check_output(
                ["nvidia-smi", "--query-gpu=name,memory.total",
                 "--format=csv,noheader,nounits"],
                text=True, timeout=5,
            ).strip()
            if out:
                first = out.splitlines()[0]
                name, vram_mb = [x.strip() for x in first.split(",")]
                return (name, int(vram_mb) / 1024, True)
        except Exception:
            pass

    system = platform.system()

    # 2. Windows: wmic / PowerShell for any GPU
    if system == "Windows":
        try:
            out = subprocess.check_output(
                ["powershell", "-NoProfile", "-Command",
                 "Get-CimInstance Win32_VideoController | "
                 "Select-Object -First 1 Name, AdapterRAM | ConvertTo-Json"],
                text=True, timeout=10,
            )
            import json
            data = json.loads(out)
            if isinstance(data, list):
                data = data[0] if data else {}
            name = data.get("Name", "") or "Unknown GPU"
            vram_bytes = data.get("AdapterRAM") or 0
            # AdapterRAM is unreliable for integrated GPUs (often capped at 4GB
            # due to DWORD limits); treat integrated as non-dedicated
            is_integrated = any(k in name.lower() for k in
                                ["intel", "uhd", "iris", "amd radeon graphics",
                                 "vega graphics", "radeon(tm) graphics"])
            vram_gb = max(0.0, vram_bytes / (1024**3))
            if is_integrated:
                # Integrated GPUs share system RAM — report 0 VRAM for planning
                return (name, 0.0, False)
            return (name, vram_gb, True)
        except Exception:
            pass

    # 3. Linux: lspci
    if system == "Linux" and shutil.which("lspci"):
        try:
            out = subprocess.check_output(["lspci"], text=True, timeout=5)
            vga_lines = [l for l in out.splitlines() if "VGA" in l or "3D" in l]
            if vga_lines:
                name = vga_lines[0].split(":", 2)[-1].strip()
                is_dedicated = any(k in name.lower() for k in
                                   ["nvidia", "geforce", "rtx", "quadro",
                                    "radeon rx", "radeon pro"])
                return (name, 0.0, is_dedicated)  # VRAM unknown without drivers
        except Exception:
            pass

    # 4. macOS: system_profiler
    if system == "Darwin":
        try:
            out = subprocess.check_output(
                ["system_profiler", "SPDisplaysDataType"],
                text=True, timeout=10,
            )
            name_match = re.search(r"Chipset Model:\s+(.+)", out)
            name = name_match.group(1).strip() if name_match else "Unknown GPU"
            # Apple Silicon = unified memory, treat as dedicated-ish
            is_apple = "apple" in name.lower()
            return (name, 0.0, is_apple)
        except Exception:
            pass

    return (None, 0.0, False)


# ---------------------------------------------------------------------------
# CPU detection
# ---------------------------------------------------------------------------

def _cpu_info() -> tuple[str, int]:
    name = platform.processor() or platform.machine() or "Unknown CPU"
    cores = os.cpu_count() or 1

    system = platform.system()
    if system == "Linux":
        try:
            with open("/proc/cpuinfo") as f:
                for line in f:
                    if line.startswith("model name"):
                        name = line.split(":", 1)[1].strip()
                        break
        except Exception:
            pass
    elif system == "Darwin":
        try:
            name = subprocess.check_output(
                ["sysctl", "-n", "machdep.cpu.brand_string"],
                text=True, timeout=5,
            ).strip()
        except Exception:
            pass
    elif system == "Windows":
        try:
            out = subprocess.check_output(
                ["powershell", "-NoProfile", "-Command",
                 "(Get-CimInstance Win32_Processor).Name"],
                text=True, timeout=10,
            ).strip()
            if out:
                name = out.splitlines()[0].strip()
        except Exception:
            pass
    return (name, cores)


# ---------------------------------------------------------------------------
# Internet + disk
# ---------------------------------------------------------------------------

def _has_internet(timeout: int = 3) -> bool:
    import urllib.request
    import urllib.error
    for url in ("https://www.google.com", "https://1.1.1.1"):
        try:
            with urllib.request.urlopen(url, timeout=timeout) as r:
                if r.status < 500:
                    return True
        except Exception:
            continue
    return False


def _free_disk_gb(path: str = ".") -> float:
    try:
        return shutil.disk_usage(path).free / (1024**3)
    except Exception:
        return 0.0


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def detect() -> HardwareProfile:
    cpu_name, cpu_cores = _cpu_info()
    total_ram, avail_ram = _ram_gb()
    gpu_name, vram_gb, has_dedicated = _gpu_info()
    return HardwareProfile(
        os=platform.system(),
        arch=platform.machine(),
        cpu_name=cpu_name,
        cpu_cores=cpu_cores,
        ram_gb=round(total_ram, 1),
        free_ram_gb=round(avail_ram, 1),
        gpu_name=gpu_name,
        vram_gb=round(vram_gb, 1),
        has_dedicated_gpu=has_dedicated,
        free_disk_gb=round(_free_disk_gb(), 1),
        has_internet=_has_internet(),
    )


# ---------------------------------------------------------------------------
# Recommendations based on hardware
# ---------------------------------------------------------------------------

# Model catalog with realistic memory requirements at Q4_K_M
# (disk_gb, ram_needed_gb_at_8k_ctx, approx_cpu_tok_per_sec_modern)
MODEL_CATALOG = [
    # Small & fast tier
    ("llama3.2:3b",   2.0,  4.0,  25, "Very fast, basic quality"),
    ("phi3.5:3.8b",   2.3,  5.0,  22, "Fast, good for simple tasks"),
    ("llama3.1:8b",   4.9,  6.5,  15, "Good balance of speed & quality"),
    ("qwen3:8b",      5.2,  7.0,  14, "Strong multilingual, fast enough"),
    # Mid tier — best quality/size for most users
    ("gemma3:12b",    7.3,  9.5,   7, "Best Polish/Spanish, 128K context"),
    ("phi4:14b",      9.1, 11.0,   5, "Best XML following (English only)"),
    ("qwen3:14b",     9.0, 11.0,   5, "Best overall, great multilingual"),
    # Large tier — needs lots of RAM
    ("mistral-small:24b", 14.3, 17.0, 3, "Near-frontier quality"),
    ("qwen3:30b-a3b-q4_K_M", 17.3, 20.0, 13, "MoE: 30B quality at 3B speed"),
]


@dataclass
class Recommendation:
    runner: str          # cloud | ollama
    reason: str
    ollama_model: Optional[str]
    warnings: List[str]
    cloud_priority: List[str]   # ordered preference of cloud providers


def recommend(profile: HardwareProfile) -> Recommendation:
    warnings: List[str] = []
    cloud_priority = ["gemini", "groq", "cerebras"]

    if profile.ram_gb < 4:
        return Recommendation(
            runner="cloud",
            reason="Less than 4GB RAM detected. Local inference is not viable; "
                   "use free cloud APIs.",
            ollama_model=None,
            warnings=["Local Ollama will not work reliably on this machine."],
            cloud_priority=cloud_priority,
        )

    # Pick the best model that BOTH fits in memory AND is fast enough to be usable.
    # On CPU-only machines, tok/s is often the real constraint — a 24B model that
    # fits but runs at 3 tok/s is worse UX than a 14B at 5 tok/s.
    safe_budget = max(profile.free_ram_gb, profile.ram_gb * 0.7) * 0.85
    # Minimum acceptable speed. GPU-accelerated: anything goes. CPU-only: need >=4.
    min_tok_s = 1 if profile.has_dedicated_gpu else 4
    best_model = None
    for name, disk, ram_needed, tok_s, desc in MODEL_CATALOG:
        if (ram_needed <= safe_budget
                and disk <= profile.free_disk_gb
                and tok_s >= min_tok_s):
            best_model = (name, disk, ram_needed, tok_s, desc)

    # Cloud always preferred when internet available, regardless of hardware
    if profile.has_internet:
        reason_parts = ["Internet is available — cloud free tiers will give "
                        "dramatically better quality and speed than any local model"]
        if not profile.has_dedicated_gpu:
            reason_parts.append("no dedicated GPU detected (CPU-only inference "
                                f"on {profile.cpu_cores} cores would be slow)")
        if profile.ram_gb < 16:
            reason_parts.append(f"only {profile.ram_gb:.0f}GB RAM limits local model size")

        ollama_model = best_model[0] if best_model else None
        if ollama_model and not profile.has_dedicated_gpu:
            warnings.append(
                f"If you do want a local fallback, {ollama_model} "
                f"(~{best_model[3]} tok/s on CPU) is the best fit for this machine."
            )
        return Recommendation(
            runner="cloud",
            reason=". ".join(reason_parts) + ".",
            ollama_model=ollama_model,
            warnings=warnings,
            cloud_priority=cloud_priority,
        )

    # Offline path: must use local
    if not best_model:
        return Recommendation(
            runner="ollama",
            reason="No internet and limited hardware. Smallest available model selected.",
            ollama_model="llama3.2:3b",
            warnings=[f"Only {profile.free_ram_gb:.1f}GB free RAM — expect slow inference."],
            cloud_priority=[],
        )

    name, disk, ram_needed, tok_s, desc = best_model
    if tok_s < 5:
        warnings.append(f"Expect ~{tok_s} tokens/sec — a 500-word response "
                        f"will take ~{int(500 / tok_s / 60)} minutes.")
    if disk > profile.free_disk_gb * 0.8:
        warnings.append(f"Model is {disk:.1f}GB and you only have "
                        f"{profile.free_disk_gb:.1f}GB free disk.")
    return Recommendation(
        runner="ollama",
        reason=f"No internet detected. Selected {name} — {desc}.",
        ollama_model=name,
        warnings=warnings,
        cloud_priority=[],
    )


# ---------------------------------------------------------------------------
# Pretty printing
# ---------------------------------------------------------------------------

def print_report(profile: HardwareProfile, rec: Recommendation) -> None:
    print("\n🩺 Prompt Forge — hardware doctor\n" + "─" * 50)
    print(f"  OS            : {profile.os} ({profile.arch})")
    print(f"  CPU           : {profile.cpu_name}")
    print(f"  CPU cores     : {profile.cpu_cores}")
    print(f"  RAM           : {profile.ram_gb:.1f} GB total, "
          f"{profile.free_ram_gb:.1f} GB free")
    print(f"  GPU           : {profile.gpu_name or '(none detected)'}")
    if profile.has_dedicated_gpu:
        print(f"  VRAM          : {profile.vram_gb:.1f} GB (dedicated)")
    else:
        print(f"  VRAM          : — (integrated/shared)")
    print(f"  Free disk     : {profile.free_disk_gb:.1f} GB")
    print(f"  Internet      : {'✓ online' if profile.has_internet else '✗ offline'}")

    print("\n📋 Recommendation\n" + "─" * 50)
    if rec.runner == "cloud":
        print(f"  Primary       : Free cloud APIs")
        print(f"  Order         : {' → '.join(rec.cloud_priority)}")
        if rec.ollama_model:
            print(f"  Offline backup: Ollama with {rec.ollama_model}")
    else:
        print(f"  Primary       : Ollama local")
        print(f"  Model         : {rec.ollama_model}")

    print(f"\n  Why: {rec.reason}")

    if rec.warnings:
        print("\n⚠ Warnings")
        for w in rec.warnings:
            print(f"    · {w}")

    print("\n💡 Next steps")
    if rec.runner == "cloud":
        print("    1. Get a free API key:")
        print("         Gemini   → https://aistudio.google.com")
        print("         Groq     → https://console.groq.com")
        print("    2. Set env var (Windows PowerShell):")
        print("         [Environment]::SetEnvironmentVariable("
              "'GEMINI_API_KEY','your_key','User')")
        print("    3. Reopen terminal, then:  forge run \"your request\"")
    else:
        print(f"    1. Install Ollama: https://ollama.com/download")
        print(f"    2. Pull model:     ollama pull {rec.ollama_model}")
        print(f"    3. Use Forge:      forge run \"your request\"")
    print()
