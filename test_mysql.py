import mysql.connector

try:
    conn = mysql.connector.connect(
        host="172.0.0.1",
        user="root",
        password="root"
    )

    cursor = conn.cursor()

    cursor.execute(
        "CREATE DATABASE IF NOT EXISTS attendance_ai"
    )

    print("Database attendance_ai berhasil dibuat!")

except Exception as e:
    print("Error:", e)
