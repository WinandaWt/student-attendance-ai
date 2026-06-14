import mysql.connector

try:
    conn = mysql.connector.connect(
        host="localhost",
        user="root",
        password=""
    )

    cursor = conn.cursor()

    cursor.execute(
        "CREATE DATABASE IF NOT EXISTS attendance_ai"
    )

    print("Database attendance_ai berhasil dibuat!")

except Exception as e:
    print("Error:", e)
