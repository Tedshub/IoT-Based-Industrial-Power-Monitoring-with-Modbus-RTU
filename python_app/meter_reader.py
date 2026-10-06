"""
meter_reader.py — Modul pembacaan data dari Power Meter FORT FCN300-3E4Y
via Modbus RTU (RS485) dengan dukungan Multi-COM & Auto-Detect.

Modul ini menangani:
  - Deteksi dan pemindaian port serial/COM yang tersedia di laptop
  - Auto-detect port converter RS485 (CH340, FTDI, CP210x, Prolific, dll.)
  - Koneksi fleksibel ke power meter via serial RS485
  - Pembacaan register sesuai konfigurasi
  - Konversi data mentah ke nilai teknik (engineering value)
"""

import struct
import time
import serial.tools.list_ports
from pymodbus.client import ModbusSerialClient

import config


# =============================================================================
#  PORT SCANNER & AUTO-DETECT
# =============================================================================

def get_available_ports():
    """
    Mendapatkan daftar seluruh port serial/COM yang terdeteksi di laptop.

    Returns:
        list[dict]: Daftar port dengan info device, description, hwid, dan is_usb.
    """
    ports = serial.tools.list_ports.comports()
    results = []
    usb_keywords = ["USB", "CH340", "FTDI", "CP210", "PROLIFIC", "PL2303", "SERIAL", "UART"]

    for p in ports:
        desc = p.description or ""
        hwid = p.hwid or ""
        combined = f"{desc} {hwid}".upper()
        is_usb = any(k in combined for k in usb_keywords)
        results.append({
            "device": p.device,
            "description": desc,
            "hwid": hwid,
            "is_usb": is_usb,
        })

    # Prioritaskan perangkat bertipe USB-Serial di awal daftar
    results.sort(key=lambda x: (not x["is_usb"], x["device"]))
    return results


def test_port_communication(port, timeout=1.5):
    """
    Menguji komunikasi Modbus RTU pada port tertentu.
    Mencoba membaca 1 register pertama dari REGISTER_MAP.

    Returns:
        tuple: (success: bool, detail: str, value: float/None)
    """
    client = ModbusSerialClient(
        port=port,
        baudrate=config.BAUDRATE,
        parity=config.PARITY,
        stopbits=config.STOPBITS,
        bytesize=config.BYTESIZE,
        timeout=timeout,
    )

    try:
        if not client.connect():
            return False, "Tidak dapat membuka port (sedang dipakai aplikasi lain atau akses ditolak)", None

        first_name = list(config.REGISTER_MAP.keys())[0]
        first_addr, first_count, first_scale = config.REGISTER_MAP[first_name]
        val = read_single_register(client, first_name, first_addr, first_count, first_scale)
        client.close()

        if val is not None:
            return True, f"Berhasil membaca {first_name} = {val}", val
        else:
            return False, "Port terbuka tetapi meter tidak merespons (cek baudrate/slave ID/kabel A-B)", None
    except Exception as e:
        try:
            client.close()
        except Exception:
            pass
        return False, f"Error: {e}", None


def find_working_port(candidate_ports=None, verbose=False):
    """
    Mencari port serial yang aktif dan merespons data Modbus dari Power Meter.

    Urutan pencarian:
    1. candidate_ports jika diberikan (misal dari argumen CLI atau list di config.py)
    2. Seluruh port USB-Serial yang terpasang di sistem
    3. Port serial lainnya

    Returns:
        str atau None: Nama port (misal 'COM3') yang berhasil diverifikasi,
        atau port USB serial pertama jika meter belum merespons tapi port ada.
    """
    available = get_available_ports()
    if not available:
        if verbose:
            print("[INFO] Tidak ada port serial/COM yang terdeteksi di laptop.")
        return None

    ports_to_try = []

    # 1. Masukkan kandidat yang valid
    if candidate_ports:
        if isinstance(candidate_ports, str):
            candidate_ports = [candidate_ports]
        for p in candidate_ports:
            if p and str(p).upper() != "AUTO" and str(p).upper() not in ports_to_try:
                ports_to_try.append(str(p).upper())

    # 2. Masukkan semua port yang terdeteksi (USB diprioritaskan)
    for p in available:
        dev = p["device"].upper()
        if dev not in ports_to_try:
            ports_to_try.append(dev)

    if verbose:
        print(f"[SCAN] Memindai {len(ports_to_try)} port serial: {', '.join(ports_to_try)}...")

    best_openable = None

    for port in ports_to_try:
        if verbose:
            print(f"  -> Menguji {port}...", end=" ", flush=True)
        ok, msg, val = test_port_communication(port, timeout=1.5)
        if ok:
            if verbose:
                print(f"[OK] ({msg})")
            return port
        else:
            if "Port terbuka" in msg and best_openable is None:
                best_openable = port
            if verbose:
                print(f"[GAGAL] ({msg})")

    # Jika tidak ada yang merespons meter, tapi ada port yang bisa dibuka atau port USB pertama
    if best_openable:
        return best_openable
    if available:
        return available[0]["device"]
    return None


