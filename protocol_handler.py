import queue
from socket_client import SocketClient


class ProtocolHandler:
    def __init__(self, client: SocketClient):
        self.client = client
        self.buffer = bytearray()

    def send(self, message):
        if not isinstance(message, bytes):
            raise TypeError("HTTP messages must be bytes")
        self.client.send(message)

    def close(self):
        self.client.close()

    def poll(self):
        while True:
            try:
                self.buffer.extend(self.client.incoming.get_nowait())
            except queue.Empty:
                break

        complete_messages = []
        while True:
            message_length = self._next_message_length()
            if message_length is None:
                break
            complete_messages.append(bytes(self.buffer[:message_length]))
            del self.buffer[:message_length]

        if self.client.stop.is_set() and self.buffer:
            complete_messages.append(bytes(self.buffer))
            self.buffer.clear()

        return complete_messages

    def _next_message_length(self):
        header_end = self.buffer.find(b"\r\n\r\n")
        if header_end < 0:
            return None

        body_start = header_end + 4
        headers = bytes(self.buffer[:header_end]).lower()

        if b"transfer-encoding: chunked" in headers:
            body_length = self._chunked_body_length(body_start)
            if body_length is None:
                return None
            return body_length

        content_length = self._content_length(headers)
        if content_length is None:
            if self.client.stop.is_set():
                return len(self.buffer)
            return None

        message_length = body_start + content_length
        if len(self.buffer) < message_length:
            return None
        return message_length

    def _content_length(self, headers):
        for line in headers.split(b"\r\n"):
            if line.startswith(b"content-length:"):
                try:
                    return int(line.split(b":", 1)[1].strip())
                except ValueError:
                    return None
        return None

    def _chunked_body_length(self, body_start):
        position = body_start
        while True:
            line_end = self.buffer.find(b"\r\n", position)
            if line_end < 0:
                return None

            try:
                chunk_size = int(self.buffer[position:line_end].split(b";", 1)[0], 16)
            except ValueError:
                return None

            position = line_end + 2
            if chunk_size == 0:
                if len(self.buffer) < position + 2:
                    return None
                if self.buffer[position:position + 2] == b"\r\n":
                    return position + 2
                trailer_end = self.buffer.find(b"\r\n\r\n", position)
                if trailer_end < 0:
                    return None
                return trailer_end + 4

            if len(self.buffer) < position + chunk_size + 2:
                return None
            position += chunk_size + 2
