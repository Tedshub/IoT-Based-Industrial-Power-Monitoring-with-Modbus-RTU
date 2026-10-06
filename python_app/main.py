"""
main.py — Program utama CLI untuk Power Meter FORT FCN300-3E4Y Logger.

Penggunaan:
    python main.py <command> [opsi]

Commands:
    start       - Mulai pembacaan data secara periodik (setiap 5 menit), offline buffer, & heartbeat
    sync        - Sinkronkan data offline (PENDING) dari Excel ke database WebApp
    read        - Baca data sekali dan tampilkan di terminal
    test        - Test koneksi ke power meter
    test-api    - Test koneksi ke backend Sicekel WebApp (HTTP/HTTPS)
    ports       - Pindai dan tampilkan seluruh COM port yang tersedia di laptop
    status      - Tampilkan info file Excel (.xlsx), status sync, dan status device online/offline
    count       - Tampilkan jumlah baris data yang tersimpan
    last [N]    - Tampilkan N data terakhir (default: 10)
    reset       - Bersihkan data lama & buat ulang struktur file Excel
    export      - Tampilkan path file Excel (.xlsx)
    help        - Tampilkan bantuan

Opsi:
    --port <PORT>   Gunakan port tertentu (contoh: --port COM3, --port AUTO)
"""

import os
import signal
import sys
import time
from datetime import datetime

# Fix encoding untuk Windows agar bisa menampilkan karakter Unicode
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

import api_client
import config
import data_logger
import heartbeat
import meter_reader


# =============================================================================
#  WARNA TERMINAL (ANSI ESCAPE CODES)
# =============================================================================

