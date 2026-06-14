from datetime import date

from analytics_service import refresh_academic_predictions
from config.database import get_connection


SEED_DATES = [
    date(2025, 11, 12),
    date(2025, 12, 12),
    date(2026, 1, 12),
    date(2026, 2, 12),
    date(2026, 3, 12),
    date(2026, 4, 12),
    date(2026, 5, 12),
    date(2026, 6, 12),
]


def main():
    conn = None
    cursor = None
    inserted_count = 0
    skipped_count = 0

    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute(
            """
            SELECT id, nim, nama
            FROM students
            ORDER BY nim ASC
            """
        )
        students = cursor.fetchall()

        target_students = students[:50]


        for index, student in enumerate(target_students):
            for offset, attendance_date in enumerate(SEED_DATES):
                if index < 5:
                    status = "VALID" if offset < 6 else "INVALID"
                    similarity = 95.0 - (offset * 2.2)
                elif index < 10:
                    status = "VALID" if offset in (0, 2, 5, 7) else "INVALID"
                    similarity = 88.0 if status == "VALID" else 52.5
                else:
                    status = "VALID" if offset in (1, 6) else "INVALID"
                    similarity = 83.5 if status == "VALID" else 41.8

                attendance_time = f"{8 + (index % 4):02d}:{(offset * 7 + index * 3) % 60:02d}:00"

                cursor.execute(
                    """
                    SELECT id
                    FROM attendance
                    WHERE student_id = %s AND tanggal = %s AND waktu = %s
                    """,
                    (student["id"], attendance_date, attendance_time),
                )
                existing_row = cursor.fetchone()
                if existing_row:
                    skipped_count += 1
                    continue

                cursor.execute(
                    """
                    INSERT INTO attendance (student_id, tanggal, waktu, similarity, status, photo_path)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (
                        student["id"],
                        attendance_date,
                        attendance_time,
                        similarity,
                        status,
                        None,
                    ),
                )
                inserted_count += 1

        conn.commit()
        refresh_academic_predictions()

        print(f"Dummy attendance inserted: {inserted_count}")
        print(f"Dummy attendance skipped: {skipped_count}")
        print("Predictions refreshed successfully.")

    except Exception as e:
        if conn:
            conn.rollback()
        print("Error:", e)

    finally:
        if cursor:
            cursor.close()
        if conn and conn.is_connected():
            conn.close()


if __name__ == "__main__":
    main()
