import os
import mysql.connector

conn = mysql.connector.connect(
    host=os.environ.get("MYSQL_HOST", "localhost"),
    port=int(os.environ.get("MYSQL_PORT", 3306)),
    user=os.environ.get("MYSQL_USER", "root"),
    password=os.environ.get("MYSQL_PASSWORD", ""),
    database=os.environ.get("MYSQL_DATABASE", "attendance_ai"),
)

cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS users(
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(50),
    password VARCHAR(255),
    role VARCHAR(20)
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS students(
    id INT AUTO_INCREMENT PRIMARY KEY,
    nim VARCHAR(20) UNIQUE,
    nama VARCHAR(100),
    jurusan VARCHAR(100),
    foto_referensi VARCHAR(255)
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS attendance(
    id INT AUTO_INCREMENT PRIMARY KEY,
    student_id INT,
    tanggal DATE,
    waktu TIME,
    similarity FLOAT,
    status VARCHAR(20),
    photo_path VARCHAR(255)
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS academic_risk(
    id INT AUTO_INCREMENT PRIMARY KEY,
    student_id INT,
    attendance_percentage FLOAT,
    risk_level VARCHAR(20)
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS academic_predictions(
    id INT AUTO_INCREMENT PRIMARY KEY,
    student_id INT NOT NULL,
    attendance_rate FLOAT,
    prediction_level VARCHAR(20),
    recommendation TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (student_id) REFERENCES students(id)
)
""")

conn.commit()

print("Semua tabel berhasil dibuat!")
