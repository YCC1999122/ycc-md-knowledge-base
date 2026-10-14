import ctypes
import os

d = r"d:\知识库管理工具\workspace\dist\kbdiagd2\_internal"
os.add_dll_directory(d)
os.add_dll_directory(os.path.join(d, "PySide6"))
os.add_dll_directory(os.path.join(d, "shiboken6"))
k32 = ctypes.WinDLL("kernel32", use_last_error=True)
k32.LoadLibraryExW.restype = ctypes.c_void_p
k32.LoadLibraryExW.argtypes = [ctypes.c_wchar_p, ctypes.c_void_p, ctypes.c_uint32]
names = ["shiboken6.abi3.dll", "python3.dll", "Qt6Core.dll", "pyside6.abi3.dll",
         r"PySide6\QtCore.pyd", r"PySide6\QtGui.pyd"]
for name in names:
    p = os.path.join(d, name)
    h = k32.LoadLibraryExW(p, None, 8)
    err = ctypes.get_last_error()
    print(f"{name:<24} {'OK' if h else f'FAIL WinError {err}'}", flush=True)
