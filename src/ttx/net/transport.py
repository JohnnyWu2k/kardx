"""Send the latest world snapshot without blocking the simulation thread."""

import socket
import threading


class SnapshotWriter:
    def __init__(self, connection: socket.socket):
        self.connection = connection
        self.condition = threading.Condition()
        self.pending: bytes | None = None
        self.closed = False
        self.thread = threading.Thread(target=self._run, name="ttx-snapshot-writer", daemon=False)

    def start(self):
        self.thread.start()

    def publish(self, snapshot: bytes):
        with self.condition:
            if not self.closed:
                # Coalesce old snapshots instead of accumulating latency.
                self.pending = snapshot
                self.condition.notify()

    def close(self):
        with self.condition:
            self.closed = True
            self.pending = None
            self.condition.notify()

    def _run(self):
        try:
            while True:
                with self.condition:
                    self.condition.wait_for(lambda: self.closed or self.pending is not None)
                    if self.closed:
                        return
                    snapshot, self.pending = self.pending, None
                self.connection.sendall(snapshot)
        except OSError:
            # Wake the receive handler so its finally block releases the actor
            # and any enemy reservation as well as the writer itself.
            try:
                self.connection.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
        finally:
            self.close()
