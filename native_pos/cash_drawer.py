"""Explicit Windows RAW drawer pulse; no database or server bootstrap."""
import ctypes
from ctypes import wintypes
import os


def authorized_local_drawer(api, printer_name):
    api._request('GET', '/api/native/sales/capabilities')
    return open_local_drawer(printer_name)


def open_local_drawer(printer_name, spool=None):
    if not str(printer_name or '').strip(): raise ValueError('Select a Windows receipt printer in Settings first')
    if spool is None:
        if os.name != 'nt': raise ValueError('Local cash drawer requires Windows')
        spool = ctypes.WinDLL('winspool.drv', use_last_error=True)
    class Document(ctypes.Structure):
        _fields_ = [('name', wintypes.LPWSTR), ('output', wintypes.LPWSTR), ('datatype', wintypes.LPWSTR)]
    signatures = {
        'OpenPrinterW': ([wintypes.LPWSTR, ctypes.POINTER(wintypes.HANDLE), ctypes.c_void_p], wintypes.BOOL),
        'StartDocPrinterW': ([wintypes.HANDLE, wintypes.DWORD, ctypes.POINTER(Document)], wintypes.DWORD),
        'StartPagePrinter': ([wintypes.HANDLE], wintypes.BOOL),
        'WritePrinter': ([wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD)], wintypes.BOOL),
        'EndPagePrinter': ([wintypes.HANDLE], wintypes.BOOL),
        'EndDocPrinter': ([wintypes.HANDLE], wintypes.BOOL),
        'ClosePrinter': ([wintypes.HANDLE], wintypes.BOOL),
    }
    for name, (args, result) in signatures.items():
        function = getattr(spool, name); function.argtypes = args; function.restype = result
    def check(ok):
        if not ok: raise OSError('Windows printer did not confirm the drawer command. Check the printer before retrying.')
    handle = wintypes.HANDLE(); check(spool.OpenPrinterW(printer_name, ctypes.byref(handle), None))
    try:
        document = Document('KAY POS Native - Cash Drawer', None, 'RAW')
        check(spool.StartDocPrinterW(handle, 1, ctypes.byref(document)))
        try:
            check(spool.StartPagePrinter(handle))
            try:
                command = b'\x1b\x70\x00\x19\xfa'; buffer = ctypes.create_string_buffer(command); written = wintypes.DWORD()
                check(spool.WritePrinter(handle, buffer, len(command), ctypes.byref(written)))
                check(written.value == len(command))
            finally: check(spool.EndPagePrinter(handle))
        finally: check(spool.EndDocPrinter(handle))
    finally: spool.ClosePrinter(handle)
    return dict(message='Drawer pulse sent to ' + printer_name + '. Check the physical drawer.')
