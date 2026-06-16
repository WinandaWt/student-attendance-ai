import os

import mysql.connector


def get_connection():
    return mysql.connector.connect(
        host=os.environ.get("MYSQL_HOST", "172.0.0.1"),
        port=int(os.environ.get("MYSQL_PORT", 3306)),
        user=os.environ.get("MYSQL_USER", "root"),
        password=os.environ.get("MYSQL_PASSWORD", "root"),
        database=os.environ.get("MYSQL_DATABASE", "attendance_ai"),
    )
