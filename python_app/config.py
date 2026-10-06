"""
Konfigurasi untuk koneksi Modbus RTU ke Power Meter FORT FCN300-3E4Y.

Sesuaikan nilai-nilai di bawah ini dengan setting pada power meter Anda.
Cek menu komunikasi pada layar LCD power meter untuk melihat:
  - Slave Address
  - Baud Rate
  - Parity
  - Stop Bits
"""

# =============================================================================
#  KONFIGURASI SERIAL / RS485
# =============================================================================

# Port serial (COM port) yang terhubung ke converter RS485
# Pilihan:
#   - "AUTO" : Otomatis mendeteksi port USB-Serial yang aktif di laptop (Direkomendasikan!)
#   - "COM3", "COM4", dll. : Menentukan port spesifik
#   - ["COM3", "COM4", "COM5"] : Daftar prioritas port yang akan dicoba berurutan
# Contoh Linux: "/dev/ttyUSB0", "AUTO", dll.
SERIAL_PORT = "AUTO"

# Auto-detect fallback:
# Jika True dan port yang ditentukan gagal dibuka / tidak merespons,
# program akan otomatis memindai dan mencari port serial lain yang aktif.
AUTO_DETECT_PORT = True

# Baud rate — sesuaikan dengan setting di power meter
# Pilihan umum: 1200, 2400, 4800, 9600, 19200, 38400
BAUDRATE = 9600

# Parity — sesuaikan dengan setting di power meter
# Pilihan: "N" (None), "E" (Even), "O" (Odd)
PARITY = "N"

# Stop bits — sesuaikan dengan setting di power meter
# Pilihan: 1 atau 2
STOPBITS = 1

# Data bits (biasanya 8, jangan diubah)
BYTESIZE = 8

# Timeout koneksi dalam detik
TIMEOUT = 3

# =============================================================================
#  KONFIGURASI MODBUS
# =============================================================================

# Slave ID / Address — sesuaikan dengan setting di power meter
# Default biasanya 1, cek menu komunikasi pada layar LCD meter
SLAVE_ID = 1

# =============================================================================
#  KONFIGURASI REGISTER MAP
# =============================================================================
#
#  ╔══════════════════════════════════════════════════════════════════════╗
#  ║  PENTING: Sesuaikan register address di bawah ini dengan manual    ║
#  ║  (buku panduan) dari power meter FORT FCN300-3E4Y Anda!            ║
#  ║                                                                     ║
#  ║  Default di bawah menggunakan mapping umum untuk seri ini.          ║
#  ║  Jika pembacaan menghasilkan nilai aneh, cek manual dan ubah       ║
#  ║  alamat register yang sesuai.                                       ║
#  ╚══════════════════════════════════════════════════════════════════════╝
#
#  Format: (register_address, register_count, scale_factor, description)
#
#  - register_address : Alamat awal register (0-based / hex)
#  - register_count   : Jumlah register yang dibaca (2 = 32-bit float/int)
#  - scale_factor     : Faktor pembagi untuk konversi ke satuan sebenarnya
#                        Contoh: jika meter mengembalikan 2305 dan faktor 10,
#                        maka nilai sebenarnya = 2305 / 10 = 230.5 V
#                        Gunakan 1 jika data sudah dalam format float IEEE-754
#  - data_type        : "float" (IEEE-754 32-bit) atau "int" (integer 16/32-bit)
#

# Tipe data yang digunakan oleh meter
# "float"  : Data disimpan sebagai IEEE-754 32-bit floating point (2 register)
# "int16"  : Data disimpan sebagai integer 16-bit (1 register) dengan scale factor
# "int32"  : Data disimpan sebagai integer 32-bit (2 register) dengan scale factor
DATA_TYPE = "int16"

