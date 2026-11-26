# Modul Nilai dan Transkrip

Tugas Minggu 9 dan 10
Nabil Maulana Hafiz
Teknik Informatika Semester 3

## Tujuan program

Pada tugas ini, saya membuat aplikasi untuk mencatat nilai mahasiswa dan menampilkan hasil belajarnya. Dosen dapat menginput nilai A sampai E, lalu program menghitung IPS dan IPK. Mahasiswa dapat melihat nilai sendiri dan mengunduh transkrip PDF.

Saya memilih Flask dan SQLite agar aplikasi bisa dijalankan di laptop tanpa memasang database server terpisah. PDF dibuat menggunakan ReportLab. Template HTML ditempatkan dalam app.py supaya berkas program tidak terlalu banyak.

## Perhitungan IPS dan IPK

Konversi nilai yang dipakai adalah A=4, B=3, C=2, D=1, dan E=0. Mutu setiap mata kuliah dihitung dari SKS dikali nilai angka.

IPS dihitung dari semua nilai yang sudah masuk pada satu semester, termasuk E. Nilai yang belum diinput tidak dimasukkan. IPK mengikuti aturan tugas, yaitu hanya menghitung mata kuliah yang lulus. Jika mahasiswa mengulang MK, program memilih nilai tertinggi berdasarkan kode MK dan menghitung SKS sekali.

Contohnya, Adi memperoleh C pada Algoritma semester 1, lalu mengulang dan mendapat A pada semester 2. Keduanya tetap tampil di transkrip, tetapi yang masuk IPK hanya A. Bila Algoritma berbobot 3 SKS dan PBO berbobot 3 SKS mendapat B, IPK-nya adalah (3 x 4 + 3 x 3) / 6 = 3,50.

Materi menyebut minimal D untuk lulus, tetapi juga mencantumkan D=2,0. Saya menggunakan D=1 sesuai urutan konversi A sampai E, dan tetap memasukkan D sebagai lulus. Batas ini diletakkan pada MIN_PASSING_POINTS agar mudah disesuaikan jika dosen meminta aturan lain.

## Input nilai dan pembatasan presensi

Sebelum menyimpan nilai, program memeriksa apakah pengguna merupakan dosen pengampu dan apakah mahasiswa terdaftar pada mata kuliah yang dipilih. Program juga memeriksa persentase presensi. Nilai boleh disimpan jika presensi minimal 75%.

Pemeriksaan dilakukan di server. Jadi, meskipun tombol yang dinonaktifkan pada halaman dipaksa aktif, permintaan dengan presensi kurang dari 75% tetap ditolak. Dalam versi ini persentase presensi masih berupa data contoh, belum terhubung dengan modul QR.

IPS dan IPK tidak disimpan sebagai angka tetap di database. Program menghitungnya kembali dari data nilai saat halaman dibuka setelah penyimpanan. Cara ini menghindari hasil IPK lama yang tertinggal setelah dosen mengedit nilai.

## Riwayat perubahan nilai

Tabel grade_history menyimpan identitas catatan, nilai lama, nilai baru, dosen pengubah, waktu, dan alasan. Trigger SQLite otomatis menambah riwayat saat data grades dimasukkan atau diperbarui. Input pertama memiliki nilai lama kosong.

Identitas pengubah berasal dari akun login, bukan kolom yang boleh diisi bebas oleh pengguna. Alasan berasal dari formulir dan wajib diisi. Perubahan nilai serta catatan riwayat disimpan dalam transaksi yang sama. Jika transaksi dibatalkan, keduanya ikut dibatalkan.

View student_grade_history menghubungkan riwayat dengan mahasiswa, mata kuliah, dan semester. Dosen atau mahasiswa yang memiliki akses dapat melihatnya melalui halaman Riwayat. Penghapusan dan perubahan isi grade_history ditolak oleh trigger.

## Transkrip

Fungsi get_transcript mengambil biodata, semua percobaan mata kuliah, IPS setiap semester, IPK, dan total SKS lulus. Data ini digunakan pada halaman HTML dan PDF.

Transkrip memiliki header kampus contoh, NIM, nama, program studi, angkatan, dan tabel per semester. Tabel berisi kode MK, nama MK, SKS, nilai, dan mutu. Tanda bintang menunjukkan percobaan MK yang dipakai dalam IPK.

Bagian akhir menampilkan SKS lulus tanpa duplikasi, IPK, predikat berdasarkan IPK, dan ruang tanda tangan dekan. Nama kampus serta lambang yang digunakan adalah contoh. Tanda tangan tidak dibuat otomatis.

Kategori predikat mengikuti IPK: minimal 3,50 Cum Laude, minimal 3,00 Sangat Memuaskan, minimal 2,00 Memuaskan, dan di bawah 2,00 Perlu Perbaikan. Kategori ini belum menyatakan mahasiswa telah lulus karena syarat lain belum diperiksa.

## Hasil pengujian

Pengujian dilakukan menggunakan unittest. Seluruh 32 metode pengujian berhasil dijalankan pada Python 3.12. Enam belas metode berfokus pada perhitungan, termasuk semua A, bobot SKS berbeda, nilai ulang naik atau turun, nilai E, nilai D, belum ada nilai, pengulangan dengan nilai sama, dan pembulatan.

Enam belas metode lainnya memeriksa aplikasi, seperti input presensi tepat 75%, penolakan di bawah 75%, perubahan nilai, trigger audit, pembatalan transaksi, hak akses, PDF, dan tampilan data mahasiswa semester awal.

Hasil pengujian menunjukkan aturan perhitungan dan validasi berjalan sesuai kasus yang diuji. PDF transkrip juga diperiksa untuk data contoh, mahasiswa yang belum memiliki nilai, dan tabel berisi 45 mata kuliah. Pengujian tampilan HTML pada browser masih perlu dilakukan secara langsung.

## Kesimpulan

Alur utama program adalah dosen menginput nilai, sistem memeriksa syarat presensi, nilai disimpan beserta riwayatnya, lalu IPS dan IPK dihitung kembali. Mahasiswa dapat melihat hasil melalui transkrip. Pengembangan berikutnya adalah menghubungkan persentase kehadiran dengan modul presensi dan menambahkan pengelolaan data mahasiswa serta mata kuliah.

