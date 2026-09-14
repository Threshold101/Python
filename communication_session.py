import queue
import random
import threading

from protocol_handler import ProtocolHandler
from socket_client import SocketClient


class CommunicationSession:
    def __init__(self, host, port):
        self.host = host
        self.port = port
        self.protocol = None
        self.stop_event = threading.Event()
        self.message_received = threading.Event()
        self.connection_closed = threading.Event()
        self.connection_error = None
        self.sent_messages = queue.Queue()
        self.received_messages = queue.Queue()
        self.send_thread = None
        self.receive_thread = None

    def start(self):
        if self.send_thread and self.send_thread.is_alive():
            return

        self.protocol = ProtocolHandler(SocketClient(self.host, self.port))
        self.stop_event.clear()
        self.message_received.clear()
        self.connection_closed.clear()
        self.connection_error = None
        self.send_thread = threading.Thread(target=self._send_loop, daemon=True)
        self.receive_thread = threading.Thread(target=self._receive_loop, daemon=True)
        self.send_thread.start()
        self.receive_thread.start()

    def stop(self):
        self.stop_event.set()
        if self.protocol:
            self.protocol.close()
        for worker in (self.send_thread, self.receive_thread):
            if worker and worker.is_alive():
                worker.join(timeout=1)
        self.protocol = None

    def _send_loop(self):
        while not self.stop_event.wait(random.uniform(0.5, 2.0)):
            if self.protocol.client.stop.is_set():
                self._mark_connection_closed(self._get_socket_error())
                return

            self.message_received.clear()
            request = (
                f"GET / HTTP/1.1\r\n"
                f"Host: {self.host}\r\n"
                "Connection: keep-alive\r\n"
                "\r\n"
            ).encode("ascii")
            self.protocol.send(request)
            self.sent_messages.put(f"GET / HTTP/1.1 Host: {self.host}")

            while not self.stop_event.is_set():
                if self.message_received.wait(0.1):
                    break

    def _receive_loop(self):
        while not self.stop_event.is_set():
            messages = self.protocol.poll()
            for message in messages:
                if self.stop_event.wait(random.uniform(0.3, 1.5)):
                    return
                self.received_messages.put(message.decode("utf-8", errors="replace"))
                self.message_received.set()

            if not messages and self.protocol.client.stop.is_set():
                self._mark_connection_closed(self._get_socket_error())
                return
            if not messages:
                self.stop_event.wait(0.1)

    def _get_socket_error(self):
        try:
            return self.protocol.client.errors.get_nowait()
        except queue.Empty:
            return None

    def _mark_connection_closed(self, error=None):
        self.stop_event.set()
        self.connection_error = error
        self.connection_closed.set()
