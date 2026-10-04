#!/usr/bin/env python3
"""Offline transport tests: completion, deadline, EOF and no automatic replay."""
import socket
import unittest
from unittest.mock import patch

import ipad_console


class FakeSocket:
    def __init__(self, chunks):
        self.chunks = iter(chunks)
        self.sent = []
        self.closed = False

    def recv(self, size):
        try:
            chunk = next(self.chunks)
        except StopIteration:
            raise socket.timeout
        if isinstance(chunk, Exception):
            raise chunk
        return chunk

    def sendall(self, data):
        self.sent.append(data)

    def close(self):
        self.closed = True


class ShellTests(unittest.TestCase):
    def shell(self, chunks):
        shell = ipad_console.IPadShell()
        shell.sock = FakeSocket(chunks)
        return shell

    def test_split_marker_completes_without_replay(self):
        shell = self.shell([b"/ # value\n__done_", b"123__\n/ # "])
        with patch("ipad_console.time.time_ns", return_value=123):
            self.assertEqual(shell.run("cat /proc/version"), "value")
        self.assertEqual(shell.sock.sent, [b"cat /proc/version\n", b"echo __done_123__\n"])

    def test_partial_output_at_eof_is_not_success(self):
        shell = self.shell([b"partial\n", b""])
        transport = shell.sock
        with self.assertRaises(ipad_console.ShellCommandIncomplete) as caught:
            shell.run("slow-command")
        self.assertEqual(caught.exception.partial_output, "partial\n")
        self.assertIn("disconnected", str(caught.exception))
        self.assertIsNone(shell.sock)
        self.assertTrue(transport.closed)
        self.assertEqual(len(transport.sent), 2)

    def test_deadline_uses_monotonic_time_and_closes(self):
        shell = self.shell([b"partial\n"])
        transport = shell.sock
        with patch("ipad_console.time.monotonic", side_effect=[10, 10.1, 11.1]), \
             self.assertRaises(ipad_console.ShellCommandIncomplete) as caught:
            shell.run("slow-command", timeout=1)
        self.assertIn("timed out", str(caught.exception))
        self.assertEqual(caught.exception.partial_output, "partial\n")
        self.assertTrue(transport.closed)
        self.assertIsNone(shell.sock)
        self.assertEqual(len(transport.sent), 2)

    def test_receive_error_closes_transport(self):
        shell = self.shell([ConnectionResetError("reset")])
        transport = shell.sock
        with self.assertRaises(ConnectionResetError):
            shell.run("cat /proc/version")
        self.assertIsNone(shell.sock)
        self.assertTrue(transport.closed)

    def test_send_error_is_not_retried(self):
        shell = self.shell([])
        transport = shell.sock
        with patch.object(transport, "sendall", side_effect=BrokenPipeError("closed")) as send:
            with self.assertRaises(BrokenPipeError):
                shell.run("command")
        self.assertEqual(send.call_count, 1)
        self.assertTrue(transport.closed)
        self.assertIsNone(shell.sock)

    def test_socket_timeout_can_be_followed_by_completion(self):
        shell = self.shell([socket.timeout(), b"value\n__done_123__\n"])
        with patch("ipad_console.time.time_ns", return_value=123):
            self.assertEqual(shell.run("command"), "value")

    def test_banner_drain_can_end_without_command_marker(self):
        shell = self.shell([b"banner\n", b""])
        self.assertEqual(shell._read_until(None, deadline=1), "banner\n")


if __name__ == "__main__":
    unittest.main()