# Register map - sesuaikan dengan manual power meter Anda
# Format: {nama_parameter: (alamat_register, jumlah_register, scale_factor)}
REGISTER_MAP = {
    # Tegangan (Voltage) — Phase R, S, T (32-bit, 2 register, scale 10000)
    "V_R":      (0x0042, 2, 10000), # Tegangan Phase R (V) -> contoh: 2328174 / 10000 = 232.8 V
    "V_S":      (0x0044, 2, 10000), # Tegangan Phase S (V)
    "V_T":      (0x0046, 2, 10000), # Tegangan Phase T (V)

    # Arus (Current) — Phase R, S, T (32-bit, 2 register, scale 1000)
    "A_R":      (0x0058, 2, 1000),  # Arus Phase R (A)
    "A_S":      (0x005A, 2, 1000),  # Arus Phase S (A)
    "A_T":      (0x005C, 2, 1000),  # Arus Phase T (A)

    # Daya Aktif (Active Power) — 32-bit, 2 register
    "kW_Total": (0x006A, 2, 1000),  # Daya Aktif Total (kW)

    # Daya Semu (Apparent Power) — 32-bit, 2 register
    "kVA_R":     (0x0074, 2, 1000), # Daya Semu Phase R (kVA)
    "kVA_S":     (0x0076, 2, 1000), # Daya Semu Phase S (kVA)
    "kVA_T":     (0x0078, 2, 1000), # Daya Semu Phase T (kVA)
    "kVA_Total": (0x007A, 2, 1000), # Daya Semu Total (kVA)

    # Daya Reaktif (Reactive Power) — 32-bit, 2 register
    "kVAR_R":     (0x006C, 2, 1000), # Daya Reaktif Phase R (kVAR)
    "kVAR_S":     (0x006E, 2, 1000), # Daya Reaktif Phase S (kVAR)
    "kVAR_T":     (0x0070, 2, 1000), # Daya Reaktif Phase T (kVAR)
    "kVAR_Total": (0x0072, 2, 1000), # Daya Reaktif Total (kVAR)

    # Power Factor (Cos Phi) — 16-bit, 1 register, scale 1000
    "PF_Total": (0x007F, 1, 1000),  # Cos Phi Total -> 1000 / 1000 = 1.000

    # Frekuensi (Frequency) — 16-bit, 1 register, scale 100
    "Freq":     (0x0080, 1, 100),   # Frekuensi (Hz) -> 5006 / 100 = 50.06 Hz
}

# =============================================================================
#  KONFIGURASI FUNCTION CODE
# =============================================================================

# Function code yang digunakan untuk membaca register
# 3 = Read Holding Registers (0x03) — paling umum
# 4 = Read Input Registers (0x04)
FUNCTION_CODE = 3

# =============================================================================
#  KONFIGURASI BYTE ORDER (untuk data type float)
# =============================================================================

# Byte order untuk konversi 32-bit float
# "big"    : Big Endian (AB CD) — paling umum
# "little" : Little Endian (CD AB)
BYTE_ORDER = "big"

# Word order untuk konversi 32-bit float
# "big"    : Big Endian (High Word dulu) — paling umum
# "little" : Little Endian (Low Word dulu)
WORD_ORDER = "big"

# =============================================================================
#  KONFIGURASI LOGGING DATA
# =============================================================================

# Interval pembacaan data dalam detik (default: 300 = 5 menit)
READ_INTERVAL = 300

# Nama file Excel untuk menyimpan data (.xlsx)
EXCEL_FILENAME = "powermeter_data.xlsx"

# (Opsional) Nama file CSV jika masih ingin menyimpan backup CSV
CSV_FILENAME = "powermeter_data.csv"

# =============================================================================
#  KONFIGURASI SIGNED / UNSIGNED
# =============================================================================

# Apakah register bernilai signed (True) atau unsigned (False)
# Untuk daya (kW, kVAR), biasanya signed agar bisa menampilkan arah daya
SIGNED_REGISTERS = False

# =============================================================================
#  KONFIGURASI SICEKEL WEB APP / API (TERPUSAT)
# =============================================================================

# Apakah integrasi data ke Web App diaktifkan (True / False)
WEBAPP_API_ENABLED = True

# Base URL utama backend Sicekel WebApp (Satu penulisan terpusat)
# Cukup ubah di sini jika port, IP, atau domain berubah (misal: "http://192.168.1.100:8000" atau "https://sicekel.com")
WEBAPP_BASE_URL = "http://127.0.0.1:8000"

# Endpoint REST API turunan (otomatis menggunakan WEBAPP_BASE_URL di atas)
WEBAPP_API_URL = f"{WEBAPP_BASE_URL.rstrip('/')}/api/power-meter-readings"
WEBAPP_SYNC_URL = f"{WEBAPP_BASE_URL.rstrip('/')}/api/power-meter-readings/sync"
WEBAPP_HEARTBEAT_URL = f"{WEBAPP_BASE_URL.rstrip('/')}/api/device-status/heartbeat"
WEBAPP_STATUS_URL = f"{WEBAPP_BASE_URL.rstrip('/')}/api/device-status"
WEBAPP_OFFLINE_URL = f"{WEBAPP_BASE_URL.rstrip('/')}/api/device-status/offline"

# Interval pengiriman status / heartbeat dalam detik (sesuai instruksi: 5 detik)
HEARTBEAT_INTERVAL = 5

# Timeout request HTTP dalam detik
WEBAPP_API_TIMEOUT = 5

# Nama perangkat / identitas meter untuk metadata database
DEVICE_NAME = "FORT FCN300-3E4Y"


