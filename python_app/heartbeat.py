"""
heartbeat.py — Modul background thread pengirim sinyal status Online/Offline (Heartbeat 5 detik).

Modul ini menangani:
  - Background daemon thread yang mengirim heartbeat ke backend setiap 5 detik.
  - Memperbarui tabel 'device_statuses' (1 baris saja) di database backend.
  - Mengirim sinyal OFFLINE saat program dihentikan (graceful shutdown / Ctrl+C).
  - Tahan terhadap gangguan jaringan (tidak crash saat internet terputus).
"""

import atexit
import threading
import time

import api_client
import config

_heartbeat_thread = None
_stop_event = threading.Event()
_is_running = False


def _heartbeat_worker():
    """Fungsi worker yang dijalankan di background thread setiap interval (5 detik)."""
    interval = getattr(config, "HEARTBEAT_INTERVAL", 5)

    while not _stop_event.is_set():
        if getattr(config, "WEBAPP_API_ENABLED", True):
            try:
                api_client.send_heartbeat(timeout=3)
            except Exception:
                pass

        # Tunggu interval atau sampai dihentikan
        _stop_event.wait(timeout=interval)


def start_heartbeat():
    """
    Memulai background heartbeat daemon thread.
    Akan otomatis mengirim status online setiap 5 detik.
    """
    global _heartbeat_thread, _is_running

    if _is_running:
        return

    _stop_event.clear()
    _is_running = True

    # Kirim heartbeat pertama kali secara langsung
    try:
        api_client.send_heartbeat(timeout=3)
    except Exception:
        pass

    _heartbeat_thread = threading.Thread(
        target=_heartbeat_worker,
        name="HeartbeatThread",
        daemon=True,
    )
    _heartbeat_thread.start()


def stop_heartbeat(send_offline_signal=True):
    """
    Menghentikan background heartbeat daemon thread dan mengirim sinyal offline.
    """
    global _is_running

    if not _is_running:
        return

    _stop_event.set()
    _is_running = False

    if send_offline_signal and getattr(config, "WEBAPP_API_ENABLED", True):
        try:
            api_client.send_offline(timeout=3)
        except Exception:
            pass


# Daftarkan shutdown hook otomatis
atexit.register(lambda: stop_heartbeat(send_offline_signal=True))
