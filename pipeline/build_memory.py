"""OS-enforced memory budgets for offline builds (no background monitor)."""

from contextlib import contextmanager
import os
import sys

DEFAULT_MEMORY_LIMIT_MB = 2048


@contextmanager
def memory_budget(limit_mb=DEFAULT_MEMORY_LIMIT_MB):
    if type(limit_mb) is not int or limit_mb <= 0:
        raise ValueError("The build memory limit must be a positive integer in MiB")
    limit = limit_mb * 1024 * 1024
    stats = {"memory_limit_mb": limit_mb}
    if os.name == "nt":
        import ctypes as c
        from ctypes import wintypes as w

        # https://learn.microsoft.com/windows/win32/api/winnt/ns-winnt-jobobject_extended_limit_information
        class BasicLimits(c.Structure):
            _fields_ = [("PerProcessUserTimeLimit", c.c_int64), ("PerJobUserTimeLimit", c.c_int64),
                        ("LimitFlags", w.DWORD), ("MinimumWorkingSetSize", c.c_size_t),
                        ("MaximumWorkingSetSize", c.c_size_t), ("ActiveProcessLimit", w.DWORD),
                        ("Affinity", c.c_size_t), ("PriorityClass", w.DWORD), ("SchedulingClass", w.DWORD)]

        class ExtendedLimits(c.Structure):
            _fields_ = [("BasicLimitInformation", BasicLimits), ("IoInfo", c.c_uint64 * 6),
                        ("ProcessMemoryLimit", c.c_size_t), ("JobMemoryLimit", c.c_size_t),
                        ("PeakProcessMemoryUsed", c.c_size_t), ("PeakJobMemoryUsed", c.c_size_t)]

        kernel = c.WinDLL("kernel32", use_last_error=True)
        signatures = {
            "CreateJobObjectW": ([c.c_void_p, w.LPCWSTR], w.HANDLE),
            "SetInformationJobObject": ([w.HANDLE, c.c_int, c.c_void_p, w.DWORD], w.BOOL),
            "QueryInformationJobObject": ([w.HANDLE, c.c_int, c.c_void_p, w.DWORD, c.c_void_p], w.BOOL),
            "AssignProcessToJobObject": ([w.HANDLE, w.HANDLE], w.BOOL),
            "GetCurrentProcess": ([], w.HANDLE),
            "CloseHandle": ([w.HANDLE], w.BOOL),
        }
        for name, (args, result) in signatures.items():
            getattr(kernel, name).argtypes = args
            getattr(kernel, name).restype = result
        job = kernel.CreateJobObjectW(None, None)
        if not job:
            raise c.WinError(c.get_last_error())
        info = ExtendedLimits()
        info.BasicLimitInformation.LimitFlags = 0x100  # JOB_OBJECT_LIMIT_PROCESS_MEMORY
        info.ProcessMemoryLimit = limit
        assigned = False
        try:
            if (not kernel.SetInformationJobObject(job, 9, c.byref(info), c.sizeof(info))
                    or not kernel.AssignProcessToJobObject(job, kernel.GetCurrentProcess())):
                raise c.WinError(c.get_last_error())
            assigned = True
            yield stats
        finally:
            if assigned:
                if kernel.QueryInformationJobObject(job, 9, c.byref(info), c.sizeof(info), None):
                    stats["peak_process_memory_bytes"] = info.PeakProcessMemoryUsed
                    stats["memory_metric"] = "committed_bytes"
                info.BasicLimitInformation.LimitFlags = 0
                kernel.SetInformationJobObject(job, 9, c.byref(info), c.sizeof(info))
            kernel.CloseHandle(job)
    else:
        import resource
        previous = resource.getrlimit(resource.RLIMIT_AS)
        effective = min(limit, previous[0]) if previous[0] != resource.RLIM_INFINITY else limit
        resource.setrlimit(resource.RLIMIT_AS, (effective, previous[1]))
        try:
            yield stats
        finally:
            peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
            stats["peak_process_memory_bytes"] = peak if sys.platform == "darwin" else peak * 1024
            stats["memory_metric"] = "peak_resident_bytes"
            resource.setrlimit(resource.RLIMIT_AS, previous)