def resolve_port(port=None):
    """
    Menentukan port serial yang akan digunakan.
    Mendukung nilai 'AUTO', list port prioritas, atau nama port spesifik.
    """
    target = port if port is not None else config.SERIAL_PORT

    if isinstance(target, (list, tuple)):
        found = find_working_port(candidate_ports=target)
        return found or target[0]

    if isinstance(target, str) and target.upper() == "AUTO":
        found = find_working_port()
        if found:
            return found
        ports = get_available_ports()
        return ports[0]["device"] if ports else "COM3"

    # Jika target adalah nama port spesifik (misal 'COM4')
    # Jika port tersebut tidak ada dan AUTO_DETECT_PORT True, lakukan auto fallback
    if getattr(config, "AUTO_DETECT_PORT", True):
        ports = get_available_ports()
        port_names = [p["device"].upper() for p in ports]
        if str(target).upper() not in port_names:
            fallback = find_working_port()
            if fallback:
                return fallback

    return str(target)


def create_client(port=None):
    """
    Membuat instance Modbus Serial Client berdasarkan konfigurasi atau port spesifik.
    """
    resolved_port = resolve_port(port)
    client = ModbusSerialClient(
        port=resolved_port,
        baudrate=config.BAUDRATE,
        parity=config.PARITY,
        stopbits=config.STOPBITS,
        bytesize=config.BYTESIZE,
        timeout=config.TIMEOUT,
    )
    client.active_port = resolved_port
    return client


# =============================================================================
#  DECODER DATA
# =============================================================================

def decode_float(registers):
    """
    Decode 2 register (32-bit) ke float IEEE-754.
    Mendukung konfigurasi byte order dan word order dari config.py.
    """
    if config.WORD_ORDER == "big":
        raw_bytes = struct.pack(">HH", registers[0], registers[1])
    else:
        raw_bytes = struct.pack(">HH", registers[1], registers[0])

    if config.BYTE_ORDER == "big":
        return struct.unpack(">f", raw_bytes)[0]
    else:
        return struct.unpack("<f", raw_bytes)[0]


def decode_int16(register_value, scale_factor, signed=False):
    """Decode 1 register (16-bit) ke nilai engineering."""
    if signed and register_value >= 0x8000:
        register_value -= 0x10000
    return register_value / scale_factor


def decode_int32(registers, scale_factor, signed=False):
    """Decode 2 register (32-bit) ke nilai engineering."""
    value = (registers[0] << 16) | registers[1]
    if signed and value >= 0x80000000:
        value -= 0x100000000
    return value / scale_factor


# =============================================================================
#  PEMBACAAN REGISTER MODBUS
# =============================================================================

def read_single_register(client, name, reg_address, reg_count, scale_factor):
    """
    Membaca satu parameter dari power meter.

    Returns:
        float atau None jika gagal membaca.
    """
    try:
        kwargs = {}
        try:
            from inspect import signature
            sig = signature(client.read_holding_registers)
            if "device_id" in sig.parameters:
                kwargs["device_id"] = config.SLAVE_ID
            elif "slave" in sig.parameters:
                kwargs["slave"] = config.SLAVE_ID
            elif "unit" in sig.parameters:
                kwargs["unit"] = config.SLAVE_ID
        except Exception:
            kwargs["device_id"] = config.SLAVE_ID

        if config.FUNCTION_CODE == 3:
            result = client.read_holding_registers(
                address=reg_address,
                count=reg_count,
                **kwargs,
            )
        else:
            result = client.read_input_registers(
                address=reg_address,
                count=reg_count,
                **kwargs,
            )

        if result.isError():
            return None

        registers = result.registers

        if config.DATA_TYPE == "float" and reg_count == 2:
            value = decode_float(registers)
        elif reg_count == 2:
            value = decode_int32(registers, scale_factor, config.SIGNED_REGISTERS)
        else:
            value = decode_int16(registers[0], scale_factor, config.SIGNED_REGISTERS)

        return round(value, 4)

    except Exception as e:
        return None


