# Draf Project UTS - LigaPass

> Platform pemesanan tiket pertandingan sepak bola dan berita terbaru sepak bola berbasis web.

---

## 👥 Anggota Kelompok
- [Jaysen Lestari](https://github.com/Jaysenlestari) — 2406395335  
- [Nadia Aisyah Fazila](https://github.com/applepiesss) — 2406495584  
- [Muhammad Aldo Fahrezy](https://github.com/aldofahrezy) — 2406423055  
- [Refki Septian](https://github.com/RefkiSeptian) — 2406397196  
- [Mei Ching](https://github.com/https://github.com/Mei2462) — 2406361662  

---

## 📝 Deskripsi Singkat
LigaPass adalah **platform berbasis web** yang berfungsi sebagai aplikasi pemesanan tiket pertandingan sepak bola sekaligus membaca berita bola terbaru. 

Fokus utama: kemudahan pemesanan, informasi pertandingan yang jelas, dan konten berita yang relevan.

> Platform pemesanan tiket pertandingan sepak bola berbasis web

---

## 🧩 Modul yang Diimplementasikan (Draft)
1. **Login & Authentication**      
*Dikerjakan oleh Jaysen Lestari*   
Registrasi, login, logout, dan manage cookie untuk mendapatkan role yang sesuai.
2. **Profile Management**  
*Dikerjakan oleh Nadia Aisyah Fazila*  
   Modul Profile menyediakan halaman profil untuk tiga peran: **User**, **Admin**, dan **Jurnalis**. Pengguna dapat melihat serta mengedit data dasar seperti foto, nama lengkap, username, email, nomor telepon, dan tanggal lahir. Admin dapat meninjau profil pengguna beserta riwayat pembelian tiket dan riwayat ulasan, serta mengelola status akun seperti aktif, suspended, atau banned(opsional). **Admin** dan **Jurnalis** bersifat **hardcoded**. Journalist memiliki ringkasan kinerja konten, seperti total tayang dan jumlah berita yang telah dipublikasikan.
3. **News**  
*Dikerjakan oleh Mei Ching*  
   Modul ini menyediakan halaman utama daftar berita yang dapat difilter dan search berdasarkan keyword. Akses berbasis peran: User dan Admin melihat semua berita, sedangkan Journalist mendapat tombol Create News untuk membuat berita baru. Pada detail berita, Journalist juga melihat Edit News untuk memperbarui atau menghapus; setelah disunting, label tanggal berubah menjadi “tanggal disunting”. 
4. **Matches**  
*Dikerjakan oleh Muhammad Aldo Fahrezy*  
   Aplikasi ini mencakup pipeline inisialisasi data (data seeding) dari dataset Kaggle dengan preprocessing/cleaning untuk menstandarkan nama tim, format tanggal–waktu, dan menangani missing/inconsistency sebelum masuk ke model Team dan Match. Admin punya CRUD penuh untuk data master: mengelola klub (tambah, lihat, ubah nama/logo, hapus) dan jadwal pertandingan (buat, lihat, ubah waktu–stadion–harga tiket, hapus). Di sisi pengguna, tersedia halaman kalender yang otomatis mengelompokkan pertandingan menjadi Upcoming, Ongoing, dan Past berdasarkan waktu saat ini, serta halaman detail pertandingan yang menampilkan info kedua tim, kickoff, stadion, harga tiket, dan ketersediaannya
4. **Product Management**  
*Dikerjakan oleh Jaysen Lestari*  
   Aplikasi ini memungkinkan user memilih pertandingan dari halaman utama, lalu memilih kategori tiket (VVIP/VIP/Reguler), memvalidasi ketersediaan kursi, menentukan jumlah (opsional bundle/promo), dan membuat pesanan. Untuk pembayaran akan dipilih salah satu dari opsi berikut: Opsi A (Dummy QR)—user menekan “Sudah membayar” sehingga status menjadi “menunggu verifikasi”, lalu admin memverifikasi; Opsi B (Payment Gateway)—proses pembayaran terintegrasi hingga terverifikasi otomatis. Setelah pembayaran terverifikasi, sistem mengeluarkan voucher/tiket. Admin memiliki dashboard pesanan yang menampilkan metrik seperti total pesanan, tiket terjual, penerimaan, sisa tiket, serta dapat mengatur sisa tiket; tiap pesanan memiliki halaman detail. Untuk Opsi A, admin juga mendapat halaman verifikasi pembayaran manual.
5. **Review & Analytics**  
*Dikerjakan oleh Refki Septian*  
   Setelah pertandingan yang ditonton selesai, pengguna dapat meninggalkan komentar terkait pertandingan dan memberi rating. Di bagian berita juga pengguna dapat meninggalkan comment. Kemudian akan ditampilkan statistik terkait pertandingan apa yang paling banyak dibeli tiketnya.

---

## 📊 Dataset
- **Match**: https://www.kaggle.com/datasets/mertbayraktar/english-premier-league-2526-season/data
