import os
import uuid
from datetime import datetime
from functools import wraps

import mysql.connector
from flask import Flask
from flask import flash
from flask import redirect
from flask import render_template
from flask import request
from flask import send_file
from flask import session
from flask import url_for
from werkzeug.security import check_password_hash
from werkzeug.security import generate_password_hash
from werkzeug.utils import secure_filename

import analytics_service as analytics
from config.database import get_connection
from student_account_service import sync_student_accounts

try:
    import numpy as np
except ImportError:
    np = None

try:
    import cv2
except ImportError:
    cv2 = None

try:
    from deepface import DeepFace
except ImportError:
    DeepFace = None

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "attendance-ai-secret-key")
app.config["REFERENCE_UPLOAD_FOLDER"] = os.path.join(
    app.root_path,
    "static",
    "uploads",
    "reference",
)
app.config["ATTENDANCE_UPLOAD_FOLDER"] = os.path.join(
    app.root_path,
    "static",
    "uploads",
    "attendance",
)
app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif"}
REFERENCE_RELATIVE_FOLDER = "uploads/reference"
ATTENDANCE_RELATIVE_FOLDER = "uploads/attendance"

os.makedirs(app.config["REFERENCE_UPLOAD_FOLDER"], exist_ok=True)
os.makedirs(app.config["ATTENDANCE_UPLOAD_FOLDER"], exist_ok=True)
analytics.ensure_analytics_tables()


def login_required(view_func):
    @wraps(view_func)
    def wrapped_view(*args, **kwargs):
        if "user_id" not in session:
            flash("Silakan login terlebih dahulu.", "warning")
            return redirect(url_for("login"))
        return view_func(*args, **kwargs)

    return wrapped_view


def is_valid_password(input_password, stored_password):
    if not stored_password:
        return False

    if stored_password.startswith("pbkdf2:sha256:") or stored_password.startswith("scrypt:"):
        return check_password_hash(stored_password, input_password)

    return input_password == stored_password


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def save_uploaded_file(photo_file, destination_folder, relative_folder):
    if not photo_file or not photo_file.filename:
        return None

    if not allowed_file(photo_file.filename):
        raise ValueError("Format foto harus png, jpg, jpeg, atau gif.")

    original_name = secure_filename(photo_file.filename)
    extension = original_name.rsplit(".", 1)[1].lower()
    filename = f"{uuid.uuid4().hex}.{extension}"
    file_path = os.path.join(destination_folder, filename)
    photo_file.save(file_path)

    return os.path.join(relative_folder, filename).replace("\\", "/")


def save_reference_photo(photo_file):
    return save_uploaded_file(
        photo_file,
        app.config["REFERENCE_UPLOAD_FOLDER"],
        REFERENCE_RELATIVE_FOLDER,
    )


def save_attendance_photo(photo_file):
    return save_uploaded_file(
        photo_file,
        app.config["ATTENDANCE_UPLOAD_FOLDER"],
        ATTENDANCE_RELATIVE_FOLDER,
    )


def delete_uploaded_photo(photo_path):
    if not photo_path:
        return

    absolute_path = os.path.join(app.root_path, "static", photo_path.replace("/", os.sep))
    if os.path.exists(absolute_path):
        os.remove(absolute_path)


def get_student_by_id(student_id):
    conn = None
    cursor = None

    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT id, nim, nama, jurusan, foto_referensi
            FROM students
            WHERE id = %s
            """,
            (student_id,),
        )
        return cursor.fetchone()
    finally:
        if cursor:
            cursor.close()
        if conn and conn.is_connected():
            conn.close()


def get_students_for_dropdown():
    conn = None
    cursor = None

    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT id, nim, nama, jurusan, foto_referensi
            FROM students
            ORDER BY nim ASC
            """
        )
        return cursor.fetchall()
    finally:
        if cursor:
            cursor.close()
        if conn and conn.is_connected():
            conn.close()


def get_absolute_photo_path(photo_path):
    if not photo_path:
        return None

    normalized_path = photo_path.replace("/", os.sep)
    return os.path.join(app.root_path, "static", normalized_path)


def load_image_with_opencv(image_path):
    if cv2 is None:
        raise RuntimeError("Library opencv-python belum terpasang.")

    image = cv2.imread(image_path)
    if image is None:
        raise ValueError("File gambar tidak dapat dibaca. Pastikan file valid.")
    return cv2.cvtColor(image, cv2.COLOR_BGR2RGB)


