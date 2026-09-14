import socket
import threading
import queue


CONNECT_TIMEOUT = 2


class SocketClient:
    def __init__(self, host, port):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            self.sock.settimeout(CONNECT_TIMEOUT)
            self.sock.connect((host, port))
        except OSError as error:
            self.sock.close()
            raise ConnectionError(
                f"Could not connect to {host}:{port}: {error}"
            ) from error
        self.sock.settimeout(None)

        self.incoming = queue.Queue()   # messages from reader → main
        self.outgoing = queue.Queue()   # messages from main → writer
        self.errors = queue.Queue()
        self.stop = threading.Event()

        self.reader_thread = threading.Thread(target=self._reader, daemon=True)
        self.writer_thread = threading.Thread(target=self._writer, daemon=True)

        self.reader_thread.start()
        self.writer_thread.start()

    # ---------------- Reader Thread ----------------
    def _reader(self):
        try:
            while not self.stop.is_set():
                data = self.sock.recv(4096)
                if not data:
                    break
                self.incoming.put(data)   # push to main thread
        except OSError as error:
            if not self.stop.is_set():
                self.errors.put(error)
        finally:
            self.stop.set()

    # ---------------- Writer Thread ----------------
    def _writer(self):
        try:
            while not self.stop.is_set():
                try:
                    msg = self.outgoing.get(timeout=0.1)
                except queue.Empty:
                    continue
                try:
                    self.sock.sendall(msg)
                except OSError as error:
                    if not self.stop.is_set():
                        self.errors.put(error)
                    break
        finally:
            self.stop.set()

    # ---------------- Public API ----------------
    def send(self, data: bytes):
        if not self.stop.is_set():
            self.outgoing.put(data)

    def close(self):
        self.stop.set()
        try:
            self.sock.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        try:
            self.sock.close()
        except OSError:
            pass
        self.reader_thread.join()
        self.writer_thread.join()
