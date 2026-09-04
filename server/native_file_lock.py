"""Cross-process, non-blocking lock for explicitly requested filesystem jobs."""
from contextlib import contextmanager
import os


class FileOperationBusy(ValueError):
    pass


@contextmanager
def file_lock(path):
    # Keep lock files: unlinking a locked inode would allow a second Unix owner.
    stream = open(path, 'a+b')
    try:
        stream.seek(0, os.SEEK_END)
        if not stream.tell(): stream.write(b'0'); stream.flush()
        stream.seek(0)
        try:
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc: raise FileOperationBusy('This operation is still running. Retry the same request after it finishes.') from exc
        try: yield
        finally:
            stream.seek(0)
            if os.name == 'nt': msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else: fcntl.flock(stream, fcntl.LOCK_UN)
    finally: stream.close()
