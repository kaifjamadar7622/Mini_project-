import os
import cv2
import numpy as np
import sqlite3
import datetime
import xml.etree.ElementTree as ET
from flask import Flask, request, jsonify, render_template, session, redirect, url_for
from deepface import DeepFace

app = Flask(__name__)
app.secret_key = 'supersecretkey'
app.config['UPLOAD_FOLDER'] = 'uploads'
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

def init_db():
    conn = sqlite3.connect('attendance.db')
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS employees (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name TEXT NOT NULL,
                        image_path TEXT,
                        fingerprint_template TEXT,
                        base_salary REAL DEFAULT 0
                    )''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS attendance (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        employee_id INTEGER,
                        check_in_time TEXT,
                        check_out_time TEXT,
                        work_hours REAL,
                        status TEXT,
                        FOREIGN KEY(employee_id) REFERENCES employees(id)
                    )''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS payroll (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        employee_id INTEGER,
                        start_date TEXT,
                        end_date TEXT,
                        total_hours REAL,
                        regular_hours REAL,
                        overtime_hours REAL,
                        base_pay REAL,
                        overtime_pay REAL,
                        total_pay REAL,
                        payment_date TEXT DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY(employee_id) REFERENCES employees(id)
                    )''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS settings (
                        key TEXT PRIMARY KEY,
                        value REAL
                    )''')

    default_settings = {
        'HOURLY_RATE': 37.50,
        'FULL_DAY_RATE': 300.00,
        'MIN_HOURS_FOR_FULL_DAY': 8,
        'OVERTIME_MULTIPLIER': 1.5
    }
    for key, value in default_settings.items():
        cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (key, value))

    conn.commit()
    conn.close()

def get_setting(key):
    conn = sqlite3.connect('attendance.db')
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM settings WHERE key = ?", (key,))
    result = cursor.fetchone()
    conn.close()
    return float(result[0]) if result else None

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/payroll')
def payroll():
    if 'user_id' not in session:
        return redirect(url_for('home'))
    return render_template('payroll.html')

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('home'))
    return render_template('dashboard.html', name=session['user_name'])

@app.route('/report')
def report():
    if 'user_id' not in session:
        return redirect(url_for('home'))
    return render_template('report.html')

@app.route('/register_employee', methods=['POST'])
def register_employee():
    name = request.form.get('name')
    image = request.files.get('biometric_image')

    if not image:
        return jsonify({'error': 'No image uploaded'}), 400

    image_path = os.path.join(app.config['UPLOAD_FOLDER'], f"{name}.jpg")
    image.save(image_path)

    conn = sqlite3.connect('attendance.db')
    cursor = conn.cursor()
    cursor.execute("INSERT INTO employees (name, image_path) VALUES (?, ?)", (name, image_path))
    conn.commit()
    conn.close()

    return jsonify({'message': 'Employee registered with face successfully'}), 201

@app.route('/register_fingerprint', methods=['POST'])
def register_fingerprint():
    name = request.form.get('name')
    pid_data = request.form.get('pidData')

    if not pid_data or not name:
        return jsonify({'error': 'Missing fingerprint or name'}), 400

    conn = sqlite3.connect('attendance.db')
    cursor = conn.cursor()
    cursor.execute("INSERT INTO employees (name, fingerprint_template) VALUES (?, ?)", (name, pid_data))
    conn.commit()
    conn.close()

    return jsonify({'message': 'Fingerprint registered successfully'}), 201

@app.route('/login', methods=['POST'])
def login():
    if 'face_image' not in request.files:
        return jsonify({'error': 'No face image provided'}), 400

    image = request.files['face_image']
    temp_image_path = "temp.jpg"
    image.save(temp_image_path)

    conn = sqlite3.connect('attendance.db')
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, image_path FROM employees WHERE image_path IS NOT NULL")
    employees = cursor.fetchall()
    conn.close()

    for emp_id, name, image_path in employees:
        try:
            result = DeepFace.verify(temp_image_path, image_path, model_name='Facenet')
            if result['verified']:
                session['user_id'] = emp_id
                session['user_name'] = name
                return jsonify({'message': 'Login successful', 'redirect': url_for('dashboard')}), 200
        except Exception as e:
            print(f"Face verification error: {e}")
            continue

    return jsonify({'error': 'Face not recognized'}), 400

@app.route('/login_fingerprint', methods=['POST'])
def login_fingerprint():
    pid_data = request.form.get('pidData')
    if not pid_data:
        return jsonify({'error': 'Missing fingerprint'}), 400

    root = ET.fromstring(pid_data)
    captured_data = root.findtext('Data')

    conn = sqlite3.connect('attendance.db')
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, fingerprint_template FROM employees WHERE fingerprint_template IS NOT NULL")
    rows = cursor.fetchall()
    conn.close()

    for emp_id, name, stored_xml in rows:
        try:
            stored_root = ET.fromstring(stored_xml)
            stored_data = stored_root.findtext('Data')
            if captured_data == stored_data:
                session['user_id'] = emp_id
                session['user_name'] = name
                return jsonify({'message': 'Login successful', 'redirect': url_for('dashboard')}), 200
        except Exception as e:
            print(f"Matching error: {e}")
            continue

    return jsonify({'error': 'Fingerprint not recognized'}), 400

@app.route('/check_in', methods=['POST'])
def check_in():
    if 'user_id' not in session:
        return jsonify({'error': 'Not logged in'}), 403

    user_id = session['user_id']
    time_now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    conn = sqlite3.connect('attendance.db')
    cursor = conn.cursor()
    cursor.execute("INSERT INTO attendance (employee_id, check_in_time, status) VALUES (?, ?, ?)", (user_id, time_now, 'Pending'))
    conn.commit()
    conn.close()

    return jsonify({'message': 'Check-in successful'}), 200

@app.route('/check_out', methods=['POST'])
def check_out():
    if 'user_id' not in session:
        return jsonify({'error': 'Not logged in'}), 403

    user_id = session['user_id']
    time_now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    conn = sqlite3.connect('attendance.db')
    cursor = conn.cursor()
    cursor.execute("SELECT id, check_in_time FROM attendance WHERE employee_id = ? AND check_out_time IS NULL", (user_id,))
    result = cursor.fetchone()

    if not result:
        conn.close()
        return jsonify({'error': 'No active check-in found'}), 400

    record_id, check_in_time = result
    check_in_datetime = datetime.datetime.strptime(check_in_time, "%Y-%m-%d %H:%M:%S")
    check_out_datetime = datetime.datetime.strptime(time_now, "%Y-%m-%d %H:%M:%S")
    work_hours = (check_out_datetime - check_in_datetime).total_seconds() / 3600

    status = ''
    if work_hours < 6:
        status = 'Absent'
    elif work_hours == 6:
        status = 'Half Time'
    elif work_hours == 8:
        status = 'Present'
    elif work_hours > 8:
        status = 'Full Time'

    cursor.execute("UPDATE attendance SET check_out_time = ?, work_hours = ?, status = ? WHERE id = ?", 
                  (time_now, work_hours, status, record_id))
    conn.commit()
    conn.close()

    return jsonify({'message': 'Check-out successful', 'work_hours': round(work_hours, 2), 'status': status}), 200

@app.route('/get_attendance_report', methods=['GET'])
def get_attendance_report():
    conn = sqlite3.connect('attendance.db')
    cursor = conn.cursor()
    cursor.execute("""
        SELECT employees.name, attendance.check_in_time, attendance.check_out_time, 
               attendance.work_hours, attendance.status 
        FROM attendance 
        JOIN employees ON attendance.employee_id = employees.id
    """)
    records = cursor.fetchall()
    conn.close()

    report = []
    for row in records:
        report.append({
            'name': row[0],
            'check_in_time': row[1],
            'check_out_time': row[2],
            'work_hours': row[3],
            'status': row[4]
        })
    return jsonify(report), 200

@app.route('/calculate_payroll', methods=['POST'])
def calculate_payroll():
    if 'user_id' not in session:
        return jsonify({'error': 'Not logged in'}), 403

    start_date = request.form.get('start_date')
    end_date = request.form.get('end_date')

    if not start_date or not end_date:
        return jsonify({'error': 'Missing date range'}), 400

    HOURLY_RATE = get_setting('HOURLY_RATE')
    MIN_HOURS_FOR_FULL_DAY = get_setting('MIN_HOURS_FOR_FULL_DAY')
    OVERTIME_MULTIPLIER = get_setting('OVERTIME_MULTIPLIER')
    OVERTIME_RATE = HOURLY_RATE * OVERTIME_MULTIPLIER

    conn = sqlite3.connect('attendance.db')
    cursor = conn.cursor()
    cursor.execute("SELECT id, name FROM employees")
    employees = cursor.fetchall()

    payroll_data = []
    for emp_id, name in employees:
        cursor.execute("""
            SELECT date(check_in_time) as work_date, 
                   SUM(work_hours) as daily_hours,
                   COUNT(*) as days_worked
            FROM attendance 
            WHERE employee_id = ? 
              AND date(check_in_time) BETWEEN ? AND ?
            GROUP BY date(check_in_time)
        """, (emp_id, start_date, end_date))

        records = cursor.fetchall()
        total_hours = 0
        regular_hours = 0
        overtime_hours = 0

        for work_date, daily_hours, days_worked in records:
            total_hours += daily_hours
            if daily_hours >= MIN_HOURS_FOR_FULL_DAY:
                regular_hours += MIN_HOURS_FOR_FULL_DAY
                overtime_hours += max(0, daily_hours - MIN_HOURS_FOR_FULL_DAY)
            else:
                regular_hours += daily_hours

        base_pay = regular_hours * HOURLY_RATE
        overtime_pay = overtime_hours * OVERTIME_RATE
        total_pay = base_pay + overtime_pay

        cursor.execute("""
            INSERT INTO payroll (employee_id, start_date, end_date, total_hours, 
                                regular_hours, overtime_hours, base_pay, 
                                overtime_pay, total_pay)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (emp_id, start_date, end_date, total_hours, regular_hours, 
              overtime_hours, base_pay, overtime_pay, total_pay))

        payroll_data.append({
            'employee_id': emp_id,
            'name': name,
            'total_hours': round(total_hours, 2),
            'regular_hours': round(regular_hours, 2),
            'overtime_hours': round(overtime_hours, 2),
            'base_pay': round(base_pay, 2),
            'overtime_pay': round(overtime_pay, 2),
            'total_pay': round(total_pay, 2)
        })

    conn.commit()
    conn.close()

    return jsonify(payroll_data), 200

@app.route('/update_settings', methods=['POST'])
def update_settings():
    if 'user_id' not in session:
        return jsonify({'error': 'Not logged in'}), 403

    settings = request.json
    conn = sqlite3.connect('attendance.db')
    cursor = conn.cursor()
    for key, value in settings.items():
        cursor.execute("UPDATE settings SET value = ? WHERE key = ?", (value, key))
    conn.commit()
    conn.close()

    return jsonify({'message': 'Settings updated successfully'}), 200

@app.route('/get_payroll_history', methods=['GET'])
def get_payroll_history():
    conn = sqlite3.connect('attendance.db')
    cursor = conn.cursor()
    cursor.execute("""
        SELECT p.id, e.name, p.start_date, p.end_date, p.total_pay, p.payment_date
        FROM payroll p
        JOIN employees e ON p.employee_id = e.id
        ORDER BY p.payment_date DESC
    """)
    payroll_history = []
    for row in cursor.fetchall():
        payroll_history.append({
            'id': row[0],
            'name': row[1],
            'start_date': row[2],
            'end_date': row[3],
            'total_pay': row[4],
            'payment_date': row[5]
        })
    conn.close()
    return jsonify(payroll_history), 200

@app.route('/logout', methods=['POST'])
def logout():
    session.clear()
    return jsonify({'message': 'Logged out successfully', 'redirect': url_for('home')}), 200

if __name__ == '__main__':
    init_db()
    app.run(debug=True)
