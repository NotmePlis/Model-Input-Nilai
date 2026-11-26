# Tugas Minggu 9 dan 10 Modul Nilai dan Transkrip

Aplikasi latihan Python untuk input nilai, IPS/IPK otomatis, PDF transkrip, dan riwayat perubahan nilai. Data contoh disimpan di SQLite. Semua halaman HTML berada di variabel TEMPLATES pada app.py supaya struktur foldernya sederhana.

## Cara menjalankan di Windows

Ekstrak ZIP, lalu buka folder hasil ekstraksi yang berisi app.py, test_app.py, dan requirements.txt. Instal Python 3.10 atau lebih baru dan centang Add Python to PATH.

Buka folder tersebut melalui VS Code, lalu jalankan perintah berikut di terminal:

    py -m venv .venv
    .venv\Scripts\python -m pip install -r requirements.txt
    .venv\Scripts\python app.py

Buka http://127.0.0.1:5000 pada browser. Biarkan terminal tetap menyala. Tekan Ctrl+C untuk menghentikan server.

Untuk menjalankan lagi:

    .venv\Scripts\python app.py

Linux atau macOS:

    python3 -m venv .venv
    .venv/bin/python -m pip install -r requirements.txt
    .venv/bin/python app.py

Database dan kunci sesi dibuat otomatis di folder instance. Jangan menghapus folder tersebut jika ingin mempertahankan data.

## Akun demonstrasi

| ID login | Nama | Peran |
| --- | --- | --- |
| dosen | Pak Andi | Dosen |
| 23001 | Adi | Mahasiswa |
| 23002 | Citra | Mahasiswa |
| 23003 | Deni | Mahasiswa semester awal |

Password seluruh akun contoh: belajar123.

Data mahasiswa dan identitas universitas adalah contoh. Lambang U bukan logo universitas sungguhan, dan kolom tanda tangan dibiarkan kosong.

## Aturan yang dipakai

1. A=4, B=3, C=2, D=1, E=0.

2. Nilai D termasuk lulus, mengikuti instruksi minimal D. Pada materi ada tulisan D=2.0 yang bertentangan dengan urutan konversi tersebut. Implementasi ini menetapkan batas lulus 1.0 melalui MIN_PASSING_POINTS.

3. IPS menghitung seluruh nilai yang sudah diinput dalam semester terpilih, termasuk E. Mata kuliah yang belum memiliki nilai belum dihitung.

4. IPK mengikuti aturan khusus tugas: hanya MK lulus, lalu ambil nilai tertinggi untuk kode MK yang diulang. SKS tidak dijumlahkan dua kali.

5. Belum memiliki nilai atau belum ada MK lulus menghasilkan IPK 0.0.

6. Perhitungan dibulatkan dua angka desimal pada hasil akhir. Predikat menggunakan IPK yang ditampilkan.

7. Presensi 75% tepat diperbolehkan; kurang dari 75% ditolak pada server.

8. Predikat: minimal 3.5 Cum Laude; minimal 3.0 Sangat Memuaskan; minimal 2.0 Memuaskan; di bawah 2.0 Perlu Perbaikan. Ini kategori berdasarkan IPK, belum keputusan kelulusan.

9. Semua percobaan MK tetap muncul di transkrip. Tanda * menunjukkan percobaan yang dihitung untuk IPK.

## Urutan demonstrasi

1. Login sebagai dosen.

2. Amati IPK Adi sebesar 3.50. Algoritma semester 1 mendapat C, lalu diulang semester 2 mendapat A. Hanya A yang dipakai dalam IPK.

3. Input A pada Basis Data Adi, presensi tepat 75%. Isi alasan, lalu simpan. IPK menjadi 3.67.

4. Coba input pada Struktur Data Adi, presensi 74%. Form dinonaktifkan, dan permintaan yang dikirim langsung ke server juga ditolak.

5. Ubah nilai PBO Adi dari B menjadi A. Isi alasan perubahan. Jika langkah 3 sudah dilakukan, IPK menjadi 4.00.

