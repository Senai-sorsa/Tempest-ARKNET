"""GPU temperature / power / load through NVIDIA's nvml.dll (no extra package). Prints one line; exit 1 if the GPU is at or above --max C.
    .venv/Scripts/python scripts/gpu_temp.py [--max 85]
"""
import ctypes
import sys

n = ctypes.WinDLL(r"C:\Windows\System32\nvml.dll")
assert n.nvmlInit_v2() == 0, "NVML did not start"
h, t, p = ctypes.c_void_p(), ctypes.c_uint(), ctypes.c_uint()
u = (ctypes.c_uint * 2)()
assert n.nvmlDeviceGetHandleByIndex_v2(0, ctypes.byref(h)) == 0
assert n.nvmlDeviceGetTemperature(h, 0, ctypes.byref(t)) == 0
watts = f"{p.value / 1000:.0f} W" if n.nvmlDeviceGetPowerUsage(h, ctypes.byref(p)) == 0 else "power n/a"
load = f"{u[0]} %" if n.nvmlDeviceGetUtilizationRates(h, u) == 0 else "load n/a"
print(f"GPU {t.value} C, {watts}, load {load}")
cap = int(sys.argv[sys.argv.index("--max") + 1]) if "--max" in sys.argv else 85
sys.exit(t.value >= cap)