def distance_to_similarity(distance):
    if np is None:
        raise RuntimeError("Library numpy belum terpasang.")

    safe_distance = float(np.clip(distance, 0.0, 1.0))
    similarity = (1 - safe_distance) * 100
    return round(max(0.0, min(100.0, similarity)), 2)


def verify_faces(reference_image_path, selfie_image_path):
    if DeepFace is None or cv2 is None or np is None:
        raise RuntimeError(
            "Library deepface, numpy, atau opencv-python belum terpasang."
        )

    # Validasi file gambar lebih awal agar error upload lebih mudah dipahami.
    load_image_with_opencv(reference_image_path)
    load_image_with_opencv(selfie_image_path)

    result = DeepFace.verify(
        img1_path=reference_image_path,
        img2_path=selfie_image_path,
        enforce_detection=False,
    )

    if "verified" not in result or "distance" not in result:
        raise ValueError("Hasil verifikasi DeepFace tidak lengkap.")

    verified = bool(result["verified"])
    distance = float(result["distance"])
    similarity = distance_to_similarity(distance)
    status = "VALID" if verified else "INVALID"

    return similarity, status


@app.route("/", methods=["GET", "POST"])
def login():

    if "user_id" in session:
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        role = request.form.get("role", "").strip()

        if not username or not password:
            flash("Username dan password wajib diisi.", "danger")
            return render_template("login.html")

        if not role:
            flash("Role wajib dipilih.", "danger")
            return render_template("login.html")

        conn = None
        cursor = None

        try:
            conn = get_connection()
            cursor = conn.cursor(dictionary=True)
            cursor.execute(
                """
                SELECT id, username, password, role
                FROM users
                WHERE username = %s AND role = %s
                """,
                (username, role),
            )
            user = cursor.fetchone()

            if not user or not is_valid_password(password, user["password"]):
                flash("Username atau password salah.", "danger")
                return render_template("login.html")

            session["user_id"] = user["id"]
            session["username"] = user["username"]
            session["role"] = user["role"]

            # Jika student, set session["student_id"] dari students (relasi berdasarkan students.id)
            if session["role"] == "student":
                # username = NIM
                cursor.execute(
                    """
                    SELECT id
                    FROM students
                    WHERE nim = %s
                    """,
                    (session["username"],),
                )
                student_row = cursor.fetchone()
                if not student_row:
                    flash("Data mahasiswa tidak ditemukan untuk NIM ini.", "danger")
                    return render_template("login.html")
                session["student_id"] = student_row["id"]
                flash("Login berhasil.", "success")
                return redirect(url_for("student_dashboard"))

            flash("Login berhasil.", "success")
            return redirect(url_for("dashboard"))


        except Exception as e:
            flash(f"Gagal login: {e}", "danger")
            return render_template("login.html")

        finally:
            if cursor:
                cursor.close()
            if conn and conn.is_connected():
                conn.close()

    return render_template("login.html")




def admin_required(view_func):
    @wraps(view_func)
    def wrapped_view(*args, **kwargs):
        if "user_id" not in session:
            flash("Silakan login terlebih dahulu.", "warning")
            return redirect(url_for("login"))
        if session.get("role") != "admin":
            flash("Akses ditolak: hanya admin.", "danger")
            if session.get("role") == "student":
                return redirect(url_for("student_dashboard"))
            return redirect(url_for("dashboard"))
        return view_func(*args, **kwargs)

    return wrapped_view


def student_required(view_func):
    @wraps(view_func)
    def wrapped_view(*args, **kwargs):
        if "user_id" not in session:
            flash("Silakan login terlebih dahulu.", "warning")
            return redirect(url_for("login"))
        if session.get("role") != "student":
            flash("Akses ditolak: hanya student.", "danger")
            if session.get("role") == "admin":
                return redirect(url_for("dashboard"))
            return redirect(url_for("login"))
        return view_func(*args, **kwargs)

    return wrapped_view


