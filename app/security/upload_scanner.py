"""Pemindaian lampiran lewat ClamAV INSTREAM; isi file tidak masuk log."""
import socket
import struct

from flask import current_app


def scan_upload(content_bytes):
    host = current_app.config["UPLOAD_SCANNER_HOST"]
    if not host:
        return  # Hanya development/testing; startup production mewajibkan scanner.
    try:
        with socket.create_connection(
            (host, current_app.config["UPLOAD_SCANNER_PORT"]),
            timeout=current_app.config["UPLOAD_SCANNER_TIMEOUT_SECONDS"],
        ) as connection:
            connection.sendall(b"zINSTREAM\0")
            for offset in range(0, len(content_bytes), 65536):
                chunk = content_bytes[offset:offset + 65536]
                connection.sendall(struct.pack("!I", len(chunk)) + chunk)
            connection.sendall(struct.pack("!I", 0))
            response = b""
            while b"\0" not in response and len(response) < 4096:
                chunk = connection.recv(1024)
                if not chunk:
                    break
                response += chunk
    except OSError:
        raise ValueError("pemindai lampiran belum tersedia; coba lagi nanti") from None
    if response != b"stream: OK\0":
        raise ValueError("lampiran ditolak oleh pemindai keamanan")
