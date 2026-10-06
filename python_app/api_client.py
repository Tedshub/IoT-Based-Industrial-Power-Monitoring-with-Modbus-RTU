"""
api_client.py — Modul komunikasi REST API Sicekel WebApp.

Modul ini menangani:
  - Base URL terpusat (single source of truth) untuk seluruh komunikasi HTTP/HTTPS
  - Pengiriman telemetry pembacaan Modbus RTU ke database WebApp
  - Pengiriman sinkronisasi batch (sync) untuk data offline yang tersimpan di Excel
  - Pengiriman sinyal heartbeat (setiap 5 detik) untuk pembaruan status Online/Offline (tabel 1 baris)
  - Pengiriman sinyal Offline saat aplikasi dihentikan
  - Penanganan error non-blocking (graceful failure) saat internet putus
"""

import json
from datetime import datetime

import config

# Coba import requests, fallback ke urllib jika tidak tersedia
try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    import urllib.error
    import urllib.request
    HAS_REQUESTS = False


def get_base_url():
    """Mendapatkan Base URL utama backend Sicekel WebApp."""
    base = getattr(config, "WEBAPP_BASE_URL", "http://127.0.0.1:8000")
    return base.rstrip("/")


def get_api_url():
    """Mendapatkan URL endpoint store reading telemetri."""
    return getattr(config, "WEBAPP_API_URL", f"{get_base_url()}/api/power-meter-readings")


def get_sync_url():
    """Mendapatkan URL endpoint batch sync data offline."""
    return getattr(config, "WEBAPP_SYNC_URL", f"{get_base_url()}/api/power-meter-readings/sync")


def get_heartbeat_url():
    """Mendapatkan URL endpoint pengiriman heartbeat 5 detik."""
    return getattr(config, "WEBAPP_HEARTBEAT_URL", f"{get_base_url()}/api/device-status/heartbeat")


def get_status_url():
    """Mendapatkan URL endpoint pembacaan status online/offline."""
    return getattr(config, "WEBAPP_STATUS_URL", f"{get_base_url()}/api/device-status")


def get_offline_url():
    """Mendapatkan URL endpoint penandaan status offline saat shutdown."""
    return getattr(config, "WEBAPP_OFFLINE_URL", f"{get_base_url()}/api/device-status/offline")


def prepare_payload(data, port=None, recorded_at=None):
    """
    Menyiapkan payload JSON dari hasil pembacaan register Modbus.

    Args:
        data (dict): Dictionary hasil pembacaan register {nama_param: nilai}
        port (str, optional): Port serial yang aktif (misal 'COM3')
        recorded_at (str/datetime, optional): Waktu pembacaan data

    Returns:
        dict: Payload siap dikirim dalam format JSON
    """
    if recorded_at is None:
        recorded_at_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    elif isinstance(recorded_at, datetime):
        recorded_at_str = recorded_at.strftime("%Y-%m-%d %H:%M:%S")
    else:
        recorded_at_str = str(recorded_at)

    payload = {
        "device_name": getattr(config, "DEVICE_NAME", "FORT FCN300-3E4Y"),
        "slave_id": getattr(config, "SLAVE_ID", 1),
        "port": port,
        "timestamp": recorded_at_str,
    }

    # Masukkan seluruh parameter telemetry yang terbaca
    for k, v in data.items():
        if k in ("Status_Sync", "Tanggal", "Waktu"):
            continue
        if v is not None:
            try:
                payload[k] = float(v)
            except (ValueError, TypeError):
                payload[k] = v
        else:
            payload[k] = None

    return payload


def send_reading(data, port=None, recorded_at=None, timeout=None):
    """
    Mengirim satu data pembacaan ke backend WebApp melalui HTTP/HTTPS POST.

    Args:
        data (dict): Dictionary parameter telemetry
        port (str, optional): Port serial
        recorded_at (str/datetime, optional): Waktu pencatatan
        timeout (int, optional): Timeout koneksi HTTP dalam detik

    Returns:
        tuple: (success: bool, message: str)
    """
    if not getattr(config, "WEBAPP_API_ENABLED", True):
        return True, "Pengiriman WebApp dinonaktifkan di konfigurasi."

    api_url = get_api_url()
    req_timeout = timeout or getattr(config, "WEBAPP_API_TIMEOUT", 5)

    payload = prepare_payload(data, port=port, recorded_at=recorded_at)

    if HAS_REQUESTS:
        try:
            resp = requests.post(
                api_url,
                json=payload,
                headers={"Content-Type": "application/json", "Accept": "application/json"},
                timeout=req_timeout,
            )

            if resp.status_code in (200, 201):
                try:
                    res_json = resp.json()
                    record_id = res_json.get("data", {}).get("id")
                    id_info = f" (ID: #{record_id})" if record_id else ""
                    return True, f"Berhasil tersimpan ke database WebApp{id_info}"
                except Exception:
                    return True, "Berhasil tersimpan ke database WebApp"
            else:
                return False, f"Server mengembalikan status HTTP {resp.status_code}: {resp.text[:120]}"

        except requests.exceptions.ConnectionError:
            return False, f"Tidak dapat terhubung ke server WebApp ({api_url}). Pastikan server WebApp sudah berjalan."
        except requests.exceptions.Timeout:
            return False, f"Koneksi ke WebApp timeout ({req_timeout} detik)."
        except Exception as e:
            return False, f"Error pengiriman ke WebApp: {e}"

    else:
        # Fallback menggunakan urllib standard library
        try:
            json_bytes = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                api_url,
                data=json_bytes,
                headers={"Content-Type": "application/json", "Accept": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=req_timeout) as response:
                if response.status in (200, 201):
                    return True, "Berhasil tersimpan ke database WebApp"
                return False, f"Status HTTP {response.status}"
        except urllib.error.URLError as e:
            return False, f"Gagal terhubung ke WebApp: {e.reason}"
        except Exception as e:
            return False, f"Error: {e}"