def calculate_attendance_rate(student_id):
    conn = None
    cursor = None
    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT
                COUNT(*) AS total_absensi,
                SUM(CASE WHEN status = 'VALID' THEN 1 ELSE 0 END) AS total_hadir
            FROM attendance
            WHERE student_id = %s
            """,
            (student_id,),
        )
        row = cursor.fetchone() or {"total_absensi": 0, "total_hadir": 0}
        total_absensi = int(row.get("total_absensi") or 0)
        total_hadir = int(row.get("total_hadir") or 0)
        rate = (total_hadir / total_absensi) * 100 if total_absensi > 0 else 0.0
        return round(rate, 2), total_hadir, total_absensi
    finally:
        if cursor:
            cursor.close()
        if conn and conn.is_connected():
            conn.close()


def calculate_risk_level(rate):
    try:
        rate = float(rate)
    except Exception:
        rate = 0.0

    if rate >= 80:
        return "LOW RISK"
    if 60 <= rate <= 79:
        return "MEDIUM RISK"
    return "HIGH RISK"


@app.route("/dashboard")
@login_required
@admin_required
def dashboard():
    try:
        stats = analytics.get_dashboard_summary()
        present_today = 0
        conn = None
        cursor = None
        try:
            conn = get_connection()
            cursor = conn.cursor(dictionary=True)
            cursor.execute(
                """
                SELECT COUNT(*) AS present_today
                FROM attendance
                WHERE tanggal = CURDATE() AND status = 'VALID'
                """
            )
            row = cursor.fetchone() or {}
            present_today = int(row.get("present_today") or 0)
        finally:
            if cursor:
                cursor.close()
            if conn and conn.is_connected():
                conn.close()
    except Exception as e:
        flash(f"Gagal mengambil data dashboard: {e}", "danger")
        stats = {
            "total_students": 0,
            "total_attendance": 0,
            "valid_attendance": 0,
            "invalid_attendance": 0,
            "verification_accuracy": 0.0,
            "low_risk_students": 0,
            "medium_risk_students": 0,
            "high_risk_students": 0,
            "safe_students": 0,
            "at_risk_students": 0,
            "critical_students": 0,
            "attendance_trend": {"labels": [], "values": [], "trend_label": "Stable"},
            "risk_distribution": {"labels": [], "values": []},
            "prediction_distribution": {"labels": [], "values": []},
        }
        present_today = 0

    return render_template(
        "dashboard.html",
        total_students=stats["total_students"],
        present_today=present_today,
        total_attendance=stats["total_attendance"],
        valid_attendance=stats["valid_attendance"],
        invalid_attendance=stats["invalid_attendance"],
        verification_accuracy=stats["verification_accuracy"],
        low_risk_students=stats["low_risk_students"],
        medium_risk_students=stats["medium_risk_students"],
        high_risk_students=stats["high_risk_students"],
        safe_students=stats["safe_students"],
        at_risk_students=stats["at_risk_students"],
        critical_students=stats["critical_students"],
        attendance_trend=stats["attendance_trend"],
        risk_distribution=stats["risk_distribution"],
        prediction_distribution=stats["prediction_distribution"],
        username=session.get("username"),
        role=session.get("role"),
    )


@app.route("/students")
@login_required
@admin_required
def students():

    conn = None
    cursor = None
    student_rows = []

    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT id, nim, nama, jurusan, foto_referensi
            FROM students
            ORDER BY nim ASC
            """
        )
        student_rows = cursor.fetchall()
    except Exception as e:
        flash(f"Gagal mengambil data mahasiswa: {e}", "danger")
    finally:
        if cursor:
            cursor.close()
        if conn and conn.is_connected():
            conn.close()

    return render_template("students.html", students=student_rows)


@app.route("/students/reset-passwords", methods=["POST"])
@login_required
@admin_required
def reset_student_passwords():
    try:
        result = sync_student_accounts(reset_existing_passwords=True)
        flash(
            (
                "Reset password student berhasil. "
                f"Diupdate: {result['updated_count']}, "
                f"dibuat baru: {result['created_count']}, "
                f"konflik: {result['conflict_count']}."
            ),
            "success",
        )
    except Exception as e:
        flash(f"Gagal reset password student: {e}", "danger")

    return redirect(url_for("students"))


