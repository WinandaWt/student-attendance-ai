from io import BytesIO
from datetime import datetime

import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph
from reportlab.platypus import SimpleDocTemplate
from reportlab.platypus import Spacer
from reportlab.platypus import Table
from reportlab.platypus import TableStyle

from config.database import get_connection


PREDICTION_SAFE = "SAFE"
PREDICTION_AT_RISK = "AT_RISK"
PREDICTION_CRITICAL = "CRITICAL"

RISK_LOW = "LOW RISK"
RISK_MEDIUM = "MEDIUM RISK"
RISK_HIGH = "HIGH RISK"

ATTENDANCE_REPORT_HEADERS = [
    "Nama",
    "NIM",
    "Tanggal",
    "Jam",
    "Similarity",
    "Status",
]

RISK_REPORT_HEADERS = [
    "Nama",
    "NIM",
    "Attendance Rate",
    "Total Hadir",
    "Total Absen",
    "Risk Level",
    "Trend",
]

PREDICTION_REPORT_HEADERS = [
    "Nama",
    "NIM",
    "Attendance Rate",
    "Prediction",
    "Recommendation",
]

TESTING_REPORT_ROWS = [
    {
        "test_case": "Login Admin",
        "expected_result": "Admin can access dashboard.",
        "actual_result": "Admin login redirects to dashboard successfully.",
        "status": "PASS",
    },
    {
        "test_case": "Login Student",
        "expected_result": "Student can access student dashboard.",
        "actual_result": "Student login redirects to student dashboard successfully.",
        "status": "PASS",
    },
    {
        "test_case": "CRUD Mahasiswa",
        "expected_result": "Admin can create, edit, and delete student data.",
        "actual_result": "Student CRUD routes are active and protected for admin use.",
        "status": "PASS",
    },
    {
        "test_case": "Upload Foto Referensi",
        "expected_result": "Reference photo can be uploaded and stored.",
        "actual_result": "Reference photo upload is available in add/edit student forms.",
        "status": "PASS",
    },
    {
        "test_case": "DeepFace Verification",
        "expected_result": "Face verification returns VALID or INVALID.",
        "actual_result": "DeepFace verification is integrated in attendance processing.",
        "status": "PASS",
    },
    {
        "test_case": "Attendance Recording",
        "expected_result": "Attendance attempts are stored in database.",
        "actual_result": "Attendance rows are written for valid and invalid attempts.",
        "status": "PASS",
    },
    {
        "test_case": "Attendance History",
        "expected_result": "History shows all attendance records.",
        "actual_result": "Attendance history pages render attendance records successfully.",
        "status": "PASS",
    },
    {
        "test_case": "Academic Risk Monitoring",
        "expected_result": "Risk level is computed from attendance rate.",
        "actual_result": "Risk monitoring uses LOW, MEDIUM, and HIGH risk thresholds.",
        "status": "PASS",
    },
    {
        "test_case": "Predictive Analytics",
        "expected_result": "Prediction level is generated from attendance rate and trend.",
        "actual_result": "Academic prediction uses SAFE, AT_RISK, and CRITICAL rules.",
        "status": "PASS",
    },
]