class Colors:
    HEADER = "\033[95m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    RESET = "\033[0m"
    BOLD = "\033[1m"
    UNDERLINE = "\033[4m"
    DIM = "\033[2m"


# =============================================================================
#  FORMATTING HELPERS
# =============================================================================

def format_value(param_name, val):
    """Format nilai parameter sesuai jenisnya."""
    if val is None:
        return f"{Colors.RED}N/A{Colors.RESET}"

    if param_name.startswith("V_"):
        return f"{Colors.GREEN}{val:.1f}{Colors.RESET} V"
    elif param_name.startswith("A_"):
        return f"{Colors.GREEN}{val:.3f}{Colors.RESET} A"
    elif param_name.startswith("kW"):
        return f"{Colors.YELLOW}{val:.3f}{Colors.RESET} kW"
    elif param_name.startswith("kVA"):
        return f"{Colors.YELLOW}{val:.3f}{Colors.RESET} kVA"
    elif param_name.startswith("kVAR"):
        return f"{Colors.YELLOW}{val:.3f}{Colors.RESET} kVAR"
    elif param_name.startswith("PF"):
        return f"{Colors.BLUE}{val:.3f}{Colors.RESET}"
    elif param_name == "Freq":
        return f"{Colors.CYAN}{val:.2f}{Colors.RESET} Hz"
    else:
        return f"{val}"


def print_banner():
    """Tampilkan banner aplikasi."""
    print(f"""
{Colors.CYAN}{Colors.BOLD}╔══════════════════════════════════════════════════════════════╗
║        ⚡ SICEKEL — POWER METER DATA LOGGER ⚡               ║
║             FORT FCN300-3E4Y  |  Modbus RTU / RS485           ║
╚══════════════════════════════════════════════════════════════╝{Colors.RESET}""")


def print_separator():
    print(f"{Colors.DIM}{'─' * 62}{Colors.RESET}")


# =============================================================================
#  COMMAND HANDLERS
# =============================================================================

def cmd_ports():
    """Pindai COM port dan uji respon komunikasi ke meter."""
    print_banner()
    print(f"{Colors.BOLD}🔍 Memindai Seluruh COM Port yang Aktif di Laptop...{Colors.RESET}")
    print_separator()

    available_ports = meter_reader.list_available_ports()

    if not available_ports:
        print(f"\n{Colors.RED}[PERINGATAN] Tidak ada port serial yang terdeteksi di laptop!{Colors.RESET}")
        print("  - Pastikan konverter USB to RS485 sudah dicolokkan ke port USB.")
        print("  - Cek Device Manager (Ports COM & LPT) untuk memastikan driver sudah terpasang.\n")
        return

    print(f"\nDitemukan {len(available_ports)} port serial:\n")
    for p in available_ports:
        is_current = (p['device'] == config.SERIAL_PORT)
        indicator = f" {Colors.GREEN}◄── [Config]{Colors.RESET}" if is_current else ""
        print(f"  {Colors.BOLD}• {p['device']}{Colors.RESET}{indicator}")
        print(f"    {Colors.DIM}Deskripsi: {p['description']}{Colors.RESET}")
        print(f"    {Colors.DIM}Hardware : {p['hwid']}{Colors.RESET}\n")

    print_separator()
    print(f"{Colors.BOLD}🔌 Menguji Komunikasi Modbus RTU ke Power Meter...{Colors.RESET}\n")

    working_ports = []
    for p in available_ports:
        port_name = p['device']
        sys.stdout.write(f"  Menguji {port_name} (Baudrate: {config.BAUDRATE}, Slave ID: {config.SLAVE_ID})... ")
        sys.stdout.flush()

        ok = meter_reader.test_connection(port=port_name)
        if ok:
            print(f"{Colors.GREEN}{Colors.BOLD}BERHASIL! Power meter merespons.{Colors.RESET}")
            working_ports.append(port_name)
        else:
            print(f"{Colors.RED}Tidak ada respon / Timeout.{Colors.RESET}")

    print_separator()
    if working_ports:
        print(f"\n{Colors.GREEN}{Colors.BOLD}✓ Port yang berhasil berkomunikasi: {', '.join(working_ports)}{Colors.RESET}")
        if config.SERIAL_PORT == "AUTO":
            print(f"  Setting 'SERIAL_PORT = AUTO' akan otomatis menggunakan port: {Colors.BOLD}{working_ports[0]}{Colors.RESET}")
        elif config.SERIAL_PORT in working_ports:
            print(f"  Setting port saat ini ({config.SERIAL_PORT}) sudah benar.")
        else:
            print(f"\n  {Colors.YELLOW}Saran: Ubah setting di config.py menjadi:{Colors.RESET}")
            print(f"  {Colors.BOLD}SERIAL_PORT = \"{working_ports[0]}\"{Colors.RESET}")
    else:
        print(f"\n{Colors.RED}✗ Tidak ada port yang merespons komunikasi Modbus.{Colors.RESET}")
        print("  Kemungkinan penyebab:")
        print("  1. Kabel A (+) dan B (-) RS485 tertukar. Coba tukar posisi kedua kabel.")
        print("  2. Slave ID berbeda (cek di layar LCD meter, ubah config.SLAVE_ID).")
        print("  3. Baudrate berbeda (cek di layar LCD meter, ubah config.BAUDRATE).")
    print()


def cmd_read(port=None):
    """Baca data sekali dari power meter dan tampilkan."""
    print_banner()

    client = meter_reader.create_client(port=port)
    active_port = getattr(client, "active_port", config.SERIAL_PORT)

    print(f"{Colors.BOLD}📖 Membaca data dari power meter...{Colors.RESET}")
    print(f"{Colors.DIM}   Port: {active_port} | Baudrate: {config.BAUDRATE} | "
          f"Slave ID: {config.SLAVE_ID}{Colors.RESET}")
    print_separator()

    try:
        data = meter_reader.read_all_parameters(client)
    finally:
        try:
            client.close()
        except Exception:
            pass

    if data is None:
        print(f"\n{Colors.RED}[ERROR] Gagal membaca data dari power meter pada port {active_port}!{Colors.RESET}")
        print(f"Gunakan 'python main.py ports' untuk melihat daftar COM port yang aktif.")
        return

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"\n  {Colors.BOLD}Waktu Pembacaan:{Colors.RESET} {Colors.CYAN}{now}{Colors.RESET}")
    print(f"  {Colors.BOLD}Port Aktif     :{Colors.RESET} {Colors.GREEN}{active_port}{Colors.RESET}\n")

    # Tampilkan per kategori
    categories = {
        "⚡ TEGANGAN (Voltage)": ["V_R", "V_S", "V_T"],
        "🔌 ARUS (Current)": ["A_R", "A_S", "A_T"],
        "📊 DAYA AKTIF (kW)": ["kW_R", "kW_S", "kW_T", "kW_Total"],
        "📊 DAYA SEMU (kVA)": ["kVA_R", "kVA_S", "kVA_T", "kVA_Total"],
        "📊 DAYA REAKTIF (kVAR)": ["kVAR_R", "kVAR_S", "kVAR_T", "kVAR_Total"],
        "🎯 POWER FACTOR (Cos φ)": ["PF_R", "PF_S", "PF_T", "PF_Total"],
        "🔄 FREKUENSI": ["Freq"],
    }

    for category, params in categories.items():
        available = [p for p in params if p in data]
        if available:
            print(f"  {Colors.BOLD}{category}{Colors.RESET}")
            for param in available:
                formatted = format_value(param, data[param])
                label = param.replace("_", " ").ljust(12)
                print(f"    {Colors.DIM}├─{Colors.RESET} {label}: {formatted}")
            print()

    print_separator()
    print(f"{Colors.GREEN}✓ Pembacaan selesai.{Colors.RESET}\n")