def read_all_parameters(client=None, port=None):
    """
    Membaca semua parameter dari power meter sesuai register map.
    Mendukung auto-fallback jika koneksi terputus.

    Returns:
        dict: {nama_parameter: nilai} atau None jika koneksi gagal.
    """
    should_close = False
    if client is None:
        client = create_client(port=port)
        should_close = True

    active_port = getattr(client, "active_port", config.SERIAL_PORT)

    try:
        if not client.connect():
            # Coba auto-fallback jika port saat ini gagal dibuka
            if getattr(config, "AUTO_DETECT_PORT", True):
                new_port = find_working_port()
                if new_port and new_port != active_port:
                    print(f"  [INFO] Port {active_port} tidak merespons, beralih ke {new_port}...")
                    try:
                        client.close()
                    except Exception:
                        pass
                    client = create_client(port=new_port)
                    active_port = new_port
                    if not client.connect():
                        print(f"[ERROR] Gagal terhubung ke power meter pada port {active_port}!")
                        return None
                else:
                    print(f"[ERROR] Gagal terhubung ke power meter!")
                    print(f"        Port: {active_port}, Baudrate: {config.BAUDRATE}")
                    return None
            else:
                print(f"[ERROR] Gagal terhubung ke power meter!")
                print(f"        Port: {active_port}, Baudrate: {config.BAUDRATE}")
                return None

        data = {}
        failed_count = 0

        for name, (reg_address, reg_count, scale_factor) in config.REGISTER_MAP.items():
            value = read_single_register(client, name, reg_address, reg_count, scale_factor)
            data[name] = value
            if value is None:
                failed_count += 1
            time.sleep(0.05)

        # Jika semua register gagal dibaca, tandai koneksi gagal
        if failed_count == len(config.REGISTER_MAP):
            return None

        return data
    finally:
        if should_close:
            try:
                client.close()
            except Exception:
                pass


def test_connection(port=None):
    """
    Test koneksi ke power meter.
    Jika port adalah 'AUTO' atau None, memindai seluruh port yang tersedia.

    Returns:
        bool: True jika berhasil terhubung dan membaca data.
    """
    target_port = port if port is not None else config.SERIAL_PORT

    if target_port == "AUTO" or (isinstance(target_port, str) and target_port.upper() == "AUTO"):
        print("[AUTO-DETECT] Memindai seluruh port serial yang tersedia...")
        working_port = find_working_port(verbose=True)
        print()
        if not working_port:
            print("[GAGAL] Tidak ada port serial yang merespons data power meter.")
            return False
        target_port = working_port

    client = create_client(port=target_port)
    actual_port = getattr(client, "active_port", target_port)

    try:
        if not client.connect():
            print("[GAGAL] Tidak dapat membuka port serial.")
            print(f"        Port: {actual_port}")
            print("        Pastikan:")
            print("        1. Kabel USB-RS485 sudah terhubung ke laptop")
            print("        2. Port COM sudah benar (jalankan 'python main.py ports')")
            print("        3. Tidak ada program lain yang sedang menggunakan port ini")
            return False

        print(f"[OK] Port serial {actual_port} berhasil dibuka.")
        print(f"     Baudrate: {config.BAUDRATE}, Parity: {config.PARITY}, "
              f"Stopbits: {config.STOPBITS}")
        print(f"     Slave ID: {config.SLAVE_ID}")
        print()

        # Coba baca register pertama sebagai test
        first_name = list(config.REGISTER_MAP.keys())[0]
        first_addr, first_count, first_scale = config.REGISTER_MAP[first_name]

        print(f"[TEST] Mencoba membaca register {first_name} "
              f"(addr=0x{first_addr:04X})...")

        value = read_single_register(client, first_name, first_addr, first_count, first_scale)

        if value is not None:
            print(f"[OK] Berhasil membaca: {first_name} = {value}")
            return True
        else:
            print("[GAGAL] Port terbuka tapi meter tidak merespons register.")
            print("        Pastikan:")
            print("        1. Kabel A (+) dan B (-) RS485 tidak terbalik")
            print("        2. Slave ID meter sesuai (saat ini: {})".format(config.SLAVE_ID))
            print("        3. Baudrate dan Parity meter sesuai")
            return False
    finally:
        try:
            client.close()
        except Exception:
            pass
