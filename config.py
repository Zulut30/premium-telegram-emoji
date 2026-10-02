"""Local environment loading and optional Windows user-protected token storage."""
import ctypes
import os
from pathlib import Path


class DataBlob(ctypes.Structure):
    _fields_ = [('length', ctypes.c_uint32), ('data', ctypes.POINTER(ctypes.c_ubyte))]


def _windows_protect(value: bytes, *, decrypt: bool) -> bytes:
    if os.name != 'nt':
        raise RuntimeError('Protected local token storage requires Windows.')
    buffer = (ctypes.c_ubyte * len(value)).from_buffer_copy(value)
    source = DataBlob(len(value), buffer)
    target = DataBlob()
    crypt = ctypes.WinDLL('crypt32', use_last_error=True)
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    method = crypt.CryptUnprotectData if decrypt else crypt.CryptProtectData
    method.argtypes = [ctypes.POINTER(DataBlob), ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint32, ctypes.POINTER(DataBlob)]
    method.restype = ctypes.c_int
    kernel.LocalFree.argtypes = [ctypes.c_void_p]
    kernel.LocalFree.restype = ctypes.c_void_p
    if not method(ctypes.byref(source), None, None, None, None, 1, ctypes.byref(target)):
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        return ctypes.string_at(target.data, target.length)
    finally:
        kernel.LocalFree(target.data)


def save_windows_token(repo_dir: Path, token: str) -> None:
    path = repo_dir / '.runtime' / 'bot-token.dpapi'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(_windows_protect(token.encode('utf-8'), decrypt=False))


def load_environment(repo_dir: Path) -> None:
    env_file = repo_dir / '.env'
    if env_file.exists():
        for line in env_file.read_text(encoding='utf-8-sig').splitlines():
            line = line.strip()
            if '=' in line and not line.startswith('#'):
                key, _, value = line.partition('=')
                key = key.strip()
                if not os.getenv(key):
                    os.environ[key] = value.strip().strip('"\'')
    protected = repo_dir / '.runtime' / 'bot-token.dpapi'
    if not os.getenv('BOT_TOKEN') and os.name == 'nt' and protected.exists():
        os.environ['BOT_TOKEN'] = _windows_protect(protected.read_bytes(), decrypt=True).decode('utf-8')
