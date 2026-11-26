"""Tes perhitungan IPK dan aturan aplikasi. Jalankan: python -m unittest -v"""
import copy
import os
import sqlite3
import tempfile
import unittest

from flask import g
import app as module


def record(code, sks, letter):
    return {"course_code": code, "sks": sks, "letter": letter}


class GPATests(unittest.TestCase):
    def test_belum_ada_nilai(self):
        self.assertEqual(module.weighted_gpa([]), 0.0)

    def test_semua_A(self):
        rows = [record("A", 3, "A"), record("B", 2, "A"), record("C", 4, "A")]
        self.assertEqual(module.weighted_gpa(rows), 4.0)

    def test_bobot_sks_berbeda(self):
        self.assertEqual(module.weighted_gpa([record("A", 3, "A"), record("B", 2, "C")]), 3.2)

    def test_mk_diulang_nilai_naik(self):
        self.assertEqual(module.weighted_gpa([record("A", 3, "C"), record("A", 3, "A")]), 4.0)

    def test_mk_diulang_nilai_turun(self):
        self.assertEqual(module.weighted_gpa([record("A", 3, "A"), record("A", 3, "C")]), 4.0)

    def test_nilai_E_tidak_masuk_ipk(self):
        self.assertEqual(module.weighted_gpa([record("A", 3, "E"), record("B", 2, "B")]), 3.0)

    def test_nilai_D_lulus_sesuai_aturan_tugas(self):
        self.assertEqual(module.weighted_gpa([record("A", 3, "D")]), 1.0)

    def test_semua_E(self):
        self.assertEqual(module.weighted_gpa([record("A", 3, "E")]), 0.0)

    def test_nilai_belum_diinput(self):
        self.assertEqual(module.weighted_gpa([record("A", 3, None)]), 0.0)

    def test_campuran_belum_ada_nilai(self):
        self.assertEqual(module.weighted_gpa([record("A", 3, None), record("B", 2, "A")]), 4.0)

    def test_mk_ulang_tidak_menggandakan_sks(self):
        rows = [record("A", 3, "C"), record("A", 3, "A"), record("B", 3, "B")]
        self.assertEqual(module.weighted_gpa(rows), 3.5)
        self.assertEqual(sum(r["sks"] for r in module.best_passed(rows)), 6)

    def test_pengulangan_dengan_nilai_sama(self):
        self.assertEqual(module.weighted_gpa([record("A", 3, "B"), record("A", 3, "B")]), 3.0)

    def test_pembulatan_dua_desimal(self):
        self.assertEqual(module.weighted_gpa([record("A", 1, "A"), record("B", 2, "B")]), 3.33)

    def test_ips_memasukkan_E(self):
        rows = [record("A", 2, "A"), record("B", 2, "E")]
        self.assertEqual(module.weighted_gpa(rows, include_failed=True, best_only=False), 2.0)

    def test_huruf_tidak_valid(self):
        with self.assertRaises(ValueError):
            module.weighted_gpa([record("A", 3, "X")])

    def test_sks_nol(self):
        with self.assertRaises(ValueError):
            module.weighted_gpa([record("A", 0, "A")])


class ApplicationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        module.app.config.update(TESTING=True, DATABASE=os.path.join(self.tmp.name, "test.db"))
        with module.app.app_context():
            module.init_db()
        self.client = module.app.test_client()
        self.login("dosen")

    def tearDown(self):
        self.tmp.cleanup()

    def login(self, uid):
        with self.client.session_transaction() as s:
            s.update(uid=uid, csrf="test-csrf")

    def save(self, eid, letter, reason="Koreksi setelah pemeriksaan"):
        return self.client.post("/grades/" + str(eid),
            data={"csrf": "test-csrf", "letter": letter, "reason": reason})

    def test_fungsi_ips_ipk_dan_transkrip(self):
        with module.app.app_context():
            self.assertEqual(module.calculate_ips("23001", 1), 2.0)
            self.assertEqual(module.calculate_ips("23001", 2), 4.0)
            self.assertEqual(module.calculate_ipk("23001"), 3.5)
            t = module.get_transcript("23001")
            self.assertEqual(t["total_sks"], 6)
            self.assertEqual(t["predicate"], "Cum Laude")

    def test_mahasiswa_semester_awal_dan_semester_kosong(self):
        with module.app.app_context():
            self.assertEqual(module.calculate_ipk("23003"), 0.0)
            self.assertEqual(module.calculate_ips("23003", 1), 0.0)
            self.assertEqual(module.calculate_ips("23003", 8), 0.0)
            self.assertEqual(module.get_transcript("23003")["total_sks"], 0)

    def test_input_nilai_pada_presensi_tepat_75(self):
        self.assertEqual(self.save(4, "A").status_code, 302)
        with module.app.app_context():
            self.assertEqual(module.calculate_ipk("23001"), 3.67)

    def test_tolak_presensi_kurang_75(self):
        self.assertEqual(self.save(5, "A").status_code, 400)
        with module.app.app_context():
            self.assertIsNone(module.db().execute("SELECT * FROM grades WHERE enrollment_id=5").fetchone())

    def test_edit_nilai_dan_audit(self):
        self.assertEqual(self.save(3, "A", "Perbaikan hasil ujian").status_code, 302)
        with module.app.app_context():
            row = module.db().execute("""
                SELECT * FROM student_grade_history WHERE nim='23001'
                AND course_code='IF201' ORDER BY id DESC LIMIT 1
            """).fetchone()
            self.assertEqual((row["old_value"], row["new_value"]), ("B", "A"))
            self.assertEqual(row["changed_by"], "dosen")
            self.assertEqual(row["reason"], "Perbaikan hasil ujian")
            self.assertTrue(row["changed_at"].endswith("Z"))
            self.assertEqual(module.calculate_ipk("23001"), 4.0)

    def test_setiap_update_sql_masuk_audit(self):
        with module.app.app_context():
            g.actor, g.reason = "dosen", "Pengujian trigger"
            before = module.db().execute("SELECT COUNT(*) FROM grade_history").fetchone()[0]
            with module.db():
                module.db().execute("UPDATE grades SET letter=letter WHERE enrollment_id=3")
            after = module.db().execute("SELECT COUNT(*) FROM grade_history").fetchone()[0]
            self.assertEqual(after, before + 1)

    def test_nilai_dan_audit_rollback_bersamaan(self):
        with module.app.app_context():
            g.actor, g.reason = "dosen", "Transaksi percobaan"
            before = module.db().execute("SELECT COUNT(*) FROM grade_history").fetchone()[0]
            with self.assertRaises(RuntimeError):
                with module.db():
                    module.db().execute("UPDATE grades SET letter='A' WHERE enrollment_id=3")
                    raise RuntimeError("Batalkan transaksi")
            row = module.db().execute("SELECT letter FROM grades WHERE enrollment_id=3").fetchone()
            after = module.db().execute("SELECT COUNT(*) FROM grade_history").fetchone()[0]
            self.assertEqual(row["letter"], "B")
            self.assertEqual(before, after)

    def test_update_tanpa_actor_ditolak(self):
        with module.app.app_context():
            with self.assertRaises(sqlite3.IntegrityError):
                with module.db():
                    module.db().execute("UPDATE grades SET letter='A' WHERE enrollment_id=3")

    def test_riwayat_tidak_bisa_dihapus(self):
        with module.app.app_context():
            with self.assertRaises(sqlite3.IntegrityError):
                with module.db():
                    module.db().execute("DELETE FROM grade_history")

    def test_alasan_dan_huruf_wajib_valid(self):
        self.assertEqual(self.save(3, "X").status_code, 400)
        self.assertEqual(self.save(3, "A", " ").status_code, 400)

    def test_mahasiswa_tidak_bisa_input_atau_lihat_transkrip_orang_lain(self):
        self.login("23001")
        self.assertEqual(self.save(3, "A").status_code, 403)
        self.assertEqual(self.client.get("/transcript/23002").status_code, 403)
        self.assertEqual(self.client.get("/transcript/23002/pdf").status_code, 403)
        self.assertEqual(self.client.get("/history/23002").status_code, 403)
        self.assertEqual(self.client.get("/transcript/23001").status_code, 200)

    def test_form_tanpa_csrf_ditolak(self):
        response = self.client.post("/grades/3", data={"letter": "A", "reason": "Koreksi"})
        self.assertEqual(response.status_code, 403)

    def test_pdf_bisa_diunduh(self):
        response = self.client.get("/transcript/23001/pdf")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data.startswith(b"%PDF-"))
        self.assertIn("attachment", response.headers["Content-Disposition"])

    def test_pdf_mahasiswa_belum_ada_nilai(self):
        self.assertEqual(self.client.get("/transcript/23003/pdf").status_code, 200)

    def test_batas_predikat(self):
        for ipk, expected in [(3.5, "Cum Laude"), (3.49, "Sangat Memuaskan"),
                              (3.0, "Sangat Memuaskan"), (2.99, "Memuaskan"),
                              (2.0, "Memuaskan"), (1.99, "Perlu Perbaikan")]:
            with self.subTest(ipk=ipk):
                self.assertEqual(module.predicate(ipk), expected)

    def test_halaman_utama_dan_riwayat(self):
        self.assertEqual(self.client.get("/").status_code, 200)
        self.assertEqual(self.client.get("/history/23001").status_code, 200)


if __name__ == "__main__":
    unittest.main(verbosity=2)

