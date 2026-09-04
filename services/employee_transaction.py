"""Request-local transaction ownership for the shared employee service.

Legacy callers keep their own connections. Server commands can borrow one outer
transaction without changing global database configuration or monkeypatching.
"""
from contextlib import contextmanager
from contextvars import ContextVar

_connection = ContextVar('employee_transaction', default=None)


class BorrowedConnection:
    def __init__(self, connection):
        self.connection = connection

    def cursor(self):
        return self.connection.cursor()

    def commit(self):
        pass

    def close(self):
        pass

    def rollback(self):
        # A service error must propagate to the transaction owner.
        pass


def connect(factory):
    connection = _connection.get()
    return BorrowedConnection(connection) if connection is not None else factory()


def active():
    return _connection.get() is not None


@contextmanager
def transaction(connection):
    token = _connection.set(connection)
    try:
        yield
    finally:
        _connection.reset(token)
