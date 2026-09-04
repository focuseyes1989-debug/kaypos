"""Windows-account encrypted recovery for commands containing credentials."""
import base64
import ctypes
from ctypes import wintypes
import json
import os
from copy import deepcopy

from native_pos.sales_state import CheckoutJournal


def protect(data, decrypt=False):
    if os.name != 'nt': raise OSError('Credential recovery requires Windows data protection')
    class Blob(ctypes.Structure):
        _fields_ = [('size', wintypes.DWORD), ('data', ctypes.POINTER(ctypes.c_ubyte))]
    buffer = ctypes.create_string_buffer(data)
    source = Blob(len(data), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_ubyte))); output = Blob()
    crypt = ctypes.WinDLL('crypt32', use_last_error=True)
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.LocalFree.argtypes = [ctypes.c_void_p]; kernel.LocalFree.restype = ctypes.c_void_p
    function = crypt.CryptUnprotectData if decrypt else crypt.CryptProtectData
    function.argtypes = [ctypes.POINTER(Blob), ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(Blob)]
    function.restype = wintypes.BOOL
    if not function(ctypes.byref(source), None, None, None, None, 1, ctypes.byref(output)):
        raise OSError(ctypes.get_last_error(), 'Windows credential protection failed')
    try: return ctypes.string_at(output.data, output.size)
    finally: kernel.LocalFree(output.data)


class ProtectedJournal(CheckoutJournal):
    def read(self):
        data = super().read()
        if data and 'protected' in data:
            try: return json.loads(protect(base64.b64decode(data['protected'], validate=True), decrypt=True))
            except (ValueError, OSError) as exc: raise ValueError('Cannot unlock recovery using this Windows account') from exc
        return data

    def write(self, data):
        if data.get('result'):
            data = deepcopy(data)
            for key in ('password', 'bot_token', 'comm_key', 'content', 'api_key', 'cloud_url'):
                data.get('payload', {}).get('values', {}).pop(key, None)
        values = data.get('payload', {}).get('values', {})
        if any(values.get(key) for key in ('password', 'bot_token', 'comm_key', 'content', 'api_key', 'cloud_url')):
            protected = base64.b64encode(protect(json.dumps(data, ensure_ascii=False, allow_nan=False).encode())).decode()
            super().write({'payload': {'request_id': data['payload']['request_id']}, 'protected': protected})
        else: super().write(data)