def cmd_read_and_save(port=None):
    """
    Baca data sekali, simpan ke Excel (.xlsx) dengan status sync,
    dan lakukan auto-sync saat koneksi internet aktif.
    """
    print(f"\n{Colors.BOLD}📖 Membaca data dari power meter...{Colors.RESET}")

    client = meter_reader.create_client(port=port)
    active_port = getattr(client, "active_port", config.SERIAL_PORT)

    try:
        data = meter_reader.read_all_parameters(client)
    finally:
        try:
            client.close()
        except Exception:
            pass

    if data is None:
        print(f"{Colors.RED}[ERROR] Gagal membaca data dari port {active_port}. Akan dicoba lagi pada interval berikutnya.{Colors.RESET}")
        return False

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"  {Colors.DIM}Waktu: {now} | Port: {active_port}{Colors.RESET}")

    # Tampilkan ringkasan singkat
    v_r = data.get("V_R")
    a_r = data.get("A_R")
    kw_total = data.get("kW_Total")
    pf_total = data.get("PF_Total")
    freq = data.get("Freq")

    print(f"  V(R)={Colors.GREEN}{v_r}{Colors.RESET} V | "
          f"A(R)={Colors.GREEN}{a_r}{Colors.RESET} A | "
          f"kW={Colors.YELLOW}{kw_total}{Colors.RESET} | "
          f"PF={Colors.BLUE}{pf_total}{Colors.RESET} | "
          f"Hz={Colors.CYAN}{freq}{Colors.RESET}")

    # 1. Simpan ke file Excel lokal terlebih dahulu dengan status PENDING
    # Jika internet hilang, pembacaan dan penyimpanan lokal tetap 100% aman berjalan!
    saved_row = data_logger.save_to_excel(data, sync_status="PENDING")
    if saved_row:
        count = data_logger.get_row_count()
        print(f"  {Colors.GREEN}✓ Tersimpan ke Excel (baris #{saved_row}, total: {count} baris){Colors.RESET}")
    else:
        print(f"  {Colors.RED}✗ Gagal menyimpan ke Excel{Colors.RESET}")

    # 2. Coba kirim data terkini ke database Sicekel WebApp via API
    if getattr(config, "WEBAPP_API_ENABLED", True):
        api_ok, api_msg = api_client.send_reading(data, port=active_port)
        if api_ok:
            print(f"  {Colors.GREEN}✓ {api_msg}{Colors.RESET}")
            # Tandai baris ini di Excel sebagai SYNCED
            if saved_row:
                data_logger.update_row_sync_status(saved_row, "SYNCED")

            # 3. KARENA KONEKSI AKTIF: Periksa apakah ada data PENDING sebelumnya (offline buffer)
            pending_count = data_logger.get_pending_count()
            if pending_count > 0:
                print(f"  {Colors.CYAN}🔄 Terdeteksi {pending_count} data tertunda. Menjalankan auto-sync...{Colors.RESET}")
                sync_ok, count_synced, sync_msg = api_client.sync_pending_records(data_logger)
                if sync_ok:
                    print(f"  {Colors.GREEN}✓ {sync_msg}{Colors.RESET}")
                else:
                    print(f"  {Colors.YELLOW}⚠ {sync_msg}{Colors.RESET}")
        else:
            print(f"  {Colors.YELLOW}⚠ {api_msg}{Colors.RESET}")
            print(f"    {Colors.DIM}→ Data tersimpan aman di Excel dengan status PENDING dan otomatis disinkronkan saat internet kembali.{Colors.RESET}")

    return bool(saved_row)


