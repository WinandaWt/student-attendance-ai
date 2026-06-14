from config.database import get_connection


# Isi daftar mahasiswa NON-dummy: NIM berurutan 220001 - 220050
STUDENTS = [
    ("220001", "Ahmad Fauzi", "Sistem Informasi", None),
    ("220002", "Bunga Maharani", "Sistem Informasi", None),
    ("220003", "Cahyo Ramadhan", "Sistem Informasi", None),
    ("220004", "Dinda Oktaviani", "Sistem Informasi", None),
    ("220005", "Eko Prasetyo", "Sistem Informasi", None),
    ("220006", "Fitri Amelia", "Sistem Informasi", None),
    ("220007", "Galih Saputra", "Sistem Informasi", None),
    ("220008", "Hana Lestari", "Sistem Informasi", None),
    ("220009", "Irfan Maulana", "Sistem Informasi", None),
    ("220010", "Jihan Permata", "Sistem Informasi", None),

    ("220011", "Kevin Sanjaya", "Teknik Informatika", None),
    ("220012", "Laila Nuraini", "Teknik Informatika", None),
    ("220013", "Muhammad Rizky", "Teknik Informatika", None),
    ("220014", "Nadia Safitri", "Teknik Informatika", None),
    ("220015", "Oki Pranata", "Teknik Informatika", None),
    ("220016", "Putri Ayuningtyas", "Teknik Informatika", None),
    ("220017", "Qori Aulia", "Teknik Informatika", None),
    ("220018", "Rafi Kurniawan", "Teknik Informatika", None),
    ("220019", "Salsaabila Putri", "Teknik Informatika", None),
    ("220020", "Teguh Hidayat", "Teknik Informatika", None),

    ("220021", "Vania Putri", "Manajemen", None),
    ("220022", "Wahyu Pratama", "Manajemen", None),
    ("220023", "Yasmin Azzahra", "Manajemen", None),
    ("220024", "Zahra Syafira", "Manajemen", None),
    ("220025", "Alya Ramadani", "Manajemen", None),
    ("220026", "Bagas Aditya", "Manajemen", None),
    ("220027", "Citra Kirana", "Manajemen", None),
    ("220028", "Dimas Wicaksono", "Manajemen", None),
    ("220029", "Elisa Putri", "Manajemen", None),
    ("220030", "Faisal Hakim", "Manajemen", None),

    ("220031", "Gilang Ramadhan", "Akuntansi", None),
    ("220032", "Hafiz Maulana", "Akuntansi", None),
    ("220033", "Intan Permata", "Akuntansi", None),
    ("220034", "Julianty Lestari", "Akuntansi", None),
    ("220035", "Kurniawan Aditya", "Akuntansi", None),
    ("220036", "Lukman Hakim", "Akuntansi", None),
    ("220037", "Maya Zahra", "Akuntansi", None),
    ("220038", "Naufal Ramadhan", "Akuntansi", None),
    ("220039", "Olimpia Salsabila", "Akuntansi", None),
    ("220040", "Putra Nugroho", "Akuntansi", None),

    ("220041", "Rania Azzura", "Teknik Komputer", None),
    ("220042", "Satria Ramadhani", "Teknik Komputer", None),
    ("220043", "Tania Wulandari", "Teknik Komputer", None),
    ("220044", "Umar Faruq", "Teknik Komputer", None),
    ("220045", "Vera Oktaviani", "Teknik Komputer", None),
    ("220046", "Wawan Setiawan", "Teknik Komputer", None),
    ("220047", "Xenia Putri", "Teknik Komputer", None),
    ("220048", "Yusuf Prabowo", "Teknik Komputer", None),
    ("220049", "Zidan Mahendra", "Teknik Komputer", None),
    ("220050", "Aulia Zahara", "Teknik Komputer", None),
]


def main():
    conn = None
    cursor = None
    inserted_count = 0

    try:
        conn = get_connection()
        cursor = conn.cursor()

        for nim, nama, jurusan, foto_referensi in STUDENTS:
            cursor.execute("SELECT id FROM students WHERE nim = %s", (nim,))
            existing_student = cursor.fetchone()

            if existing_student:
                continue

            cursor.execute(
                """
                INSERT INTO students (nim, nama, jurusan, foto_referensi)
                VALUES (%s, %s, %s, %s)
                """,
                (nim, nama, jurusan, foto_referensi),
            )
            inserted_count += 1

        conn.commit()
        print(f"{inserted_count} data mahasiswa berhasil ditambahkan.")

    except Exception as e:
        print("Error:", e)
    finally:
        if cursor:
            cursor.close()
        if conn and conn.is_connected():
            conn.close()


if __name__ == "__main__":
    main()