@app.route("/students/add", methods=["GET", "POST"])
@login_required
def add_student():
    if request.method == "POST":
        nim = request.form.get("nim", "").strip()
        nama = request.form.get("nama", "").strip()
        jurusan = request.form.get("jurusan", "").strip()
        photo_file = request.files.get("foto_referensi")

        if not nim or not nama or not jurusan:
            flash("NIM, nama, dan jurusan wajib diisi.", "danger")
            return render_template("add_student.html")

        conn = None
        cursor = None
        photo_path = None

        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM students WHERE nim = %s", (nim,))
            existing_student = cursor.fetchone()

            if existing_student:
                flash("NIM sudah terdaftar. Gunakan NIM lain.", "danger")
                return render_template("add_student.html")

            photo_path = save_reference_photo(photo_file)

            cursor.execute(
                """
                INSERT INTO students (nim, nama, jurusan, foto_referensi)
                VALUES (%s, %s, %s, %s)
                """,
                (nim, nama, jurusan, photo_path),
            )
            conn.commit()
            try:
                sync_student_accounts(reset_existing_passwords=False)
            except Exception as sync_error:
                flash(
                    f"Data mahasiswa berhasil ditambahkan, tetapi sinkron akun student gagal: {sync_error}",
                    "warning",
                )

            flash("Data mahasiswa berhasil ditambahkan.", "success")
            return redirect(url_for("students"))

        except ValueError as e:
            flash(str(e), "danger")
            return render_template("add_student.html")
        except mysql.connector.Error as e:
            if photo_path:
                delete_uploaded_photo(photo_path)
            flash(f"Gagal menambahkan mahasiswa: {e}", "danger")
            return render_template("add_student.html")
        finally:
            if cursor:
                cursor.close()
            if conn and conn.is_connected():
                conn.close()

    return render_template("add_student.html")


@app.route("/students/edit/<int:student_id>", methods=["GET", "POST"])
@login_required
def edit_student(student_id):
    student = get_student_by_id(student_id)
    if not student:
        flash("Data mahasiswa tidak ditemukan.", "danger")
        return redirect(url_for("students"))

    if request.method == "POST":
        old_nim = student["nim"]
        nim = request.form.get("nim", "").strip()
        nama = request.form.get("nama", "").strip()
        jurusan = request.form.get("jurusan", "").strip()
        photo_file = request.files.get("foto_referensi")

        if not nim or not nama or not jurusan:
            flash("NIM, nama, dan jurusan wajib diisi.", "danger")
            return render_template("edit_student.html", student=student)

        conn = None
        cursor = None
        new_photo_path = None

        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id FROM students WHERE nim = %s AND id != %s",
                (nim, student_id),
            )
            existing_student = cursor.fetchone()

            if existing_student:
                flash("NIM sudah digunakan oleh mahasiswa lain.", "danger")
                return render_template("edit_student.html", student=student)

            if photo_file and photo_file.filename:
                new_photo_path = save_reference_photo(photo_file)
            else:
                new_photo_path = student["foto_referensi"]

            cursor.execute(
                """
                UPDATE students
                SET nim = %s, nama = %s, jurusan = %s, foto_referensi = %s
                WHERE id = %s
                """,
                (nim, nama, jurusan, new_photo_path, student_id),
            )
            conn.commit()

            if photo_file and photo_file.filename and student["foto_referensi"]:
                delete_uploaded_photo(student["foto_referensi"])

            if old_nim != nim:
                cursor.execute(
                    """
                    UPDATE users
                    SET username = %s, password = %s
                    WHERE username = %s AND role = 'student'
                    """,
                    (nim, generate_password_hash(nim), old_nim),
                )
                conn.commit()
                try:
                    sync_student_accounts(reset_existing_passwords=False)
                except Exception as sync_error:
                    flash(
                        f"Data mahasiswa berhasil diperbarui, tetapi sinkron akun student gagal: {sync_error}",
                        "warning",
                    )

            flash("Data mahasiswa berhasil diperbarui.", "success")
            return redirect(url_for("students"))

        except ValueError as e:
            flash(str(e), "danger")
            return render_template("edit_student.html", student=student)
        except mysql.connector.Error as e:
            if new_photo_path and new_photo_path != student["foto_referensi"]:
                delete_uploaded_photo(new_photo_path)
            flash(f"Gagal memperbarui mahasiswa: {e}", "danger")
            return render_template("edit_student.html", student=student)
        finally:
            if cursor:
                cursor.close()
            if conn and conn.is_connected():
                conn.close()

    return render_template("edit_student.html", student=student)


