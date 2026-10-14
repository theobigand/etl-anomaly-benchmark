"""Reject network connections from Python subprocesses launched by tests."""

import socket


def _deny_connection(*_args, **_kwargs):
    raise RuntimeError("network access is disabled during pytest")


socket.socket.connect = _deny_connection
socket.socket.connect_ex = _deny_connection
socket.create_connection = _deny_connection