def cmd_sync():
    """Sinkronkan data offline (PENDING) dari file Excel ke database WebApp."""
    print_banner()
    print(f"{Colors.BOLD}🔄 Sinkronisasi Data Offline ke Database...{Colors.RESET}")
    print(f"  {Colors.DIM}Target Endpoint : {api_client.get_sync_url()}{Colors.RESET}")
    print_separator()

    pending_count = data_logger.get_pending_count()
    if pending_count == 0:
        print(f"  {Colors.GREEN}✓ Semua data di Excel sudah tersinkronisasi (Status: SYNCED).{Colors.RESET}\n")
        return

    print(f"  Ditemukan {Colors.YELLOW}{Colors.BOLD}{pending_count}{Colors.RESET} data berstatus PENDING di Excel.")
    print(f"  Mengirimkan data ke database WebApp...\n")

    ok, synced, msg = api_client.sync_pending_records(data_logger)
    print_separator()
    if ok:
        print(f"{Colors.GREEN}{Colors.BOLD}✓ Sinkronisasi Berhasil!{Colors.RESET}")
        print(f"  {msg}\n")
    else:
        print(f"{Colors.RED}{Colors.BOLD}✗ Sinkronisasi Gagal!{Colors.RESET}")
        print(f"  {msg}")
        print(f"  {Colors.YELLOW}ℹ Catatan: Data tetap aman tersimpan di Excel.{Colors.RESET}\n")