@app.route("/students/delete/<int:student_id>", methods=["POST"])
@login_required
def delete_student(student_id):
    student = get_student_by_id(student_id)
    if not student:
        flash("Data mahasiswa tidak ditemukan.", "danger")
        return redirect(url_for("students"))

    conn = None
    cursor = None

    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM students WHERE id = %s", (student_id,))
        cursor.execute(
            "DELETE FROM users WHERE username = %s AND role = 'student'",
            (student["nim"],),
        )
        conn.commit()

        if student["foto_referensi"]:
            delete_uploaded_photo(student["foto_referensi"])

        flash("Data mahasiswa berhasil dihapus.", "success")
    except mysql.connector.Error as e:
        flash(f"Gagal menghapus mahasiswa: {e}", "danger")
    finally:
        if cursor:
            cursor.close()
        if conn and conn.is_connected():
            conn.close()

    return redirect(url_for("students"))


@app.route("/attendance", methods=["GET", "POST"])
@login_required
@admin_required
def attendance():

    students = get_students_for_dropdown()
    result = None

    if request.method == "POST":
        student_id = request.form.get("student_id", "").strip()
        selfie_file = request.files.get("selfie_photo")

        if not student_id or not selfie_file or not selfie_file.filename:
            flash("Mahasiswa dan foto selfie wajib diisi.", "danger")
            return render_template("attendance.html", students=students, result=result, selected_student=None)

        student = get_student_by_id(student_id)
        if not student:
            flash("Data mahasiswa tidak ditemukan.", "danger")
            return render_template("attendance.html", students=students, result=result, selected_student=None)

        if not student["foto_referensi"]:
            flash("Foto referensi mahasiswa belum tersedia.", "danger")
            return render_template("attendance.html", students=students, result=result, selected_student=None)

        reference_path = get_absolute_photo_path(student["foto_referensi"])
        if not reference_path or not os.path.exists(reference_path):
            flash("File foto referensi mahasiswa tidak ditemukan.", "danger")
            return render_template("attendance.html", students=students, result=result, selected_student=None)

        selfie_path = None
        conn = None
        cursor = None

        try:
            selfie_relative_path = save_attendance_photo(selfie_file)
            selfie_path = get_absolute_photo_path(selfie_relative_path)

            similarity, status = verify_faces(reference_path, selfie_path)

            result = {
                "student_name": student["nama"],
                "student_nim": student["nim"],
                "similarity": similarity,
                "status": status,
                "photo_path": selfie_relative_path,
            }

            if status == "VALID":
                conn = get_connection()
                cursor = conn.cursor()
                now = datetime.now()
                cursor.execute(
                    """
                    INSERT INTO attendance (student_id, tanggal, waktu, similarity, status, photo_path)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (
                        student["id"],
                        now.date(),
                        now.strftime("%H:%M:%S"),
                        similarity,
                        status,
                        selfie_relative_path,
                    ),
                )
                conn.commit()

                flash("Absensi berhasil diproses dan disimpan.", "success")

                # Pastikan koneksi ditutup untuk cabang VALID.
                cursor.close()
                conn.close()
            else:
                conn = get_connection()
                cursor = conn.cursor()
                now = datetime.now()
                cursor.execute(
                    """
                    INSERT INTO attendance (student_id, tanggal, waktu, similarity, status, photo_path)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (
                        student["id"],
                        now.date(),
                        now.strftime("%H:%M:%S"),
                        similarity,
                        status,
                        None,
                    ),
                )
                conn.commit()

                # Foto selfie tetap dihapus agar tidak menumpuk data yang tidak valid.
                if selfie_path and os.path.exists(selfie_path):
                    os.remove(selfie_path)

                # Agar UI tetap bisa menampilkan confidence score, selfie_path dibuat None.
                result["photo_path"] = None
                flash("Verifikasi gagal. Attempt dicatat sebagai INVALID.", "danger")

        except ValueError as e:
            if selfie_path and os.path.exists(selfie_path):
                os.remove(selfie_path)
            flash(str(e), "danger")
        except RuntimeError as e:
            if selfie_path and os.path.exists(selfie_path):
                os.remove(selfie_path)
            flash(str(e), "danger")
        except mysql.connector.Error as e:
            if selfie_path and os.path.exists(selfie_path):
                os.remove(selfie_path)
            flash(f"Gagal menyimpan absensi: {e}", "danger")
        except Exception as e:
            if selfie_path and os.path.exists(selfie_path):
                os.remove(selfie_path)
            flash(f"Terjadi kesalahan saat memproses absensi: {e}", "danger")
        finally:
            if cursor:
                cursor.close()
            if conn and conn.is_connected():
                conn.close()

    return render_template("attendance.html", students=students, result=result, selected_student=None)