def send_sync_batch(readings, timeout=None):
    """
    Mengirim batch data telemetry offline ke endpoint sync WebApp.

    Args:
        readings (list[dict]): Daftar payload telemetry
        timeout (int, optional): Timeout HTTP

    Returns:
        tuple: (success: bool, synced_count: int, message: str)
    """
    if not readings:
        return True, 0, "Tidak ada data yang perlu disinkronkan."

    if not getattr(config, "WEBAPP_API_ENABLED", True):
        return False, 0, "Integrasi WebApp dinonaktifkan di konfigurasi."

    sync_url = get_sync_url()
    req_timeout = timeout or getattr(config, "WEBAPP_API_TIMEOUT", 10)
    payload = {"readings": readings}

    if HAS_REQUESTS:
        try:
            resp = requests.post(
                sync_url,
                json=payload,
                headers={"Content-Type": "application/json", "Accept": "application/json"},
                timeout=req_timeout,
            )

            if resp.status_code == 200:
                res_json = resp.json()
                synced_count = res_json.get("synced_count", len(readings))
                return True, synced_count, f"Berhasil sinkronisasi {synced_count} data ke database."
            else:
                return False, 0, f"Server mengembalikan status HTTP {resp.status_code}: {resp.text[:120]}"

        except requests.exceptions.ConnectionError:
            return False, 0, f"Tidak dapat terhubung ke server WebApp ({sync_url})."
        except requests.exceptions.Timeout:
            return False, 0, f"Koneksi timeout ({req_timeout} detik)."
        except Exception as e:
            return False, 0, f"Gagal sinkronisasi data: {e}"

    else:
        try:
            json_bytes = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                sync_url,
                data=json_bytes,
                headers={"Content-Type": "application/json", "Accept": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=req_timeout) as response:
                if response.status == 200:
                    body = json.loads(response.read().decode("utf-8"))
                    synced_count = body.get("synced_count", len(readings))
                    return True, synced_count, f"Berhasil sinkronisasi {synced_count} data ke database."
                return False, 0, f"Status HTTP {response.status}"
        except Exception as e:
            return False, 0, str(e)


def sync_pending_records(data_logger_mod=None, batch_size=50):
    """
    Memeriksa dan menyinkronkan seluruh data PENDING di Excel ke database.
    Jika berhasil, status baris di Excel akan diperbarui menjadi SYNCED.

    Args:
        data_logger_mod: Modul data_logger (opsional, default import internal)
        batch_size (int): Jumlah baris per batch pengiriman

    Returns:
        tuple: (success: bool, synced_count: int, message: str)
    """
    if data_logger_mod is None:
        import data_logger as data_logger_mod

    pending_items = data_logger_mod.get_pending_rows()
    if not pending_items:
        return True, 0, "Tidak ada data pending. Semua data di Excel sudah tersinkronisasi."

    total_pending = len(pending_items)
    total_synced = 0

    # Kirim per batch
    for i in range(0, total_pending, batch_size):
        chunk = pending_items[i:i + batch_size]
        batch_payload = []
        batch_row_indices = []

        for item in chunk:
            payload = prepare_payload(
                item["data"],
                recorded_at=item["timestamp"]
            )
            batch_payload.append(payload)
            batch_row_indices.append(item["row_index"])

        ok, count, msg = send_sync_batch(batch_payload)
        if ok:
            # Perbarui status di Excel
            data_logger_mod.mark_rows_synced(batch_row_indices)
            total_synced += count
        else:
            return False, total_synced, f"Gagal saat menyinkronkan batch {i//batch_size + 1}: {msg}"

    return True, total_synced, f"Sukses menyinkronkan total {total_synced} dari {total_pending} data tertunda ke database."


