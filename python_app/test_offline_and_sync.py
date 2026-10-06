"""
test_offline_and_sync.py — Test script untuk memvalidasi fitur:
1. Base URL terpusat
2. Penyimpanan Excel dengan status PENDING saat offline
3. Deteksi baris pending
4. Pembaruan status menjadi SYNCED
"""

import os
import unittest
import openpyxl

import config
import data_logger
import api_client


class TestOfflineBufferAndSync(unittest.TestCase):

    def setUp(self):
        # Gunakan file test khusus agar tidak mengganggu file produksi
        self.original_filename = config.EXCEL_FILENAME
        config.EXCEL_FILENAME = "test_powermeter_data.xlsx"
        data_logger.reset_excel()

    def tearDown(self):
        test_path = data_logger.get_excel_path()
        if os.path.exists(test_path):
            try:
                os.remove(test_path)
            except Exception:
                pass
        config.EXCEL_FILENAME = self.original_filename

    def test_base_url_centralization(self):
        """Memastikan Base URL terpusat dan seluruh endpoint diturunkan dengan benar."""
        base_url = api_client.get_base_url()
        self.assertEqual(base_url, config.WEBAPP_BASE_URL.rstrip("/"))
        self.assertTrue(api_client.get_api_url().startswith(base_url))
        self.assertTrue(api_client.get_sync_url().startswith(base_url))
        self.assertTrue(api_client.get_heartbeat_url().startswith(base_url))
        self.assertTrue(api_client.get_status_url().startswith(base_url))
        self.assertTrue(api_client.get_offline_url().startswith(base_url))

    def test_excel_has_sync_column(self):
        """Memastikan kolom Status_Sync ada pada header Excel."""
        headers = data_logger.get_headers()
        self.assertIn("Status_Sync", headers)

    def test_offline_buffering_as_pending(self):
        """Memastikan data tersimpan di Excel dengan status PENDING saat offline."""
        mock_data = {
            "V_R": 220.5,
            "V_S": 221.0,
            "V_T": 219.5,
            "A_R": 5.2,
            "kW_Total": 3.4,
        }

        # Simpan dengan status PENDING
        row_idx = data_logger.save_to_excel(mock_data, sync_status="PENDING")
        self.assertGreater(row_idx, 1)

        # Cek jumlah data pending
        pending_rows = data_logger.get_pending_rows()
        self.assertEqual(len(pending_rows), 1)
        self.assertEqual(pending_rows[0]["row_index"], row_idx)
        self.assertAlmostEqual(pending_rows[0]["data"]["V_R"], 220.5)

        # Update status baris menjadi SYNCED
        data_logger.update_row_sync_status(row_idx, "SYNCED")
        pending_after = data_logger.get_pending_rows()
        self.assertEqual(len(pending_after), 0)

    def test_mark_multiple_rows_synced(self):
        """Memastikan fungsi mark_rows_synced memperbarui beberapa baris sekaligus."""
        for i in range(3):
            data_logger.save_to_excel({"V_R": 220.0 + i}, sync_status="PENDING")

        pending_before = data_logger.get_pending_rows()
        self.assertEqual(len(pending_before), 3)

        indices = [item["row_index"] for item in pending_before]
        updated = data_logger.mark_rows_synced(indices)
        self.assertEqual(updated, 3)

        pending_after = data_logger.get_pending_rows()
        self.assertEqual(len(pending_after), 0)

        info = data_logger.get_file_info()
        self.assertEqual(info["synced_count"], 3)
        self.assertEqual(info["pending_count"], 0)


if __name__ == "__main__":
    unittest.main()
