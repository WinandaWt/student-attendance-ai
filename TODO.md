# TODO - Data Mahasiswa 50 & Seed Attendance

## Step 1
- [x] Update `insert_students.py` menjadi 50 mahasiswa (NIM 220001–220050) dengan nama & jurusan realistis, tanpa teks "dummy".



## Step 2
- [x] Update `seed_evaluation_data.py` agar memakai `students[:50]` (bukan `[:15]`).


## Step 3
- [x] Jalankan:
  - `python insert_students.py`
  - `python sync_student_accounts.py`
  - `python seed_evaluation_data.py`


## Step 4
- [ ] Verifikasi cepat dengan membuka endpoint `/students` dan memastikan jumlah data 50.