6. Buka Riwayat. Periksa nilai lama, nilai baru, pengubah, waktu WIB, dan alasan.

7. Buka Transkrip, lalu Unduh PDF.

8. Login sebagai 23001 melalui jendela Incognito untuk melihat transkrip sebagai mahasiswa.

9. Login sebagai 23003 untuk mencoba mahasiswa yang belum memiliki nilai. IPK 0.00, nilai MK ditampilkan sebagai tanda -.

## Cara menjalankan pengujian

    .venv\Scripts\python -m unittest -v

Tersedia 32 metode pengujian: 16 untuk perhitungan dan 16 untuk aplikasi. Beberapa metode memeriksa beberapa kondisi sekaligus.

Hasil pengujian: 32 metode pengujian lulus pada Python 3.12. PDF contoh, PDF mahasiswa belum memiliki nilai, serta PDF dengan 45 baris mata kuliah berhasil dibuat dan diperiksa. Tampilan browser belum diuji langsung.

## Cara kerja audit

Aplikasi mendaftarkan fungsi SQLite current_actor() dan audit_reason() pada setiap koneksi. Nilainya diisi dari dosen yang sudah login dan alasan pada form.

Trigger AFTER INSERT menyimpan input awal. Trigger AFTER UPDATE menyimpan setiap pembaruan grades, termasuk pembaruan SQL dengan nilai huruf yang tetap sama. Bila pengguna menyimpan nilai yang tidak berubah melalui form, aplikasi tidak mengirim UPDATE sehingga tidak menambah riwayat.

grade_history memiliki kolom id, grade_id, old_value, new_value, changed_by, changed_at, dan reason. Waktu disimpan dalam UTC dan ditampilkan sebagai WIB. Perubahan nilai dan penambahan audit berada dalam transaksi yang sama. Trigger menolak perubahan tanpa actor atau alasan. Riwayat tidak memiliki menu edit, dan trigger menolak UPDATE/DELETE pada grade_history.

View student_grade_history menghubungkan riwayat dengan NIM, mata kuliah, semester, dan nama pengubah.

## HTML dan PDF

Template HTML dinamis terdapat pada TEMPLATES["transcript.html"]. Tampilannya memakai CSS cetak dan tabel per semester.

PDF dibuat oleh fungsi build_pdf menggunakan ReportLab. Template HTML dan generator PDF mengambil objek data yang sama dari get_transcript, tetapi ReportLab menyusun tata letak PDF sendiri, bukan mengubah HTML menjadi PDF.

Header PDF diulang pada setiap halaman. Tabel memiliki header berulang, nama MK dapat membungkus ke beberapa baris, dan halaman diberi nomor. Bagian akhir memuat SKS lulus, IPK, predikat, serta ruang tanda tangan dekan.

## Batasan

- Modul ini berdiri sendiri; belum digabungkan dengan source modul presensi QR sebelumnya.

- attendance_percent adalah data contoh pada enrollments. Untuk integrasi nyata, ganti sumber persentase ini dengan rekap presensi per mahasiswa dan MK.

- Data mahasiswa, MK, dan enrollment dibuat otomatis untuk demo. Belum ada menu pengelolaan data tersebut.

- Jika presensi kemudian turun, nilai yang sudah tersimpan tidak otomatis dihapus. Koreksi nilai berikutnya tetap harus memenuhi batas presensi saat disimpan.

- Pengelompokan pengulangan menggunakan kode MK. Perubahan kode atau ekuivalensi kurikulum belum ditangani.

- Server Flask dijalankan secara lokal untuk tugas. Akun contoh perlu diganti sebelum penggunaan nyata.


## Upload ke GitHub

Ekstrak ZIP, lalu upload seluruh isi folder proyek ke repository GitHub. Letakkan app.py, requirements.txt, test_app.py, dan README.md pada direktori utama repository. File ZIP tidak perlu diupload sebagai source.

Database, kunci sesi, cache Python, dan virtual environment tidak disertakan. Berkas .gitignore mencegah berkas lokal tersebut ikut masuk git. Laporan Word ada di docs/Laporan_Modul_Nilai_Transkrip.docx.