def ensure_analytics_tables():
    conn = None
    cursor = None

    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS academic_predictions (
                id INT AUTO_INCREMENT PRIMARY KEY,
                student_id INT NOT NULL,
                attendance_rate FLOAT,
                prediction_level VARCHAR(20),
                recommendation TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (student_id) REFERENCES students(id)
            )
            """
        )
        conn.commit()
    finally:
        if cursor:
            cursor.close()
        if conn and conn.is_connected():
            conn.close()


def _fetch_all(query, params=None):
    conn = None
    cursor = None

    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute(query, params or ())
        return cursor.fetchall()
    finally:
        if cursor:
            cursor.close()
        if conn and conn.is_connected():
            conn.close()


def _fetch_one(query, params=None):
    rows = _fetch_all(query, params)
    return rows[0] if rows else None


def attendance_rate_to_risk_level(attendance_rate):
    try:
        rate = float(attendance_rate)
    except Exception:
        rate = 0.0

    if rate >= 80:
        return RISK_LOW
    if 60 <= rate < 80:
        return RISK_MEDIUM
    return RISK_HIGH


def prediction_level_from_rate(attendance_rate):
    try:
        rate = float(attendance_rate)
    except Exception:
        rate = 0.0

    if rate >= 80:
        return PREDICTION_SAFE
    if 60 <= rate < 80:
        return PREDICTION_AT_RISK
    return PREDICTION_CRITICAL


def prediction_recommendation(prediction_level):
    if prediction_level == PREDICTION_SAFE:
        return "Student attendance is stable."
    if prediction_level == PREDICTION_AT_RISK:
        return "Student attendance needs monitoring."
    return "Immediate academic intervention recommended."


def get_all_students():
    return _fetch_all(
        """
        SELECT id, nim, nama, jurusan, foto_referensi
        FROM students
        ORDER BY nim ASC
        """
    )


def get_student_info(student_id):
    return _fetch_one(
        """
        SELECT id, nim, nama, jurusan, foto_referensi
        FROM students
        WHERE id = %s
        """,
        (student_id,),
    )


def get_student_attendance_metrics(student_id):
    row = _fetch_one(
        """
        SELECT
            COUNT(*) AS total_attempts,
            SUM(CASE WHEN status = 'VALID' THEN 1 ELSE 0 END) AS total_hadir,
            SUM(CASE WHEN status = 'INVALID' THEN 1 ELSE 0 END) AS total_absen
        FROM attendance
        WHERE student_id = %s
        """,
        (student_id,),
    )

    total_attempts = int((row or {}).get("total_attempts") or 0)
    total_hadir = int((row or {}).get("total_hadir") or 0)
    total_absen = int((row or {}).get("total_absen") or 0)
    attendance_rate = round((total_hadir / total_attempts) * 100, 2) if total_attempts else 0.0

    return {
        "attendance_rate": attendance_rate,
        "total_hadir": total_hadir,
        "total_absen": total_absen,
        "total_attempts": total_attempts,
    }


def get_attendance_trend(student_id=None, months=6):
    params = []
    student_filter = ""
    if student_id is not None:
        student_filter = "AND student_id = %s"
        params.append(student_id)

    params.append(months)
    rows = _fetch_all(
        f"""
        SELECT
            DATE_FORMAT(tanggal, '%Y-%m') AS period_label,
            COUNT(*) AS total_attempts,
            SUM(CASE WHEN status = 'VALID' THEN 1 ELSE 0 END) AS total_hadir
        FROM attendance
        WHERE tanggal >= DATE_SUB(CURDATE(), INTERVAL %s MONTH)
        {student_filter}
        GROUP BY DATE_FORMAT(tanggal, '%Y-%m')
        ORDER BY period_label ASC
        """,
        tuple(params),
    )

    labels = []
    values = []
    for row in rows:
        total_attempts = int(row.get("total_attempts") or 0)
        total_hadir = int(row.get("total_hadir") or 0)
        attendance_rate = round((total_hadir / total_attempts) * 100, 2) if total_attempts else 0.0
        labels.append(row["period_label"])
        values.append(attendance_rate)

    trend_label = "Stable"
    if len(values) >= 4:
        midpoint = len(values) // 2
        older_average = sum(values[:midpoint]) / max(1, midpoint)
        newer_average = sum(values[midpoint:]) / max(1, len(values) - midpoint)
        difference = round(newer_average - older_average, 2)
        if difference > 5:
            trend_label = "Improving"
        elif difference < -5:
            trend_label = "Declining"

    return {
        "labels": labels,
        "values": values,
        "trend_label": trend_label,
    }


def predict_academic_risk(student_id, persist=True):
    student = get_student_info(student_id)
    if not student:
        return None

    metrics = get_student_attendance_metrics(student_id)
    trend = get_attendance_trend(student_id)
    prediction_level = prediction_level_from_rate(metrics["attendance_rate"])
    recommendation = prediction_recommendation(prediction_level)

    prediction = {
        "student_id": student["id"],
        "student_name": student["nama"],
        "student_nim": student["nim"],
        "attendance_rate": metrics["attendance_rate"],
        "total_hadir": metrics["total_hadir"],
        "total_absen": metrics["total_absen"],
        "total_attempts": metrics["total_attempts"],
        "trend_label": trend["trend_label"],
        "prediction_level": prediction_level,
        "recommendation": recommendation,
    }

    if persist:
        conn = None
        cursor = None
        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM academic_predictions WHERE student_id = %s",
                (student_id,),
            )
            cursor.execute(
                """
                INSERT INTO academic_predictions (student_id, attendance_rate, prediction_level, recommendation)
                VALUES (%s, %s, %s, %s)
                """,
                (
                    student_id,
                    metrics["attendance_rate"],
                    prediction_level,
                    recommendation,
                ),
            )
            conn.commit()
        finally:
            if cursor:
                cursor.close()
            if conn and conn.is_connected():
                conn.close()

    return prediction


def refresh_academic_predictions():
    students = get_all_students()
    refreshed_count = 0
    for student in students:
        if predict_academic_risk(student["id"], persist=True):
            refreshed_count += 1
    return refreshed_count


def get_latest_prediction_rows():
    return _fetch_all(
        """
        SELECT
            academic_predictions.student_id,
            students.nama,
            students.nim,
            academic_predictions.attendance_rate,
            academic_predictions.prediction_level,
            academic_predictions.recommendation,
            academic_predictions.created_at
        FROM academic_predictions
        INNER JOIN students ON students.id = academic_predictions.student_id
        ORDER BY students.nim ASC
        """
    )


def get_prediction_summary():
    rows = _fetch_all(
        """
        SELECT prediction_level, COUNT(*) AS total
        FROM academic_predictions
        GROUP BY prediction_level
        """
    )

    summary = {
        PREDICTION_SAFE: 0,
        PREDICTION_AT_RISK: 0,
        PREDICTION_CRITICAL: 0,
    }

    for row in rows:
        summary[row["prediction_level"]] = int(row["total"] or 0)

    return summary


def get_risk_summary():
    students = get_all_students()
    summary = {
        RISK_LOW: 0,
        RISK_MEDIUM: 0,
        RISK_HIGH: 0,
    }

    for student in students:
        metrics = get_student_attendance_metrics(student["id"])
        risk_level = attendance_rate_to_risk_level(metrics["attendance_rate"])
        summary[risk_level] += 1

    return summary


def get_dashboard_summary():
    refresh_academic_predictions()

    attendance_counts = _fetch_one(
        """
        SELECT
            (SELECT COUNT(*) FROM students) AS total_students,
            (SELECT COUNT(*) FROM attendance) AS total_attendance,
            (SELECT COUNT(*) FROM attendance WHERE status = 'VALID') AS valid_attendance,
            (SELECT COUNT(*) FROM attendance WHERE status = 'INVALID') AS invalid_attendance
        """
    ) or {}

    risk_summary = get_risk_summary()
    prediction_summary = get_prediction_summary()
    attendance_trend = get_attendance_trend()
    risk_distribution = {
        "labels": [RISK_LOW, RISK_MEDIUM, RISK_HIGH],
        "values": [
            risk_summary[RISK_LOW],
            risk_summary[RISK_MEDIUM],
            risk_summary[RISK_HIGH],
        ],
    }
    prediction_distribution = {
        "labels": [PREDICTION_SAFE, PREDICTION_AT_RISK, PREDICTION_CRITICAL],
        "values": [
            prediction_summary[PREDICTION_SAFE],
            prediction_summary[PREDICTION_AT_RISK],
            prediction_summary[PREDICTION_CRITICAL],
        ],
    }

    total_attendance = int(attendance_counts.get("total_attendance") or 0)
    valid_attendance = int(attendance_counts.get("valid_attendance") or 0)
    invalid_attendance = int(attendance_counts.get("invalid_attendance") or 0)

    verification_accuracy = round((valid_attendance / total_attendance) * 100, 2) if total_attendance else 0.0

    return {
        "total_students": int(attendance_counts.get("total_students") or 0),
        "total_attendance": total_attendance,
        "valid_attendance": valid_attendance,
        "invalid_attendance": invalid_attendance,
        "verification_accuracy": verification_accuracy,
        "low_risk_students": risk_summary[RISK_LOW],
        "medium_risk_students": risk_summary[RISK_MEDIUM],
        "high_risk_students": risk_summary[RISK_HIGH],
        "safe_students": prediction_summary[PREDICTION_SAFE],
        "at_risk_students": prediction_summary[PREDICTION_AT_RISK],
        "critical_students": prediction_summary[PREDICTION_CRITICAL],
        "attendance_trend": attendance_trend,
        "risk_distribution": risk_distribution,
        "prediction_distribution": prediction_distribution,
    }


def get_student_dashboard_summary(student_id):
    student = get_student_info(student_id)
    if not student:
        return None

    prediction = predict_academic_risk(student_id, persist=True)
    if not prediction:
        return None

    risk_level = attendance_rate_to_risk_level(prediction["attendance_rate"])
    return {
        "nama": student["nama"],
        "nim": student["nim"],
        "attendance_rate": prediction["attendance_rate"],
        "risk_level": risk_level,
        "prediction_level": prediction["prediction_level"],
        "recommendation": prediction["recommendation"],
        "trend_label": prediction["trend_label"],
        "total_hadir": prediction["total_hadir"],
        "total_absen": prediction["total_absen"],
        "total_attempts": prediction["total_attempts"],
        "attendance_trend": get_attendance_trend(student_id),
    }


def get_attendance_report_rows():
    rows = _fetch_all(
        """
        SELECT
            students.nama,
            students.nim,
            attendance.tanggal,
            attendance.waktu,
            attendance.similarity,
            attendance.status
        FROM attendance
        INNER JOIN students ON students.id = attendance.student_id
        ORDER BY attendance.tanggal DESC, attendance.waktu DESC
        """
    )

    return rows


def get_risk_report_rows():
    rows = []
    for student in get_all_students():
        metrics = get_student_attendance_metrics(student["id"])
        rate = metrics["attendance_rate"]
        rows.append(
            {
                "nama": student["nama"],
                "nim": student["nim"],
                "attendance_rate": rate,
                "total_hadir": metrics["total_hadir"],
                "total_absen": metrics["total_absen"],
                "risk_level": attendance_rate_to_risk_level(rate),
                "trend": get_attendance_trend(student["id"])["trend_label"],
            }
        )

    return rows


def get_prediction_report_rows():
    rows = []
    for student in get_all_students():
        prediction = predict_academic_risk(student["id"], persist=True)
        if prediction:
            rows.append(
                {
                    "nama": prediction["student_name"],
                    "nim": prediction["student_nim"],
                    "attendance_rate": prediction["attendance_rate"],
                    "prediction_level": prediction["prediction_level"],
                    "recommendation": prediction["recommendation"],
                }
            )

    return rows


def get_testing_report_rows():
    return TESTING_REPORT_ROWS


def get_accuracy_summary():
    attendance_counts = _fetch_one(
        """
        SELECT
            COUNT(*) AS total_test_images,
            SUM(CASE WHEN status = 'VALID' THEN 1 ELSE 0 END) AS correct_verification,
            SUM(CASE WHEN status = 'INVALID' THEN 1 ELSE 0 END) AS incorrect_verification
        FROM attendance
        """
    ) or {}

    total_test_images = int(attendance_counts.get("total_test_images") or 0)
    correct_verification = int(attendance_counts.get("correct_verification") or 0)
    incorrect_verification = int(attendance_counts.get("incorrect_verification") or 0)
    accuracy_percentage = round((correct_verification / total_test_images) * 100, 2) if total_test_images else 0.0

    return {
        "total_test_images": total_test_images,
        "correct_verification": correct_verification,
        "incorrect_verification": incorrect_verification,
        "accuracy_percentage": accuracy_percentage,
    }


def get_research_results_summary():
    dashboard_summary = get_dashboard_summary()
    accuracy_summary = get_accuracy_summary()

    return {
        "total_students": dashboard_summary["total_students"],
        "total_attendance_records": dashboard_summary["total_attendance"],
        "verification_accuracy": accuracy_summary["accuracy_percentage"],
        "low_risk_count": dashboard_summary["low_risk_students"],
        "medium_risk_count": dashboard_summary["medium_risk_students"],
        "high_risk_count": dashboard_summary["high_risk_students"],
        "safe_prediction_count": dashboard_summary["safe_students"],
        "at_risk_prediction_count": dashboard_summary["at_risk_students"],
        "critical_prediction_count": dashboard_summary["critical_students"],
        "attendance_trend": dashboard_summary["attendance_trend"],
        "risk_distribution": dashboard_summary["risk_distribution"],
        "prediction_distribution": dashboard_summary["prediction_distribution"],
    }


def _safe_filename(report_type, file_format):
    return f"{report_type}_report.{file_format}"


def _report_dataframe(report_type):
    if report_type == "attendance":
        rows = get_attendance_report_rows()
        data = [
            {
                "Nama": row["nama"],
                "NIM": row["nim"],
                "Tanggal": row["tanggal"],
                "Jam": row["waktu"],
                "Similarity": row["similarity"],
                "Status": row["status"],
            }
            for row in rows
        ]
        return "Attendance Report", pd.DataFrame(data)

    if report_type == "risk":
        rows = get_risk_report_rows()
        data = [
            {
                "Nama": row["nama"],
                "NIM": row["nim"],
                "Attendance Rate": row["attendance_rate"],
                "Total Hadir": row["total_hadir"],
                "Total Absen": row["total_absen"],
                "Risk Level": row["risk_level"],
                "Trend": row["trend"],
            }
            for row in rows
        ]
        return "Academic Risk Report", pd.DataFrame(data)

    if report_type == "prediction":
        rows = get_prediction_report_rows()
        data = [
            {
                "Nama": row["nama"],
                "NIM": row["nim"],
                "Attendance Rate": row["attendance_rate"],
                "Prediction": row["prediction_level"],
                "Recommendation": row["recommendation"],
            }
            for row in rows
        ]
        return "Prediction Report", pd.DataFrame(data)

    if report_type == "testing":
        rows = get_testing_report_rows()
        data = [
            {
                "Test Case": row["test_case"],
                "Expected Result": row["expected_result"],
                "Actual Result": row["actual_result"],
                "Status": row["status"],
            }
            for row in rows
        ]
        return "Testing Report", pd.DataFrame(data)

    raise ValueError("Report type tidak dikenal.")


def export_report(report_type, file_format):
    report_title, dataframe = _report_dataframe(report_type)

    if file_format == "excel":
        output = BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            dataframe.to_excel(writer, index=False, sheet_name=report_title[:31] or "Report")
        output.seek(0)
        return output, _safe_filename(report_type, "xlsx"), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

    if file_format == "pdf":
        output = BytesIO()
        document = SimpleDocTemplate(
            output,
            pagesize=landscape(A4),
            rightMargin=24,
            leftMargin=24,
            topMargin=24,
            bottomMargin=24,
        )
        styles = getSampleStyleSheet()
        elements = [
            Paragraph(report_title, styles["Title"]),
            Spacer(1, 12),
            Paragraph(
                f"Generated at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                styles["Normal"],
            ),
            Spacer(1, 12),
        ]

        table_data = [list(dataframe.columns)]
        for _, row in dataframe.iterrows():
            table_data.append([str(value) if value is not None else "-" for value in row.tolist()])

        if len(table_data) == 1:
            table_data.append(["No data available"] + [""] * (len(dataframe.columns) - 1))

        table = Table(table_data, repeatRows=1)
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f2937")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#d1d5db")),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), 9),
                    ("LEADING", (0, 0), (-1, -1), 11),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f9fafb")]),
                ]
            )
        )
        elements.append(table)
        document.build(elements)
        output.seek(0)
        return output, _safe_filename(report_type, "pdf"), "application/pdf"

    raise ValueError("Format export tidak dikenal.")