@app.route("/attendance/history")
@login_required
@admin_required
def attendance_history():


    conn = None
    cursor = None
    records = []

    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT
                attendance.id,
                students.nama,
                students.nim,
                attendance.tanggal,
                attendance.waktu,
                attendance.similarity,
                attendance.status,
                attendance.photo_path
            FROM attendance
            INNER JOIN students ON students.id = attendance.student_id
            ORDER BY attendance.tanggal DESC, attendance.waktu DESC
            """
        )
        records = cursor.fetchall()
    except Exception as e:
        flash(f"Gagal mengambil riwayat absensi: {e}", "danger")
    finally:
        if cursor:
            cursor.close()
        if conn and conn.is_connected():
            conn.close()

    return render_template("attendance_history.html", records=records)


@app.route("/predictions")
@login_required
@admin_required
def predictions():
    stats = analytics.get_dashboard_summary()
    prediction_rows = analytics.get_latest_prediction_rows()

    return render_template(
        "predictions.html",
        prediction_rows=prediction_rows,
        total_students=stats["total_students"],
        total_attendance=stats["total_attendance"],
        low_risk_students=stats["low_risk_students"],
        medium_risk_students=stats["medium_risk_students"],
        high_risk_students=stats["high_risk_students"],
        safe_students=stats["safe_students"],
        at_risk_students=stats["at_risk_students"],
        critical_students=stats["critical_students"],
        attendance_trend=stats["attendance_trend"],
        risk_distribution=stats["risk_distribution"],
        prediction_distribution=stats["prediction_distribution"],
    )


@app.route("/testing-report")
@login_required
@admin_required
def testing_report():
    test_rows = analytics.get_testing_report_rows()
    pass_count = sum(1 for row in test_rows if row["status"] == "PASS")
    fail_count = sum(1 for row in test_rows if row["status"] == "FAIL")

    return render_template(
        "testing_report.html",
        test_rows=test_rows,
        pass_count=pass_count,
        fail_count=fail_count,
        total_cases=len(test_rows),
    )


@app.route("/accuracy-report")
@login_required
@admin_required
def accuracy_report():
    accuracy = analytics.get_accuracy_summary()

    return render_template(
        "accuracy_report.html",
        accuracy=accuracy,
    )


@app.route("/research-results")
@login_required
@admin_required
def research_results():
    summary = analytics.get_research_results_summary()
    return render_template(
        "research_results.html",
        summary=summary,
    )


@app.route("/export/<report_type>/<file_format>")
@login_required
@admin_required
def export_report(report_type, file_format):
    try:
        file_stream, filename, mimetype = analytics.export_report(report_type, file_format)
        return send_file(
            file_stream,
            as_attachment=True,
            download_name=filename,
            mimetype=mimetype,
        )
    except Exception as e:
        flash(f"Gagal mengekspor report: {e}", "danger")
        return redirect(url_for("dashboard"))


@app.route("/student/dashboard")
@login_required
@student_required
def student_dashboard():
    student_id = session.get("student_id")
    if not student_id:
        flash("student_id belum tersedia di session.", "danger")
        return redirect(url_for("login"))

    student_dashboard_data = analytics.get_student_dashboard_summary(student_id)
    if not student_dashboard_data:
        flash("Data mahasiswa tidak ditemukan.", "danger")
        return redirect(url_for("login"))

    return render_template(
        "student_dashboard.html",
        nama=student_dashboard_data["nama"],
        nim=student_dashboard_data["nim"],
        attendance_rate=student_dashboard_data["attendance_rate"],
        risk_level=student_dashboard_data["risk_level"],
        prediction_level=student_dashboard_data["prediction_level"],
        recommendation=student_dashboard_data["recommendation"],
        trend_label=student_dashboard_data["trend_label"],
        total_hadir=student_dashboard_data["total_hadir"],
        total_absen=student_dashboard_data["total_absen"],
        total_absensi=student_dashboard_data["total_attempts"],
        attendance_trend=student_dashboard_data["attendance_trend"],
    )


@app.route("/student/history")
@login_required
@student_required
def student_history():
    student_id = session.get("student_id")
    if not student_id:
        flash("student_id belum tersedia di session.", "danger")
        return redirect(url_for("login"))

    conn = None
    cursor = None
    records = []

    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT
                tanggal,
                waktu,
                similarity,
                status,
                photo_path
            FROM attendance
            WHERE student_id = %s
            ORDER BY tanggal DESC, waktu DESC
            """,
            (student_id,),
        )
        records = cursor.fetchall()
    except Exception as e:
        flash(f"Gagal mengambil riwayat Anda: {e}", "danger")
    finally:
        if cursor:
            cursor.close()
        if conn and conn.is_connected():
            conn.close()

    return render_template("student_history.html", records=records)


