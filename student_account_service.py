from werkzeug.security import generate_password_hash

from config.database import get_connection


DEFAULT_ROLE = "student"


def sync_student_accounts(reset_existing_passwords=False):
    conn = None
    cursor = None
    created_count = 0
    updated_count = 0
    skipped_count = 0
    conflict_count = 0

    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute(
            """
            SELECT nim, nama
            FROM students
            WHERE nim IS NOT NULL AND nim != ''
            ORDER BY nim ASC
            """
        )
        students = cursor.fetchall()

        for student in students:
            username = student["nim"].strip()
            password_hash = generate_password_hash(username)

            cursor.execute(
                """
                SELECT id, role
                FROM users
                WHERE username = %s
                """,
                (username,),
            )
            existing_user = cursor.fetchone()

            if existing_user:
                if existing_user["role"] != DEFAULT_ROLE:
                    conflict_count += 1
                    continue

                if reset_existing_passwords:
                    cursor.execute(
                        """
                        UPDATE users
                        SET password = %s
                        WHERE id = %s
                        """,
                        (password_hash, existing_user["id"]),
                    )
                    updated_count += 1
                else:
                    skipped_count += 1
                continue

            cursor.execute(
                """
                INSERT INTO users (username, password, role)
                VALUES (%s, %s, %s)
                """,
                (username, password_hash, DEFAULT_ROLE),
            )
            created_count += 1

        conn.commit()

        return {
            "created_count": created_count,
            "updated_count": updated_count,
            "skipped_count": skipped_count,
            "conflict_count": conflict_count,
        }

    except Exception:
        if conn:
            conn.rollback()
        raise

    finally:
        if cursor:
            cursor.close()
        if conn and conn.is_connected():
            conn.close()
