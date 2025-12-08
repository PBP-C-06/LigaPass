# ⚽ LigaPass

> Platform pemesanan tiket pertandingan sepak bola dan berita terbaru sepak bola berbasis web.

---

## 👷 Anggota Kelompok
- [Jaysen Lestari](https://github.com/Jaysenlestari) - 2406395335  
- [Nadia Aisyah Fazila](https://github.com/applepiesss) - 2406495584  
- [Muhammad Aldo Fahrezy](https://github.com/aldofahrezy) - 2406423055  
- [Refki Septian](https://github.com/RefkiSeptian) - 2406397196  
- [Mei Ching](https://github.com/https://github.com/Mei2462) - 2406361662  

---

## 📝 Deskripsi Singkat
LigaPass adalah platform berbasis web yang memudahkan penggemar sepak bola untuk memesan tiket pertandingan secara praktis sekaligus mengikuti berita terkini seputar dunia bola. Dengan antarmuka yang sederhana dan informatif, pengguna bisa menemukan jadwal pertandingan, memilih kategori tempat duduk sesuai kebutuhan, serta melakukan pembayaran dengan aman dan cepat.

Selain fitur pemesanan, LigaPass juga menghadirkan berita bola terbaru, analisis pertandingan, dan update transfer pemain yang dikurasi agar tetap relevan dengan minat pengguna. Kombinasi layanan pemesanan tiket dan portal berita ini membuat LigaPass menjadi solusi all-in-one bagi para pecinta sepak bola yang ingin mendapatkan pengalaman menonton lebih seru dan informatif.

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
   Modul ini menyediakan halaman utama daftar berita yang dapat difilter dan search berdasarkan keyword. Akses berbasis peran: User melihat semua berita, sedangkan Journalist mendapat tombol Create News untuk membuat berita baru. Pada detail berita, Journalist juga melihat Edit News untuk memperbarui atau menghapus; setelah disunting, label tanggal berubah menjadi “tanggal disunting”. Selain itu, User dan Journalist dapat berinteraksi dengan menuliskan comment pada halaman news detail.
4. **Matches**  
*Dikerjakan oleh Muhammad Aldo Fahrezy*  
   Aplikasi ini mencakup pipeline inisialisasi data (data seeding) dari dataset Kaggle dengan preprocessing/cleaning untuk menstandarkan nama tim, format tanggal–waktu, dan menangani missing/inconsistency sebelum masuk ke model Team dan Match. Admin punya CRUD penuh untuk data master: mengelola klub (tambah, lihat, ubah nama/logo, hapus) dan jadwal pertandingan (buat, lihat, ubah waktu–stadion–harga tiket, hapus). Di sisi pengguna, tersedia halaman kalender yang otomatis mengelompokkan pertandingan menjadi Upcoming, Ongoing, dan Past berdasarkan waktu saat ini, serta halaman detail pertandingan yang menampilkan info kedua tim, kickoff, stadion, harga tiket, dan ketersediaannya
4. **Product Management**  
*Dikerjakan oleh Jaysen Lestari*  
   Aplikasi ini memungkinkan user memilih pertandingan dari halaman utama, lalu memilih kategori tiket (VVIP/VIP/Reguler), memvalidasi ketersediaan kursi, menentukan jumlah (opsional bundle/promo), dan membuat pesanan. Untuk pembayaran akan dipilih salah satu dari opsi berikut: Opsi A (Dummy QR)—user menekan “Sudah membayar” sehingga status menjadi “menunggu verifikasi”, lalu admin memverifikasi; Opsi B (Payment Gateway)—proses pembayaran terintegrasi hingga terverifikasi otomatis. Setelah pembayaran terverifikasi, sistem mengeluarkan voucher/tiket.
5. **Review & Comment**  
*Dikerjakan oleh Refki Septian*  
   Pada bagian modul ini, admin memiliki sistem menyediakan fitur analitik yang menampilkan ringkasan tiket terjual, pendapatan, tren penjualan, serta visualisasi seat occupancy yang bisa difilter berdasarkan kategori tiket; selain itu, admin juga dapat memantau agregasi review penonton berupa rating rata-rata, komentar. Untuk User, tersedia ringkasan riwayat pembelian tiket, statistik kehadiran, grafik pengeluaran bulanan maupun tahunan, serta informasi loyalty points jika sistem poin diaktifkan; pengguna juga dapat memberikan rating pertandingan dan menuliskan komentar pengalaman menonton. Admin memiliki dashboard pesanan yang menampilkan metrik seperti total pesanan, tiket terjual, penerimaan, sisa tiket, serta dapat mengatur sisa tiket; tiap pesanan memiliki halaman detail. Untuk Opsi A, admin juga mendapat halaman verifikasi pembayaran manual.
   
---

## 📊 Dataset
- **Match** (Inggris): https://www.kaggle.com/datasets/mertbayraktar/english-premier-league-2526-season/data
- **Match** (Indonesia) : https://www.transfermarkt.co.in/liga-1-indonesia/restprogramm/wettbewerb/IN1L (scrapping)

---

## 👤Role
- **User** : User dapat melakukan registrasi, login, serta mengelola profil pribadi mereka. Mereka bisa membeli tiket pertandingan dengan memilih kategori kursi (VVIP, VIP, Reguler), melakukan pembayaran, dan mendapatkan tiket digital. User juga memiliki riwayat pembelian, statistik kehadiran, grafik pengeluaran, serta dapat memberikan review dan komentar pada pertandingan maupun berita.
- **Admin** : Admin memiliki kendali penuh terhadap sistem, mulai dari manajemen data klub dan pertandingan (CRUD), verifikasi pembayaran, hingga monitoring penjualan tiket melalui dashboard analitik. Admin juga dapat meninjau profil pengguna, mengelola status akun, serta memantau ulasan penonton lengkap dengan rating, komentar, dan visualisasi tren. Dengan akses ini, Admin berperan penting dalam menjaga kelancaran operasional aplikasi.
- **Journalist** : journalist berfokus pada pengelolaan konten berita. Mereka memiliki akses untuk membuat, mengedit, dan menghapus berita, serta melihat ringkasan kinerja konten berupa total tayang dan jumlah artikel yang dipublikasikan. Pada halaman berita, Journalist mendapat tombol khusus untuk membuat berita baru dan mengelola konten yang sudah ada. Dengan demikian, Journalist menjadi sumber utama informasi terbaru bagi pengguna aplikasi.

--- 

## 🔗 URL
**Deployment** : https://jaysen-lestari-ligapass.pbp.cs.ui.ac.id/   
**Figma** : https://www.figma.com/proto/czV0IIjdOHyPQ4iIKozhPX/TK-UTS?page-id=0%3A1&node-id=1-1935&p=f&viewport=-1269%2C-173%2C0.41&t=KgYTQaoFAjTJ0iZZ-1&scaling=min-zoom&content-scaling=fixed
**User flow** : https://www.figma.com/proto/czV0IIjdOHyPQ4iIKozhPX/LigaPass?node-id=0-1&p=f&viewport=-567%2C78%2C0.21&t=18d5UYBpfanXeuIm-0&scaling=contain&content-scaling=fixed&starting-point-node-id=1%3A1935
**Admin flow**: https://www.figma.com/proto/czV0IIjdOHyPQ4iIKozhPX/LigaPass?node-id=12-131&p=f&viewport=321%2C241%2C0.09&t=18d5UYBpfanXeuIm-0&scaling=min-zoom&content-scaling=fixed&starting-point-node-id=353%3A1124
**Journalist flow**: https://www.figma.com/proto/czV0IIjdOHyPQ4iIKozhPX/LigaPass?node-id=182-2062&p=f&viewport=243%2C401%2C0.08&t=18d5UYBpfanXeuIm-0&scaling=min-zoom&content-scaling=fixed&starting-point-node-id=353%3A1373