@app.route("/student/attendance", methods=["GET", "POST"])
@login_required
@student_required
def student_attendance():
    student_id = session.get("student_id")
    if not student_id:
        flash("student_id belum tersedia di session.", "danger")
        return redirect(url_for("login"))

    student = get_student_by_id(student_id)
    if not student:
        flash("Data mahasiswa tidak ditemukan.", "danger")
        return redirect(url_for("student_dashboard"))

    if not student["foto_referensi"]:
        flash("Foto referensi mahasiswa belum tersedia.", "danger")
        return render_template(
            "attendance.html",
            students=[],
            result=None,
            selected_student=student,
        )

    reference_path = get_absolute_photo_path(student["foto_referensi"])
    if not reference_path or not os.path.exists(reference_path):
        flash("File foto referensi mahasiswa tidak ditemukan.", "danger")
        return render_template(
            "attendance.html",
            students=[],
            result=None,
            selected_student=student,
        )

    result = None

    if request.method == "POST":
        selfie_file = request.files.get("selfie_photo")

        if not selfie_file or not selfie_file.filename:
            flash("Foto selfie wajib diisi.", "danger")
            return render_template(
                "attendance.html",
                students=[],
                result=result,
                selected_student=student,
            )

        selfie_path = None
        conn = None
        cursor = None

        try:
            selfie_relative_path = save_attendance_photo(selfie_file)
            selfie_path = get_absolute_photo_path(selfie_relative_path)

            similarity, status = verify_faces(reference_path, selfie_path)

            result = {
                "student_name": student["nama"],
                "student_nim": student["nim"],
                "similarity": similarity,
                "status": status,
                "photo_path": selfie_relative_path if status == "VALID" else None,
            }

            if status == "VALID":
                conn = get_connection()
                cursor = conn.cursor()
                now = datetime.now()
                cursor.execute(
                    """
                    INSERT INTO attendance (student_id, tanggal, waktu, similarity, status, photo_path)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (
                        student_id,
                        now.date(),
                        now.strftime("%H:%M:%S"),
                        similarity,
                        status,
                        selfie_relative_path,
                    ),
                )
                conn.commit()
                flash("Absensi Anda berhasil disimpan.", "success")
            else:
                conn = get_connection()
                cursor = conn.cursor()
                now = datetime.now()
                cursor.execute(
                    """
                    INSERT INTO attendance (student_id, tanggal, waktu, similarity, status, photo_path)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (
                        student_id,
                        now.date(),
                        now.strftime("%H:%M:%S"),
                        similarity,
                        status,
                        None,
                    ),
                )
                conn.commit()

                # Tolak absensi: hapus foto selfie setelah hasil INVALID dicatat.
                if selfie_path and os.path.exists(selfie_path):
                    os.remove(selfie_path)
                flash("Verifikasi gagal. Attempt dicatat sebagai INVALID.", "danger")

        except ValueError as e:
            if selfie_path and os.path.exists(selfie_path):
                os.remove(selfie_path)
            flash(str(e), "danger")
        except RuntimeError as e:
            if selfie_path and os.path.exists(selfie_path):
                os.remove(selfie_path)
            flash(str(e), "danger")
        except mysql.connector.Error as e:
            if selfie_path and os.path.exists(selfie_path):
                os.remove(selfie_path)
            flash(f"Gagal menyimpan absensi: {e}", "danger")
        except Exception as e:
            if selfie_path and os.path.exists(selfie_path):
                os.remove(selfie_path)
            flash(f"Terjadi kesalahan saat memproses absensi: {e}", "danger")
        finally:
            if cursor:
                cursor.close()
            if conn and conn.is_connected():
                conn.close()

    return render_template(
        "attendance.html",
        students=[],
        result=result,
        selected_student=student,
    )


@app.route("/logout")
@login_required
def logout():
    session.clear()
    flash("Anda berhasil logout.", "success")
    return redirect(url_for("login"))


if __name__ == "__main__":
    app.run(debug=True)
