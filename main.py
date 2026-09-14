import queue
import threading
import tkinter as tk
from tkinter import ttk
from communication_session import CommunicationSession


class CommunicationUI:
    def __init__(self, root):
        self.root = root
        self.session = None
        self.connection_thread = None
        self.connection_cancelled = threading.Event()
        self.connection_generation = 0
        self.ui_closed = False

        root.title("Message Communication")
        root.geometry("620x420")
        root.minsize(480, 320)
        root.protocol("WM_DELETE_WINDOW", self.close)

        controls = ttk.Frame(root, padding=12)
        controls.pack(fill=tk.X)

        ttk.Label(controls, text="Host").pack(side=tk.LEFT)
        self.host_entry = ttk.Entry(controls, width=16)
        self.host_entry.insert(0, "example.com")
        self.host_entry.pack(side=tk.LEFT, padx=(4, 12))

        ttk.Label(controls, text="Port").pack(side=tk.LEFT)
        self.port_entry = ttk.Entry(controls, width=7)
        self.port_entry.insert(0, "80")
        self.port_entry.pack(side=tk.LEFT, padx=(4, 12))

        self.start_button = ttk.Button(controls, text="START", command=self.start)
        self.start_button.pack(side=tk.LEFT)
        self.stop_button = ttk.Button(controls, text="STOP", command=self.stop, state=tk.DISABLED)
        self.stop_button.pack(side=tk.LEFT, padx=(8, 0))
        self.status = ttk.Label(controls, text="Stopped")
        self.status.pack(side=tk.RIGHT)

        panes = ttk.Frame(root, padding=(12, 0, 12, 12))
        panes.pack(fill=tk.BOTH, expand=True)
        panes.columnconfigure(0, weight=1)
        panes.columnconfigure(1, weight=1)
        panes.rowconfigure(1, weight=1)

        ttk.Label(panes, text="Message SENT").grid(row=0, column=0, sticky=tk.W, padx=(0, 6))
        ttk.Label(panes, text="Message RECV").grid(row=0, column=1, sticky=tk.W, padx=(6, 0))

        self.sent_log = tk.Listbox(panes)
        self.sent_log.grid(row=1, column=0, sticky="nsew", padx=(0, 6))
        self.received_log = tk.Listbox(panes)
        self.received_log.grid(row=1, column=1, sticky="nsew", padx=(6, 0))

        root.after(100, self.update_logs)

    def start(self):
        try:
            host = self.host_entry.get().strip()
            port = int(self.port_entry.get().strip())
        except ValueError as error:
            self.status.configure(text=f"Invalid port: {error}")
            return

        if not host:
            self.status.configure(text="Host is required")
            return

        if not 1 <= port <= 65535:
            self.status.configure(text="Invalid port: use a value from 1 to 65535")
            return

        self.start_button.configure(state=tk.DISABLED)
        self.stop_button.configure(state=tk.NORMAL)
        self.status.configure(text="Connecting...")
        self.connection_generation += 1
        generation = self.connection_generation
        self.connection_cancelled.clear()
        self.connection_thread = threading.Thread(
            target=self._connect_session,
            args=(host, port, generation),
            daemon=True,
        )
        self.connection_thread.start()

    def _connect_session(self, host, port, generation):
        try:
            session = CommunicationSession(host, port)
            if self.connection_cancelled.is_set() or generation != self.connection_generation:
                session.stop()
                return
            session.start()
        except OSError as error:
            self._post_to_ui(
                lambda error=error, generation=generation: self._connection_failed(
                    error, generation
                )
            )
            return

        self._post_to_ui(
            lambda session=session, generation=generation: self._connection_ready(
                session, generation
            )
        )

    def _post_to_ui(self, callback):
        if self.ui_closed:
            return
        try:
            self.root.after(0, callback)
        except tk.TclError:
            pass

    def _connection_ready(self, session, generation):
        if (
            self.ui_closed
            or self.connection_cancelled.is_set()
            or generation != self.connection_generation
        ):
            session.stop()
            return
        self.session = session
        self.status.configure(text="Running")

    def _connection_failed(self, error, generation):
        if (
            self.ui_closed
            or self.connection_cancelled.is_set()
            or generation != self.connection_generation
        ):
            return
        self.session = None
        self.start_button.configure(state=tk.NORMAL)
        self.stop_button.configure(state=tk.DISABLED)
        self.status.configure(text=f"Connection failed: {error}")

    def stop(self):
        self.connection_generation += 1
        self.connection_cancelled.set()
        if self.session:
            self.session.stop()
        self.session = None
        self.start_button.configure(state=tk.NORMAL)
        self.stop_button.configure(state=tk.DISABLED)
        self.status.configure(text="Stopped")

    def _connection_closed(self):
        error = self.session.connection_error if self.session else None
        self.stop()
        self.start_button.configure(state=tk.NORMAL)
        self.stop_button.configure(state=tk.DISABLED)
        if error:
            self.status.configure(text=f"Connection error: {error}")
        else:
            self.status.configure(text="Stopped: connection closed")

    def update_logs(self):
        if self.session and self.session.connection_closed.is_set():
            self._connection_closed()

        if not self.session:
            self.root.after(100, self.update_logs)
            return

        while True:
            try:
                self.sent_log.insert(tk.END, self.session.sent_messages.get_nowait())
                self.sent_log.yview_moveto(1)
            except queue.Empty:
                break

        while True:
            try:
                self.received_log.insert(tk.END, self.session.received_messages.get_nowait())
                self.received_log.yview_moveto(1)
            except queue.Empty:
                break

        self.root.after(100, self.update_logs)

    def close(self):
        self.ui_closed = True
        self.stop()
        self.root.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    CommunicationUI(root)
    root.mainloop()
