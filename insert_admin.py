import mysql.connector
from werkzeug.security import generate_password_hash


ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "admin123"
ADMIN_ROLE = "admin"


try:
    conn = mysql.connector.connect(
        host="localhost",
        user="root",
        password="",
        database="attendance_ai",
    )
    cursor = conn.cursor()

    cursor.execute(
        "SELECT id FROM users WHERE username = %s",
        (ADMIN_USERNAME,),
    )
    existing_admin = cursor.fetchone()

    if existing_admin:
        print(f"User '{ADMIN_USERNAME}' sudah ada di tabel users.")
    else:
        cursor.execute(
            """
            INSERT INTO users (username, password, role)
            VALUES (%s, %s, %s)
            """,
            (
                ADMIN_USERNAME,
                generate_password_hash(ADMIN_PASSWORD),
                ADMIN_ROLE,
            ),
        )
        conn.commit()
        print("Admin berhasil ditambahkan!")
        print(f"Username: {ADMIN_USERNAME}")
        print(f"Password: {ADMIN_PASSWORD}")

except Exception as e:
    print("Error:", e)

finally:
    if "cursor" in locals():
        cursor.close()
    if "conn" in locals() and conn.is_connected():
        conn.close()