def cmd_start(port=None):
    """Mulai pembacaan data periodik dengan offline buffer & heartbeat daemon."""
    print_banner()

    # Inisialisasi port
    client = meter_reader.create_client(port=port)
    active_port = getattr(client, "active_port", config.SERIAL_PORT)
    client.close()

    interval = config.READ_INTERVAL
    interval_min = interval / 60

    print(f"{Colors.BOLD}🚀 Memulai data logging...{Colors.RESET}")
    print(f"  {Colors.DIM}Interval   : {interval} detik ({interval_min:.1f} menit){Colors.RESET}")
    print(f"  {Colors.DIM}Port Aktif : {Colors.GREEN}{active_port}{Colors.RESET}")
    print(f"  {Colors.DIM}Baudrate   : {config.BAUDRATE}{Colors.RESET}")
    print(f"  {Colors.DIM}Slave ID   : {config.SLAVE_ID}{Colors.RESET}")
    print(f"  {Colors.DIM}File Excel : {config.EXCEL_FILENAME}{Colors.RESET}")
    if getattr(config, "WEBAPP_API_ENABLED", True):
        print(f"  {Colors.DIM}Base URL   : {Colors.CYAN}{config.WEBAPP_BASE_URL}{Colors.RESET}")
        print(f"  {Colors.DIM}Heartbeat  : Tiap {config.HEARTBEAT_INTERVAL}s (Tabel 1 baris auto-update){Colors.RESET}")
    print_separator()
    print(f"{Colors.YELLOW}  Tekan Ctrl+C untuk menghentikan logging.{Colors.RESET}")
    print_separator()

    # Pastikan file Excel ada & siap
    data_logger.ensure_excel_exists()

    # Mulai background heartbeat daemon (kirim sinyal Online setiap 5 detik ke tabel 1 baris)
    if getattr(config, "WEBAPP_API_ENABLED", True):
        heartbeat.start_heartbeat()

    # Periksa data pending dari sesi sebelumnya saat program pertama kali dinyalakan
    pending_init = data_logger.get_pending_count()
    if pending_init > 0 and getattr(config, "WEBAPP_API_ENABLED", True):
        print(f"{Colors.CYAN}🔄 Menemukan {pending_init} data offline tertunda. Mencoba sinkronisasi awal...{Colors.RESET}")
        sync_ok, count_synced, sync_msg = api_client.sync_pending_records(data_logger)
        if sync_ok and count_synced > 0:
            print(f"{Colors.GREEN}✓ {sync_msg}{Colors.RESET}\n")
        else:
            print(f"{Colors.YELLOW}⚠ Backend belum terjangkau. Data tetap aman di Excel dan akan dicoba kembali saat online.{Colors.RESET}\n")

    # Handle Ctrl+C dengan baik
    running = True

    def signal_handler(sig, frame):
        nonlocal running
        running = False
        print(f"\n\n{Colors.YELLOW}⏹  Logging dihentikan oleh user.{Colors.RESET}")
        # Hentikan heartbeat dan kirim sinyal offline
        heartbeat.stop_heartbeat(send_offline_signal=True)
        count = data_logger.get_row_count()
        print(f"  Total data tersimpan: {Colors.BOLD}{count}{Colors.RESET} baris")
        print(f"  File: {data_logger.get_excel_path()}\n")
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)

    read_count = 0

    while running:
        read_count += 1
        print(f"\n{Colors.BOLD}[#{read_count}]{Colors.RESET} — "
              f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        cmd_read_and_save(port=port)

        if running:
            print(f"\n  {Colors.DIM}⏳ Pembacaan berikutnya dalam {interval_min:.0f} menit...{Colors.RESET}")

            # Countdown timer yang bisa di-interrupt
            for remaining in range(interval, 0, -1):
                if not running:
                    break
                time.sleep(1)


def cmd_test(port=None):
    """Test koneksi ke power meter."""
    print_banner()
    target_display = port or config.SERIAL_PORT
    print(f"{Colors.BOLD}🔍 Testing koneksi ke power meter (Target: {target_display})...{Colors.RESET}")
    print_separator()

    success = meter_reader.test_connection(port=port)

    print_separator()
    if success:
        print(f"{Colors.GREEN}{Colors.BOLD}✓ Test koneksi BERHASIL!{Colors.RESET}")
        print(f"  Power meter siap untuk logging data.")
    else:
        print(f"{Colors.RED}{Colors.BOLD}✗ Test koneksi GAGAL!{Colors.RESET}")
        print(f"  Gunakan 'python main.py ports' untuk mengecek daftar port yang aktif di laptop.")
    print()


def cmd_test_api():
    """Test koneksi ke REST API backend Sicekel WebApp."""
    print_banner()
    base_url = api_client.get_base_url()
    print(f"{Colors.BOLD}🌐 Testing Koneksi ke Sicekel WebApp API...{Colors.RESET}")
    print(f"  {Colors.DIM}Base URL    : {base_url}{Colors.RESET}")
    print(f"  {Colors.DIM}Endpoint API: {api_client.get_api_url()}{Colors.RESET}")
    print(f"  {Colors.DIM}Status API  : {api_client.get_status_url()}{Colors.RESET}")
    print_separator()

    ok, msg = api_client.test_api_connection(timeout=getattr(config, "WEBAPP_API_TIMEOUT", 5))
    print_separator()
    if ok:
        print(f"{Colors.GREEN}{Colors.BOLD}✓ Koneksi ke Sicekel WebApp BERHASIL!{Colors.RESET}")
        print(f"  {msg}\n")
    else:
        print(f"{Colors.RED}{Colors.BOLD}✗ Koneksi ke Sicekel WebApp GAGAL!{Colors.RESET}")
        print(f"  Detail: {msg}")
        print(f"\n  {Colors.YELLOW}ℹ Petunjuk: Pastikan server Laravel sudah berjalan.")
        print(f"  Buka terminal baru di folder 'Sicekel_WebApp' lalu ketik: 'php artisan serve'{Colors.RESET}\n")


def cmd_status(port=None):
    """Tampilkan status file Excel, info data, dan status device online/offline."""
    print_banner()
    print(f"{Colors.BOLD}📊 Status Data Logger & Koneksi{Colors.RESET}")
    print_separator()

    info = data_logger.get_file_info()

    if not info["exists"]:
        print(f"  {Colors.YELLOW}File Excel belum dibuat.{Colors.RESET}")
        print(f"  Jalankan 'python main.py start' untuk memulai logging.\n")
        return

    print(f"  {Colors.BOLD}File Excel:{Colors.RESET}")
    print(f"    Path          : {Colors.CYAN}{info['path']}{Colors.RESET}")
    print(f"    Ukuran File   : {info['file_size']}")
    print(f"    Total Baris   : {Colors.GREEN}{Colors.BOLD}{info['row_count']}{Colors.RESET} baris")
    print(f"    Data SYNCED   : {Colors.GREEN}{info.get('synced_count', 0)}{Colors.RESET} baris")
    pending = info.get('pending_count', 0)
    pending_color = Colors.YELLOW if pending > 0 else Colors.GREEN
    print(f"    Data PENDING  : {pending_color}{pending}{Colors.RESET} baris")
    print()
    print(f"  {Colors.BOLD}Rentang Data:{Colors.RESET}")
    print(f"    Data Pertama  : {info['first_record']}")
    print(f"    Data Terakhir : {info['last_record']}")

    print_separator()

    # Konfigurasi saat ini
    target = port or config.SERIAL_PORT
    print(f"\n  {Colors.BOLD}Konfigurasi Aktif:{Colors.RESET}")
    print(f"    Setting Port  : {target}")
    print(f"    Baudrate      : {config.BAUDRATE}")
    print(f"    Slave ID      : {config.SLAVE_ID}")
    print(f"    Interval      : {config.READ_INTERVAL}s ({config.READ_INTERVAL / 60:.1f} menit)")
    print(f"    Data Type     : {config.DATA_TYPE}")
    print(f"    Function Code : {config.FUNCTION_CODE}")

    # Konfigurasi Web App & Device Status
    api_enabled = getattr(config, "WEBAPP_API_ENABLED", True)
    print(f"\n  {Colors.BOLD}Sicekel Web App API & Status:{Colors.RESET}")
    print(f"    Integrasi API : {Colors.GREEN if api_enabled else Colors.RED}{'Aktif' if api_enabled else 'Nonaktif'}{Colors.RESET}")
    print(f"    Base URL      : {Colors.CYAN}{api_client.get_base_url()}{Colors.RESET}")
    print(f"    Timeout       : {getattr(config, 'WEBAPP_API_TIMEOUT', 5)}s")

    if api_enabled:
        status_ok, status_data = api_client.get_device_status()
        if status_ok:
            is_on = status_data.get("is_online", 0)
            label = status_data.get("status_label", "UNKNOWN")
            status_color = Colors.GREEN if is_on else Colors.RED
            print(f"    Status Device : {status_color}{label}{Colors.RESET}")
            print(f"    Heartbeat Terakhir : {status_data.get('last_heartbeat_at', '-')}")
            print(f"    Sync Terakhir      : {status_data.get('last_sync_at', '-')}")
        else:
            print(f"    Status Device : {Colors.DIM}(Server backend belum terhubung){Colors.RESET}")
    print()


def cmd_count():
    """Tampilkan jumlah baris data yang tersimpan."""
    count = data_logger.get_row_count()
    info = data_logger.get_file_info()
    print(f"\n{Colors.BOLD}📈 Jumlah data tersimpan:{Colors.RESET} "
          f"{Colors.GREEN}{Colors.BOLD}{count}{Colors.RESET} baris "
          f"({Colors.GREEN}{info.get('synced_count', 0)} Synced{Colors.RESET}, "
          f"{Colors.YELLOW}{info.get('pending_count', 0)} Pending{Colors.RESET})\n")


def cmd_last(n=10):
    """Tampilkan N data terakhir dari Excel."""
    print_banner()
    print(f"{Colors.BOLD}📋 {n} Data Terakhir{Colors.RESET}")
    print_separator()

    headers, rows = data_logger.get_last_n_rows(n)

    if not rows:
        print(f"  {Colors.YELLOW}Belum ada data tersimpan.{Colors.RESET}\n")
        return

    # Tampilkan header
    print(f"\n  {'No':>4}  {'Timestamp':<20}", end="")
    summary_params = ["V_R", "A_R", "kW_Total", "PF_Total", "Freq"]
    for param in summary_params:
        if param in headers:
            print(f"  {param:>10}", end="")
    if "Status_Sync" in headers:
        print(f"  {'Sync':>10}", end="")
    print()
    print(f"  {'─' * 4}  {'─' * 20}", end="")
    for _ in summary_params:
        print(f"  {'─' * 10}", end="")
    if "Status_Sync" in headers:
        print(f"  {'─' * 10}", end="")
    print()

    # Tampilkan data
    start_idx = data_logger.get_row_count() - len(rows) + 1
    for i, row in enumerate(rows):
        row_num = start_idx + i
        timestamp = row[0] if row else "-"
        print(f"  {Colors.DIM}{row_num:>4}{Colors.RESET}  {timestamp:<20}", end="")

        for param in summary_params:
            if param in headers:
                col_idx = headers.index(param)
                if col_idx < len(row):
                    val = row[col_idx]
                    try:
                        val_float = float(val)
                        if param.startswith("V_"):
                            print(f"  {Colors.GREEN}{val_float:>10.1f}{Colors.RESET}", end="")
                        elif param.startswith("A_"):
                            print(f"  {Colors.GREEN}{val_float:>10.3f}{Colors.RESET}", end="")
                        elif param.startswith("PF"):
                            print(f"  {Colors.BLUE}{val_float:>10.3f}{Colors.RESET}", end="")
                        elif param.startswith("Freq"):
                            print(f"  {Colors.CYAN}{val_float:>10.2f}{Colors.RESET}", end="")
                        else:
                            print(f"  {Colors.YELLOW}{val_float:>10.3f}{Colors.RESET}", end="")
                    except (ValueError, TypeError):
                        print(f"  {Colors.RED}{val:>10}{Colors.RESET}", end="")
                else:
                    print(f"  {'N/A':>10}", end="")

        if "Status_Sync" in headers:
            col_idx = headers.index("Status_Sync")
            val_sync = row[col_idx] if col_idx < len(row) else "-"
            if val_sync == "SYNCED":
                print(f"  {Colors.GREEN}{val_sync:>10}{Colors.RESET}", end="")
            elif val_sync == "PENDING":
                print(f"  {Colors.YELLOW}{val_sync:>10}{Colors.RESET}", end="")
            else:
                print(f"  {val_sync:>10}", end="")

        print()

    print_separator()
    total = data_logger.get_row_count()
    print(f"  {Colors.DIM}Menampilkan {len(rows)} dari {total} baris total{Colors.RESET}\n")


def cmd_export():
    """Tampilkan path file Excel."""
    excel_path = data_logger.get_excel_path()
    exists = "✓ Ada" if os.path.exists(excel_path) else "✗ Belum dibuat"
    print(f"\n{Colors.BOLD}📁 File Excel:{Colors.RESET}")
    print(f"  Path   : {Colors.CYAN}{excel_path}{Colors.RESET}")
    print(f"  Status : {exists}\n")


def cmd_reset():
    """Bersihkan dan buat ulang file Excel."""
    print_banner()
    print(f"{Colors.BOLD}🧹 Membersihkan Data Excel...{Colors.RESET}")
    print_separator()
    if data_logger.reset_excel():
        print(f"{Colors.GREEN}✓ File Excel berhasil dibersihkan dan di-format ulang sesuai REGISTER_MAP saat ini.{Colors.RESET}\n")
    else:
        print(f"{Colors.RED}✗ Gagal mereset file Excel.{Colors.RESET}\n")


def cmd_help():
    """Tampilkan bantuan penggunaan."""
    print_banner()
    print(f"{Colors.BOLD}📖 Panduan Penggunaan{Colors.RESET}")
    print_separator()
    print(f"""
  {Colors.BOLD}python main.py <command> [--port <PORT>]{Colors.RESET}

  {Colors.BOLD}Commands:{Colors.RESET}

    {Colors.GREEN}ports{Colors.RESET}       Pindai & tampilkan seluruh COM port yang ada di laptop
                serta tes komunikasi langsung ke Power Meter.

    {Colors.GREEN}start{Colors.RESET}       Mulai pembacaan data secara periodik (setiap {config.READ_INTERVAL // 60} menit)
                - Data otomatis disimpan ke Excel (.xlsx).
                - Jika internet hilang, pembacaan tetap berjalan & berstatus PENDING di Excel.
                - Saat internet kembali, data pending otomatis disinkronkan ke database.
                - Menjalankan heartbeat daemon 5 detik untuk status Online/Offline.
                Tekan Ctrl+C untuk menghentikan.

    {Colors.GREEN}sync{Colors.RESET}        Sinkronkan seluruh data PENDING di Excel secara manual ke database.

    {Colors.GREEN}read{Colors.RESET}        Baca data sekali dan tampilkan di terminal.
                Data TIDAK disimpan ke Excel.

    {Colors.GREEN}test{Colors.RESET}        Test koneksi ke power meter.
                Berguna untuk memastikan kabel & konfigurasi sudah benar.

    {Colors.GREEN}test-api{Colors.RESET}    Test koneksi ke REST API backend Sicekel WebApp.
                Memastikan base URL & endpoint dapat dijangkau.

    {Colors.GREEN}status{Colors.RESET}      Tampilkan info lengkap: file Excel, status sync,
                status device online/offline, dan konfigurasi aktif.

    {Colors.GREEN}count{Colors.RESET}       Tampilkan jumlah baris data yang berhasil disimpan.

    {Colors.GREEN}last [N]{Colors.RESET}    Tampilkan N data terakhir (default: 10).
                Contoh: python main.py last 20

    {Colors.GREEN}reset{Colors.RESET}       Bersihkan data lama & buat ulang struktur Excel sesuai konfigurasi.

    {Colors.GREEN}export{Colors.RESET}      Tampilkan path file Excel (.xlsx).

    {Colors.GREEN}help{Colors.RESET}        Tampilkan bantuan ini.

  {Colors.BOLD}Opsi Port:{Colors.RESET}

    {Colors.CYAN}--port <PORT>{Colors.RESET}  Tentukan port serial secara manual (default: {config.SERIAL_PORT})
                Contoh:
                  python main.py start --port COM3
                  python main.py test --port AUTO
                  python main.py read --port COM4

  {Colors.BOLD}Contoh:{Colors.RESET}

    python main.py ports         # Cek semua COM port di laptop
    python main.py test          # Cek koneksi meter (otomatis deteksi port)
    python main.py read          # Baca nilai saat ini
    python main.py start         # Mulai logging periodik
    python main.py sync          # Sinkronkan data offline tertunda
""")


# ============================================================================
#  MAIN ENTRY POINT & ARGUMENT PARSING
# ============================================================================

def parse_args():
    """Parse argumen baris perintah."""
    args = sys.argv[1:]
    port = None
    cleaned = []

    i = 0
    while i < len(args):
        arg = args[i]
        if arg in ("--port", "-p") and i + 1 < len(args):
            port = args[i + 1]
            i += 2
        elif arg.startswith("--port="):
            port = arg.split("=", 1)[1]
            i += 1
        else:
            cleaned.append(arg)
            i += 1

    return port, cleaned


def main():
    """Entry point program."""
    custom_port, cleaned_args = parse_args()

    if not cleaned_args:
        cmd_help()
        return

    command = cleaned_args[0].lower()

    if command in ("ports", "scan", "comports"):
        cmd_ports()
    elif command == "start":
        cmd_start(port=custom_port)
    elif command == "sync":
        cmd_sync()
    elif command == "read":
        cmd_read(port=custom_port)
    elif command == "test":
        cmd_test(port=custom_port)
    elif command in ("test-api", "testapi", "api"):
        cmd_test_api()
    elif command == "status":
        cmd_status(port=custom_port)
    elif command == "count":
        cmd_count()
    elif command in ("reset", "clean"):
        cmd_reset()
    elif command == "last":
        n = 10
        if len(cleaned_args) > 1:
            try:
                n = int(cleaned_args[1])
            except ValueError:
                print(f"{Colors.RED}[ERROR] Argumen harus berupa angka.{Colors.RESET}")
                return
        cmd_last(n)
    elif command == "export":
        cmd_export()
    elif command in ("help", "-h", "--help"):
        cmd_help()
    else:
        print(f"\n{Colors.RED}[ERROR] Command tidak dikenal: '{command}'{Colors.RESET}")
        print(f"Gunakan 'python main.py help' untuk melihat daftar command.\n")


if __name__ == "__main__":
    main()