def send_heartbeat(device_name=None, timeout=3):
    """
    Mengirim ping heartbeat ke backend untuk memperbarui status Online (tabel 1 baris).

    Args:
        device_name (str, optional): Nama device/program
        timeout (int): Timeout request HTTP

    Returns:
        tuple: (success: bool, data_or_msg: dict/str)
    """
    if not getattr(config, "WEBAPP_API_ENABLED", True):
        return False, "Integrasi WebApp dinonaktifkan."

    heartbeat_url = get_heartbeat_url()
    dev_name = device_name or getattr(config, "DEVICE_NAME", "FORT FCN300-3E4Y")
    payload = {"device_name": dev_name}

    if HAS_REQUESTS:
        try:
            resp = requests.post(
                heartbeat_url,
                json=payload,
                headers={"Content-Type": "application/json", "Accept": "application/json"},
                timeout=timeout,
            )
            if resp.status_code == 200:
                return True, resp.json().get("data", {})
            return False, f"Status HTTP {resp.status_code}"
        except Exception as e:
            return False, str(e)
    else:
        try:
            json_bytes = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                heartbeat_url,
                data=json_bytes,
                headers={"Content-Type": "application/json", "Accept": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=timeout) as response:
                if response.status == 200:
                    body = json.loads(response.read().decode("utf-8"))
                    return True, body.get("data", {})
                return False, f"Status HTTP {response.status}"
        except Exception as e:
            return False, str(e)


def send_offline(device_name=None, timeout=3):
    """
    Mengirim sinyal eksplisit ke backend bahwa program Python sedang dihentikan (OFFLINE).

    Args:
        device_name (str, optional): Nama device
        timeout (int): Timeout request HTTP

    Returns:
        tuple: (success: bool, message: str)
    """
    if not getattr(config, "WEBAPP_API_ENABLED", True):
        return True, "Integrasi WebApp dinonaktifkan."

    offline_url = get_offline_url()

    if HAS_REQUESTS:
        try:
            resp = requests.post(
                offline_url,
                json={"device_name": device_name or getattr(config, "DEVICE_NAME", "FORT FCN300-3E4Y")},
                headers={"Content-Type": "application/json", "Accept": "application/json"},
                timeout=timeout,
            )
            if resp.status_code == 200:
                return True, "Status device berhasil diubah ke OFFLINE di database."
            return False, f"Status HTTP {resp.status_code}"
        except Exception as e:
            return False, str(e)
    else:
        try:
            req = urllib.request.Request(
                offline_url,
                data=b"{}",
                headers={"Content-Type": "application/json", "Accept": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=timeout) as response:
                return response.status == 200, f"Status HTTP {response.status}"
        except Exception as e:
            return False, str(e)


def get_device_status(timeout=3):
    """
    Mengambil data status terkini dari tabel singleton 1 baris di database WebApp.

    Returns:
        tuple: (success: bool, status_data: dict)
    """
    status_url = get_status_url()

    if HAS_REQUESTS:
        try:
            resp = requests.get(
                status_url,
                headers={"Accept": "application/json"},
                timeout=timeout,
            )
            if resp.status_code == 200:
                return True, resp.json().get("data", {})
            return False, {"error": f"Status HTTP {resp.status_code}"}
        except Exception as e:
            return False, {"error": str(e)}
    else:
        try:
            req = urllib.request.Request(status_url, headers={"Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=timeout) as response:
                if response.status == 200:
                    body = json.loads(response.read().decode("utf-8"))
                    return True, body.get("data", {})
                return False, {"error": f"Status HTTP {response.status}"}
        except Exception as e:
            return False, {"error": str(e)}


def test_api_connection(timeout=3):
    """
    Menguji koneksi ke endpoint backend Sicekel WebApp.

    Returns:
        tuple: (success: bool, detail: str)
    """
    base_url = get_base_url()
    status_url = get_status_url()

    if HAS_REQUESTS:
        try:
            resp = requests.get(
                status_url,
                headers={"Accept": "application/json"},
                timeout=timeout,
            )
            if resp.status_code == 200:
                data = resp.json().get("data", {})
                status_str = data.get("status_label", "AKTIF")
                return True, f"Koneksi OK (HTTP 200) ke {base_url} [Device Status: {status_str}]"
            else:
                return False, f"Server merespons status HTTP {resp.status_code}"
        except requests.exceptions.ConnectionError:
            return False, f"Server WebApp offline atau URL {base_url} tidak dapat dijangkau"
        except requests.exceptions.Timeout:
            return False, f"Koneksi timeout ({timeout}s)"
        except Exception as e:
            return False, str(e)
    else:
        try:
            req = urllib.request.Request(status_url, headers={"Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=timeout) as response:
                if response.status == 200:
                    return True, f"Koneksi OK (HTTP 200) ke {base_url}"
                return False, f"Status HTTP {response.status}"
        except Exception as e:
            return False, str(e)
