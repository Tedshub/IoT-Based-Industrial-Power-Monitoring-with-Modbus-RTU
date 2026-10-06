# ⚡ Power Meter Data Logger — FORT FCN300-3E4Y

Program Python CLI untuk membaca data listrik dari **Power Meter FORT FCN300-3E4Y** melalui komunikasi **Modbus RTU / RS485**, dan menyimpannya ke file Excel (`.xlsx`) secara periodik (setiap 5 menit).

## 📋 Daftar Isi

- [Parameter yang Dibaca](#parameter-yang-dibaca)
- [Kebutuhan Hardware](#kebutuhan-hardware)
- [Wiring / Koneksi Hardware](#wiring--koneksi-hardware)
- [Setting Power Meter](#setting-power-meter)
- [Instalasi Software](#instalasi-software)
- [Konfigurasi Program](#konfigurasi-program)
- [Cara Menjalankan Program](#cara-menjalankan-program)
- [Daftar Command CLI](#daftar-command-cli)
- [Struktur File Excel](#struktur-file-excel)
- [Troubleshooting](#troubleshooting)
- [Struktur Project](#struktur-project)

---

## Parameter yang Dibaca

| Parameter | Simbol | Satuan | Keterangan |
|-----------|--------|--------|------------|
| Tegangan Phase R, S, T | V_R, V_S, V_T | Volt (V) | Tegangan per phase |
| Arus Phase R, S, T | A_R, A_S, A_T | Ampere (A) | Arus per phase |
| Daya Aktif | kW_R, kW_S, kW_T, kW_Total | Kilowatt (kW) | Daya nyata |
| Daya Semu | kVA_R, kVA_S, kVA_T, kVA_Total | Kilovolt-Ampere (kVA) | Daya semu |
| Daya Reaktif | kVAR_R, kVAR_S, kVAR_T, kVAR_Total | Kilovolt-Ampere Reaktif (kVAR) | Daya reaktif |
| Power Factor | PF_R, PF_S, PF_T, PF_Total | - | Cos phi (0 ~ 1.0) |
| Frekuensi | Freq | Hertz (Hz) | Frekuensi jaringan |

---

## Kebutuhan Hardware

### 1. Power Meter FORT FCN300-3E4Y
- Power meter sudah terpasang dan berfungsi pada panel listrik.
- Pastikan CT (Current Transformer) ratio sudah diprogram dengan benar pada meter.

### 2. Converter USB to RS485
- **Rekomendasi**: CH340/FT232 USB to RS485 converter module.
- Bisa dibeli di Tokopedia/Shopee dengan harga ~Rp 15.000 - 50.000.
- Pastikan converter mendukung **half-duplex RS485**.

### 3. Kabel Twisted Pair
- Gunakan kabel twisted pair (UTP Cat5e bisa digunakan — ambil 1 pair saja).
- Panjang kabel disarankan **maksimal 100 meter** untuk komunikasi yang stabil.

### 4. Komputer / Laptop
- Windows / Linux / macOS.
- Memiliki port USB yang tersedia.
- Python 3.8 atau lebih baru sudah terinstall.

---

## Wiring / Koneksi Hardware

### Diagram Koneksi

```
┌─────────────────┐         Kabel RS485          ┌─────────────────────┐
│   KOMPUTER /    │         (Twisted Pair)        │   POWER METER       │
│   LAPTOP        │                               │   FCN300-3E4Y       │
│                 │    ┌──────────────────────┐    │                     │
│  USB ◄──────────┼───►│  USB to RS485       │    │                     │
│  Port           │    │  Converter Module    │    │   Terminal RS485    │
│                 │    │                      │    │                     │
│                 │    │  A+ ─────────────────┼───►│   A+ (Pin 14)      │
│                 │    │  B- ─────────────────┼───►│   B- (Pin 15)      │
│                 │    │  GND ────────────────┼───►│   GND (opsional)   │
│                 │    └──────────────────────┘    │                     │
└─────────────────┘                               └─────────────────────┘
```

### Langkah Koneksi

1. **Matikan suplai daya** ke power meter sebelum melakukan koneksi (jika memungkinkan).
2. **Hubungkan converter USB to RS485** ke komputer via port USB.
3. **Hubungkan kabel RS485** dari converter ke terminal power meter:
   - **A+** converter → **A+** power meter (biasanya terminal 14)
   - **B-** converter → **B-** power meter (biasanya terminal 15)
   - **GND** (opsional) untuk jarak jauh
4. **Nyalakan kembali** power meter.
5. **Periksa Device Manager** (Windows) untuk mengetahui nomor COM port:
   - Klik kanan **Start** → **Device Manager**
   - Buka **Ports (COM & LPT)**
   - Catat nomor COM port converter (misal: **COM3**)

> ⚠️ **PERINGATAN KESELAMATAN**: Power meter terhubung ke jaringan listrik bertegangan tinggi. Pastikan semua koneksi pada terminal RS485 dilakukan oleh teknisi yang berkompeten. JANGAN menyentuh terminal tegangan tinggi pada power meter.

### Catatan Penting Pin RS485 pada FCN300-3E4Y

| Pin | Fungsi | Keterangan |
|-----|--------|------------|
| 14 | A+ (Data+) | Sinyal RS485 positif |
| 15 | B- (Data-) | Sinyal RS485 negatif |

> 📌 **Nomor pin** bisa berbeda tergantung versi hardware. Selalu cek label pada body meter atau buku manual yang disertakan.

---

## Setting Power Meter

Setting komunikasi pada layar LCD power meter harus sesuai dengan konfigurasi di file `config.py`.

### Cara Akses Menu Komunikasi di Power Meter:

1. Tekan tombol **SET** / **MENU** pada power meter.
2. Navigasi ke menu **Comm** / **Communication** / **RS485**.
3. Catat dan/atau sesuaikan parameter berikut:

| Parameter | Nilai Default | Keterangan |
|-----------|--------------|------------|
| **Address (Slave ID)** | 1 | Alamat Modbus meter (1-247) |
| **Baud Rate** | 9600 | Kecepatan komunikasi |
| **Parity** | None (N) | Cek bit paritas |
| **Stop Bits** | 1 | Jumlah stop bit |
| **Protocol** | Modbus RTU | Protokol komunikasi |

4. Tekan **ENT** / **OK** untuk menyimpan.
5. **Catat semua setting** — akan dibutuhkan untuk konfigurasi `config.py`.

---

## Instalasi Software

### 1. Pastikan Python Sudah Terinstall

```bash
python --version
```

Harus menampilkan **Python 3.8** atau lebih baru. Jika belum terinstall, download dari [python.org](https://www.python.org/downloads/).

### 2. Buka Terminal / Command Prompt

Navigasi ke direktori project:

```bash
cd "c:\AUDIT TA\jajal jajal"
```

### 3. Buat Virtual Environment (Jika Belum Ada)

Virtual environment sudah dibuat di direktori ini. Jika perlu membuat ulang:

```bash
python -m venv venv
```

### 4. Aktifkan Virtual Environment

**Windows (Command Prompt):**
```bash
venv\Scripts\activate
```

**Windows (PowerShell):**
```powershell
.\venv\Scripts\Activate.ps1
```

> Jika ada error di PowerShell tentang execution policy, jalankan dulu:
> ```powershell
> Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
> ```

**Linux / macOS:**
```bash
source venv/bin/activate
```

Setelah aktif, terminal akan menampilkan `(venv)` di awal baris:
```
(venv) c:\AUDIT TA\jajal jajal>
```

### 5. Install Dependencies

```bash
pip install -r requirements.txt
```

Output yang diharapkan:
```
Successfully installed pymodbus-3.x.x pyserial-3.x
```

### 6. Verifikasi Instalasi

```bash
pip list
```

Pastikan `pymodbus` dan `pyserial` muncul di daftar.

---

## Konfigurasi Program

### Edit File `config.py`

Buka file `config.py` dengan text editor dan sesuaikan:

#### A. Konfigurasi Serial Port (Multi-COM & Auto-Detect)

```python
# Pilihan:
# "AUTO" : Otomatis mendeteksi port USB-Serial yang aktif di laptop (Direkomendasikan!)
# "COM3", "COM4", dll. : Menentukan port tertentu
# ["COM3", "COM4"] : Daftar prioritas port yang akan dicoba berurutan
SERIAL_PORT = "AUTO"
AUTO_DETECT_PORT = True   # Fallback otomatis jika port utama terputus / berganti
BAUDRATE = 9600          # Sesuaikan dengan setting meter
PARITY = "N"             # "N" (None), "E" (Even), "O" (Odd)
STOPBITS = 1             # 1 atau 2
```

#### B. Konfigurasi Modbus

```python
SLAVE_ID = 1             # Sesuaikan dengan setting meter
FUNCTION_CODE = 3        # 3 = Holding Register, 4 = Input Register
```

#### C. Register Map ⚠️ PENTING

**Alamat register HARUS disesuaikan dengan manual (buku panduan) power meter Anda!**

Default yang ada di `config.py` menggunakan mapping umum. Jika pembacaan menghasilkan nilai aneh/tidak masuk akal:

1. Buka buku manual FCN300-3E4Y yang disertakan saat pembelian.
2. Cari bagian **"Register Map"** atau **"Communication Address"**.
3. Update alamat register di `config.py` sesuai manual.

```python
# Contoh format:
# "nama_parameter": (alamat_register, jumlah_register, scale_factor)
REGISTER_MAP = {
    "V_R":  (0x0000, 1, 10),   # Alamat 0x0000, 1 register, bagi 10
    # ... sesuaikan dengan manual ...
}
```

#### D. Tipe Data

```python
# Pilih sesuai format data yang digunakan meter:
DATA_TYPE = "int16"     # "int16", "int32", atau "float"
```

- **int16**: Data 16-bit integer, 1 register, dengan scale factor.
- **int32**: Data 32-bit integer, 2 register, dengan scale factor.
- **float**: Data 32-bit IEEE-754 floating point, 2 register.

> 💡 **Tips**: Jika tidak yakin, mulai dengan `"int16"`. Jika nilai yang terbaca terlalu besar/kecil/aneh, coba ubah ke `"int32"` atau `"float"`, dan sesuaikan `register_count` menjadi 2.

#### E. Interval Pembacaan

```python
READ_INTERVAL = 300      # 300 detik = 5 menit
```

---

## Cara Menjalankan Program

> ⚠️ Pastikan virtual environment sudah aktif! (lihat tanda `(venv)` di terminal)

### Langkah 1: Test Koneksi

Selalu test koneksi dulu sebelum memulai logging:

```bash
python main.py test
```

Jika berhasil:
```
[OK] Port serial COM3 berhasil dibuka.
[TEST] Mencoba membaca register V_R (addr=0x0000)...
[OK] Berhasil membaca: V_R = 230.5
✓ Test koneksi BERHASIL!
```

### Langkah 2: Baca Data Sekali (Opsional)

Untuk melihat semua parameter tanpa menyimpan ke CSV:

```bash
python main.py read
```

### Langkah 3: Mulai Logging Data

```bash
python main.py start
```

Program akan:
1. ✅ Membuat file CSV otomatis jika belum ada.
2. ✅ Membaca data dari power meter.
3. ✅ Menampilkan ringkasan data di terminal.
4. ✅ Menyimpan data ke CSV.
5. ✅ Menunggu 5 menit lalu mengulang dari langkah 2.

Tekan **Ctrl+C** kapan saja untuk menghentikan logging.

### Langkah 4: Cek Status Data

Di terminal lain (atau setelah menghentikan logging):

```bash
python main.py status
python main.py count
python main.py last 20
```

---

## Daftar Command CLI

| Command | Fungsi | Contoh |
|---------|--------|--------|
| `ports` | Pindai & tampilkan seluruh COM port di laptop & tes komunikasi meter | `python main.py ports` |
| `start` | Mulai logging data periodik (5 menit) ke Excel, offline buffer, & heartbeat | `python main.py start` |
| `sync` | Sinkronkan data offline (PENDING) dari Excel ke database WebApp secara manual | `python main.py sync` |
| `read` | Baca data sekali, tampilkan tanpa simpan | `python main.py read` |
| `test` | Test koneksi ke power meter (otomatis deteksi port) | `python main.py test` |
| `test-api` | Test koneksi ke REST API backend Sicekel WebApp | `python main.py test-api` |
| `status` | Info lengkap: file Excel, status sync, status device online/offline & config | `python main.py status` |
| `count` | Jumlah baris data yang tersimpan di Excel (Synced vs Pending) | `python main.py count` |
| `last [N]` | Tampilkan N data terakhir (default: 10) beserta status sync | `python main.py last 20` |
| `reset` | Bersihkan data lama & buat ulang struktur Excel | `python main.py reset` |
| `export` | Tampilkan path file Excel | `python main.py export` |
| `help` | Tampilkan bantuan penggunaan | `python main.py help` |

> 💡 **Opsi Pemilihan Port `--port`:**
> Anda bisa menentukan port secara manual pada perintah apa pun, contoh:
> ```bash
> python main.py ports               # Cek port mana saja yang ada di laptop
> python main.py test --port COM3    # Tes spesifik di COM3
> python main.py start --port AUTO   # Logging dengan auto-detect
> python main.py sync                # Sinkronkan data offline yang tertunda
> ```

---

## Fitur Offline Buffering & Sinkronisasi Otomatis

1. **Penyimpanan Lokal Mandiri:**
   Ketika laptop tidak terhubung ke internet atau server WebApp sedang dimatikan, proses pembacaan Modbus RTU dari power meter **tidak akan berhenti**. Setiap pembacaan disimpan ke file Excel lokal `powermeter_data.xlsx` dengan kolom `Status_Sync = PENDING`.
2. **Auto-Sync saat Online Kembali:**
   Segera setelah koneksi internet/server kembali pulih, saat siklus pembacaan berikutnya berhasil mengirim data, sistem otomatis mendeteksi baris-baris berstatus `PENDING` di Excel dan mengirimkannya dalam batch ke API `/api/power-meter-readings/sync`.
3. **Pembaruan Status Excel:**
   Setelah database mengonfirmasi penerimaan data, status baris di Excel secara otomatis diubah menjadi `SYNCED` dengan warna hijau.

---

## Fitur Heartbeat & Status Online/Offline (Tabel 1 Baris)

- **Daemon 5 Detik:** Background thread di program Python mengirim sinyal ping setiap 5 detik ke endpoint `/api/device-status/heartbeat`.
- **Tabel Singleton:** Backend memperbarui tabel `device_statuses` yang **hanya memiliki 1 baris data** (`id = 1`) tanpa menambah baris baru.
- **Graceful Shutdown:** Saat program Python dihentikan dengan `Ctrl+C`, sinyal offline otomatis dikirim untuk mengubah status menjadi `0` (OFFLINE).
- **Deteksi Otomatis Jika Putus Tiba-Tiba:** Jika internet putus mendadak atau PC mati sehingga sinyal offline tidak sempat terkirim, backend secara otomatis mendeteksi status OFFLINE jika jeda heartbeat melebihi 15 detik.

---

## Struktur File Excel

File Excel (`powermeter_data.xlsx`) otomatis dibuat saat pertama kali menjalankan `start` atau `status`. 

Fitur file Excel yang dihasilkan:
- **Sheet Name**: `PowerMeter_Data`
- **Header Khusus**: Warna biru profesional (`#1F4E78`), teks tebal putih, rata tengah.
- **Freeze Panes**: Baris header dikunci (freeze), sehingga saat scroll ke bawah header tetap terlihat.
- **Tipe Data Numerik**: Nilai disimpan sebagai angka murni (bukan teks) sehingga bisa langsung dibuat grafik, rata-rata, rumus `SUM`/`AVERAGE` di Excel.
- **Auto-Fit Lebar Kolom**: Lebar kolom disesuaikan otomatis agar tidak terpotong atau menampilkan tanda `###`.
- **Kolom Status_Sync**: Menampilkan status sinkronisasi (`SYNCED` hijau atau `PENDING` kuning/oranye).

### Keterangan Kolom:

| Kolom | Keterangan |
|-------|------------|
| Timestamp | Waktu pembacaan lengkap (`YYYY-MM-DD HH:MM:SS`) |
| Tanggal | Tanggal saja (`YYYY-MM-DD`) |
| Waktu | Jam saja (`HH:MM:SS`) |
| V_R, V_S, V_T | Tegangan Phase R, S, T (Volt) |
| A_R, A_S, A_T | Arus Phase R, S, T (Ampere) |
| kW_R/S/T/Total | Daya Aktif per phase & total (kW) |
| kVA_R/S/T/Total | Daya Semu per phase & total (kVA) |
| kVAR_R/S/T/Total | Daya Reaktif per phase & total (kVAR) |
| PF_R/S/T/Total | Power Factor (Cos Phi) per phase & total |
| Freq | Frekuensi jaringan (Hz) |
| Status_Sync | Status sinkronisasi ke cloud database (`SYNCED` / `PENDING`) |

File Excel bisa langsung dibuka dengan **Microsoft Excel**, **WPS Office**, atau **Google Sheets**.

---

## Troubleshooting

### ❌ "Tidak dapat membuka port serial"

- **Penyebab**: Port COM salah atau sudah digunakan program lain.
- **Solusi**:
  1. Buka **Device Manager** → **Ports (COM & LPT)** → Catat nomor COM port.
  2. Update `SERIAL_PORT` di `config.py`.
  3. Tutup program lain yang menggunakan port tersebut.

### ❌ "Gagal membaca register" / Timeout

- **Penyebab**: Konfigurasi tidak sesuai dengan setting meter.
- **Solusi**:
  1. Cek **Slave ID** di menu meter, update di `config.py`.
  2. Cek **Baud Rate** di menu meter, update di `config.py`.
  3. Cek **Parity** di menu meter, update di `config.py`.
  4. Pastikan kabel A+ dan B- tidak tertukar.

### ❌ Nilai terbaca aneh / sangat besar / sangat kecil

- **Penyebab**: Register address, data type, atau scale factor salah.
- **Solusi**:
  1. Cek manual meter untuk alamat register yang benar.
  2. Coba ubah `DATA_TYPE` di `config.py` (`"int16"` → `"float"` atau sebaliknya).
  3. Sesuaikan `scale_factor` di `REGISTER_MAP`.
  4. Coba ubah `BYTE_ORDER` atau `WORD_ORDER` jika menggunakan float.

### ❌ "ModuleNotFoundError: No module named 'pymodbus'"

- **Penyebab**: Dependencies belum diinstall atau venv belum aktif.
- **Solusi**:
  1. Aktifkan venv: `venv\Scripts\activate`
  2. Install ulang: `pip install -r requirements.txt`

### ❌ PowerShell execution policy error

- **Solusi**:
  ```powershell
  Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
  ```

---

## Struktur Project

```
jajal jajal/
├── venv/                  # Virtual environment Python
├── config.py              # Konfigurasi koneksi & register map
├── meter_reader.py        # Modul pembacaan Modbus RTU
├── data_logger.py         # Modul penyimpanan data Excel (.xlsx)
├── main.py                # Program utama CLI
├── requirements.txt       # Dependencies (pymodbus, pyserial, openpyxl)
├── powermeter_data.xlsx   # File data Excel (dibuat otomatis saat logging)
└── README.md              # Dokumentasi ini
```

---

## Lisensi

Program ini dibuat untuk keperluan Audit TA. Bebas digunakan dan dimodifikasi sesuai kebutuhan.
