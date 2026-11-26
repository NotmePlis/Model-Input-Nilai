"""Tugas Minggu 9-10: input nilai, IPK, transkrip, dan audit."""
import io
import os
import secrets
import sqlite3
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from functools import wraps
from html import escape

from flask import Flask, abort, flash, g, redirect, render_template, request, send_file, session, url_for
from jinja2 import DictLoader
from werkzeug.security import check_password_hash, generate_password_hash

app = Flask(__name__)
os.makedirs(app.instance_path, exist_ok=True)
key_path = os.path.join(app.instance_path, "secret.key")
if not os.path.exists(key_path):
    with open(key_path, "w") as f:
        f.write(secrets.token_hex(32))
with open(key_path) as f:
    app.secret_key = os.environ.get("SECRET_KEY") or f.read().strip()
app.config.update(
    DATABASE=os.path.join(app.instance_path, "nilai.db"),
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    MAX_CONTENT_LENGTH=1024 * 1024,
)

POINTS = {"A": 4.0, "B": 3.0, "C": 2.0, "D": 1.0, "E": 0.0}
# Modul menyebut minimal D. Dengan skala di atas, D bernilai 1.0.
MIN_PASSING_POINTS = 1.0

SCHEMA = """
PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY, name TEXT NOT NULL,
    password TEXT NOT NULL, role TEXT NOT NULL CHECK(role IN ('dosen','mahasiswa'))
);
CREATE TABLE IF NOT EXISTS students (
    nim TEXT PRIMARY KEY REFERENCES users(id),
    program TEXT NOT NULL, cohort INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS courses (
    code TEXT PRIMARY KEY, name TEXT NOT NULL,
    sks INTEGER NOT NULL CHECK(sks > 0),
    lecturer TEXT NOT NULL REFERENCES users(id)
);
CREATE TABLE IF NOT EXISTS enrollments (
    id INTEGER PRIMARY KEY,
    nim TEXT NOT NULL REFERENCES students(nim),
    course_code TEXT NOT NULL REFERENCES courses(code),
    semester INTEGER NOT NULL CHECK(semester > 0),
    attendance_percent REAL NOT NULL CHECK(attendance_percent BETWEEN 0 AND 100),
    UNIQUE(nim, course_code, semester)
);
CREATE TABLE IF NOT EXISTS grades (
    id INTEGER PRIMARY KEY,
    enrollment_id INTEGER NOT NULL UNIQUE REFERENCES enrollments(id),
    letter TEXT NOT NULL CHECK(letter IN ('A','B','C','D','E'))
);
CREATE TABLE IF NOT EXISTS grade_history (
    id INTEGER PRIMARY KEY,
    grade_id INTEGER NOT NULL REFERENCES grades(id),
    old_value TEXT,
    new_value TEXT NOT NULL,
    changed_by TEXT NOT NULL REFERENCES users(id),
    changed_at TEXT NOT NULL,
    reason TEXT NOT NULL CHECK(length(trim(reason)) > 0)
);
-- Actor dan alasan disediakan koneksi dari akun yang sedang login.
CREATE TRIGGER IF NOT EXISTS grade_insert_context
BEFORE INSERT ON grades
WHEN current_actor() IS NULL OR length(trim(coalesce(audit_reason(),''))) = 0
BEGIN
    SELECT RAISE(ABORT, 'Actor dan alasan perubahan wajib diisi');
END;
CREATE TRIGGER IF NOT EXISTS grade_update_context
BEFORE UPDATE ON grades
WHEN current_actor() IS NULL OR length(trim(coalesce(audit_reason(),''))) = 0
BEGIN
    SELECT RAISE(ABORT, 'Actor dan alasan perubahan wajib diisi');
END;
CREATE TRIGGER IF NOT EXISTS grade_insert_audit
AFTER INSERT ON grades
BEGIN
    INSERT INTO grade_history(grade_id,old_value,new_value,changed_by,changed_at,reason)
    VALUES(NEW.id,NULL,NEW.letter,current_actor(),
           strftime('%Y-%m-%dT%H:%M:%fZ','now'),audit_reason());
END;
CREATE TRIGGER IF NOT EXISTS grade_update_audit
AFTER UPDATE ON grades
BEGIN
    INSERT INTO grade_history(grade_id,old_value,new_value,changed_by,changed_at,reason)
    VALUES(NEW.id,OLD.letter,NEW.letter,current_actor(),
           strftime('%Y-%m-%dT%H:%M:%fZ','now'),audit_reason());
END;
CREATE TRIGGER IF NOT EXISTS history_no_update
BEFORE UPDATE ON grade_history
BEGIN
    SELECT RAISE(ABORT, 'Riwayat tidak dapat diubah');
END;
CREATE TRIGGER IF NOT EXISTS history_no_delete
BEFORE DELETE ON grade_history
BEGIN
    SELECT RAISE(ABORT, 'Riwayat tidak dapat dihapus');
END;
CREATE VIEW IF NOT EXISTS student_grade_history AS
SELECT h.id,h.grade_id,e.nim,u.name student_name,e.course_code,
       c.name course_name,e.semester,h.old_value,h.new_value,
       h.changed_by,actor.name actor_name,h.changed_at,h.reason
FROM grade_history h
JOIN grades gr ON gr.id=h.grade_id
JOIN enrollments e ON e.id=gr.enrollment_id
JOIN users u ON u.id=e.nim
JOIN courses c ON c.code=e.course_code
JOIN users actor ON actor.id=h.changed_by;
"""


def db():
    if "db" not in g:
        g.db = sqlite3.connect(app.config["DATABASE"])
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys=ON")
        g.db.create_function("current_actor", 0, lambda: g.get("actor"))
        g.db.create_function("audit_reason", 0, lambda: g.get("reason"))
    return g.db


@app.teardown_appcontext
def close_db(error=None):
    conn = g.pop("db", None)
    if conn is not None:
        conn.close()


def init_db():
    db().executescript(SCHEMA)
    if db().execute("SELECT COUNT(*) FROM users").fetchone()[0]:
        return
    with db():
        for uid, name, role in [
            ("dosen", "Pak Andi", "dosen"), ("23001", "Adi", "mahasiswa"),
            ("23002", "Citra", "mahasiswa"), ("23003", "Deni", "mahasiswa"),
        ]:
            db().execute("INSERT INTO users VALUES(?,?,?,?)",
                         (uid, name, generate_password_hash("belajar123"), role))
        for nim in ["23001", "23002", "23003"]:
            db().execute("INSERT INTO students VALUES(?,?,?)", (nim, "Teknik Informatika", 2025))
        db().executemany("INSERT INTO courses VALUES(?,?,?,?)", [
            ("IF101", "Algoritma dan Pemrograman", 3, "dosen"),
            ("IF201", "Pemrograman Berorientasi Objek", 3, "dosen"),
            ("IF202", "Basis Data", 3, "dosen"),
            ("IF203", "Struktur Data", 2, "dosen"),
        ])
        db().executemany("INSERT INTO enrollments VALUES(?,?,?,?,?)", [
            (1, "23001", "IF101", 1, 100), (2, "23001", "IF101", 2, 100),
            (3, "23001", "IF201", 3, 80), (4, "23001", "IF202", 3, 75),
            (5, "23001", "IF203", 3, 74), (6, "23002", "IF201", 3, 90),
            (7, "23003", "IF201", 1, 100),
        ])
        g.actor, g.reason = "dosen", "Data contoh awal"
        db().executemany("INSERT INTO grades(enrollment_id,letter) VALUES(?,?)",
                         [(1, "C"), (2, "A"), (3, "B"), (6, "A")])


def best_passed(records):
    """Satu MK satu nilai terbaik; MK E atau belum dinilai tidak dipakai."""
    chosen = {}
    for row in records:
        letter = row["letter"]
        if letter is None:
            continue
        if letter not in POINTS or row["sks"] <= 0:
            raise ValueError("Nilai atau SKS tidak valid")
        if POINTS[letter] < MIN_PASSING_POINTS:
            continue
        previous = chosen.get(row["course_code"])
        if previous is None or POINTS[letter] >= POINTS[previous["letter"]]:
            chosen[row["course_code"]] = row
    return list(chosen.values())


def weighted_gpa(records, include_failed=False, best_only=True):
    for row in records:
        if row["letter"] is not None and (
            row["letter"] not in POINTS or row["sks"] <= 0
        ):
            raise ValueError("Nilai atau SKS tidak valid")
    selected = best_passed(records) if best_only else [
        row for row in records if row["letter"] is not None
        and (include_failed or POINTS[row["letter"]] >= MIN_PASSING_POINTS)
    ]
    total_sks = sum(row["sks"] for row in selected)
    if total_sks == 0:
        return 0.0
    total_mutu = sum(row["sks"] * POINTS[row["letter"]] for row in selected)
    return round(total_mutu / total_sks, 2)


def academic_records(nim):
    return [dict(row) for row in db().execute("""
        SELECT e.id,e.nim,e.course_code,c.name course_name,c.sks,
               e.semester,e.attendance_percent,gr.letter
        FROM enrollments e JOIN courses c ON c.code=e.course_code
        LEFT JOIN grades gr ON gr.enrollment_id=e.id
        WHERE e.nim=? ORDER BY e.semester,e.id
    """, (nim,))]


def calculate_ips(nim, semester):
    # IPS memakai seluruh nilai semester tersebut, termasuk E.
    rows = [r for r in academic_records(nim) if r["semester"] == semester]
    return weighted_gpa(rows, include_failed=True, best_only=False)


def calculate_ipk(nim):
    # IPK mengikuti aturan tugas: MK lulus dan nilai terbaik jika diulang.
    return weighted_gpa(academic_records(nim))


def predicate(ipk):
    if ipk >= 3.5:
        return "Cum Laude"
    if ipk >= 3.0:
        return "Sangat Memuaskan"
    if ipk >= 2.0:
        return "Memuaskan"
    return "Perlu Perbaikan"


def get_transcript(nim):
    student = db().execute("""
        SELECT s.*,u.name FROM students s JOIN users u ON u.id=s.nim WHERE s.nim=?
    """, (nim,)).fetchone()
    if not student:
        raise ValueError("Mahasiswa tidak ditemukan")
    records = academic_records(nim)
    selected = best_passed(records)
    counted = {r["id"] for r in selected}
    grouped = defaultdict(list)
    for row in records:
        row["mutu"] = None if row["letter"] is None else row["sks"] * POINTS[row["letter"]]
        row["counted"] = row["id"] in counted
        grouped[row["semester"]].append(row)
    ipk = calculate_ipk(nim)
    total_sks = sum(r["sks"] for r in selected)
    return {
        "student": dict(student),
        "semesters": [{"number": s, "rows": rows, "ips": calculate_ips(nim, s)}
                      for s, rows in sorted(grouped.items())],
        "total_sks": total_sks,
        "ipk": ipk,
        "predicate": predicate(ipk) if total_sks else "Belum ada nilai lulus",
    }


def login_required(role=None):
    def decorator(fn):
        @wraps(fn)
        def wrapped(*args, **kwargs):
            user = db().execute("SELECT * FROM users WHERE id=?", (session.get("uid"),)).fetchone()
            if not user:
                return redirect(url_for("login"))
            if role and user["role"] != role:
                abort(403)
            g.user = user
            return fn(*args, **kwargs)
        return wrapped
    return decorator


@app.before_request
def csrf_guard():
    session.setdefault("csrf", secrets.token_hex(24))
    if request.method == "POST":
        token = request.form.get("csrf", "")
        if not secrets.compare_digest(session["csrf"], token):
            abort(403, "Form tidak valid. Muat ulang halaman.")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        user = db().execute("SELECT * FROM users WHERE id=?", (request.form.get("uid"),)).fetchone()
        if user and check_password_hash(user["password"], request.form.get("password", "")):
            session.clear()
            session.update(uid=user["id"], csrf=secrets.token_hex(24))
            return redirect(url_for("index"))
        flash("ID atau password salah.")
    return render_template("login.html")


@app.post("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.get("/")
@login_required()
def index():
    rows = db().execute("""
        SELECT e.*,c.name course_name,c.sks,u.name student_name,gr.letter
        FROM enrollments e JOIN courses c ON c.code=e.course_code
        JOIN users u ON u.id=e.nim LEFT JOIN grades gr ON gr.enrollment_id=e.id
        WHERE c.lecturer=? OR e.nim=?
        ORDER BY e.nim,e.semester,e.id
    """, (g.user["id"], g.user["id"])).fetchall()
    nims = sorted({r["nim"] for r in rows})
    transcripts = [get_transcript(nim) for nim in nims]
    return render_template("index.html", rows=rows, summaries=transcripts, points=POINTS)


@app.post("/grades/<int:enrollment_id>")
@login_required("dosen")
def save_grade(enrollment_id):
    enrollment = db().execute("""
        SELECT e.* FROM enrollments e JOIN courses c ON c.code=e.course_code
        WHERE e.id=? AND c.lecturer=?
    """, (enrollment_id, g.user["id"])).fetchone()
    if not enrollment:
        abort(404)
    if enrollment["attendance_percent"] < 75:
        abort(400, "Nilai ditolak karena presensi kurang dari 75%.")
    letter = request.form.get("letter", "").strip().upper()
    reason = request.form.get("reason", "").strip()
    if letter not in POINTS:
        abort(400, "Nilai harus A, B, C, D, atau E.")
    if not reason:
        abort(400, "Alasan input atau perubahan wajib diisi.")
    existing = db().execute("SELECT * FROM grades WHERE enrollment_id=?", (enrollment_id,)).fetchone()
    g.actor, g.reason = g.user["id"], reason
    with db():
        if existing:
            if existing["letter"] == letter:
                flash("Nilai tidak berubah.")
                return redirect(url_for("index"))
            db().execute("UPDATE grades SET letter=? WHERE id=?", (letter, existing["id"]))
        else:
            db().execute("INSERT INTO grades(enrollment_id,letter) VALUES(?,?)",
                         (enrollment_id, letter))
    flash("Nilai disimpan. IPS dan IPK sudah dihitung ulang.")
    return redirect(url_for("index"))


def check_student_access(nim):
    if g.user["role"] == "mahasiswa":
        if g.user["id"] != nim:
            abort(403)
    elif not db().execute("""
        SELECT 1 FROM enrollments e JOIN courses c ON c.code=e.course_code
        WHERE e.nim=? AND c.lecturer=?
    """, (nim, g.user["id"])).fetchone():
        abort(403)


@app.get("/transcript/<nim>")
@login_required()
def transcript(nim):
    check_student_access(nim)
    try:
        data = get_transcript(nim)
    except ValueError:
        abort(404)
    return render_template("transcript.html", t=data)


def build_pdf(data):
    """PDF dan HTML menggunakan objek transkrip yang sama."""
    import reportlab
    from pathlib import Path
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

    # Font ikut tertanam dalam PDF; tidak bergantung pada font komputer pembaca.
    font_dir = Path(reportlab.__file__).parent / "fonts"
    if "TranscriptRegular" not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont("TranscriptRegular", str(font_dir / "Vera.ttf")))
        pdfmetrics.registerFont(TTFont("TranscriptBold", str(font_dir / "VeraBd.ttf")))
    output = io.BytesIO()
    styles = getSampleStyleSheet()
    styles["Heading3"].fontName = "TranscriptBold"
    normal = styles["Normal"]
    normal.fontName, normal.fontSize, normal.leading = "TranscriptRegular", 10, 14

    def text(value):
        return Paragraph(escape(str(value)), normal)

    def header(canvas, doc):
        w, h = A4
        canvas.saveState()
        canvas.setStrokeColor(colors.black)
        canvas.circle(19 * mm, h - 18 * mm, 6 * mm)
        canvas.setFont("TranscriptBold", 15)
        canvas.drawCentredString(19 * mm, h - 20 * mm, "U")
        canvas.setFont("TranscriptBold", 12)
        canvas.drawString(30 * mm, h - 16 * mm, "UNIVERSITAS CONTOH")
        canvas.setFont("TranscriptBold", 14)
        canvas.drawString(30 * mm, h - 23 * mm, "TRANSKRIP AKADEMIK")
        canvas.setFont("TranscriptRegular", 8)
        canvas.drawString(30 * mm, h - 28 * mm, "Dokumen demonstrasi untuk tugas perkuliahan")
        canvas.line(14 * mm, h - 32 * mm, w - 14 * mm, h - 32 * mm)
        canvas.drawString(14 * mm, 9 * mm, "Contoh transkrip akademik")
        canvas.drawRightString(w - 14 * mm, 9 * mm, "Halaman " + str(doc.page))
        canvas.restoreState()

    doc = SimpleDocTemplate(output, pagesize=A4,
        leftMargin=14 * mm, rightMargin=14 * mm,
        topMargin=38 * mm, bottomMargin=17 * mm)
    student = data["student"]
    story = [text("NIM: " + student["nim"]), text("Nama: " + student["name"]),
             text("Program Studi: " + student["program"]),
             text("Angkatan: " + str(student["cohort"])), Spacer(1, 5 * mm)]
    if not data["semesters"]:
        story.append(text("Belum ada mata kuliah."))
    for semester in data["semesters"]:
        story.append(Paragraph("Semester " + str(semester["number"]), styles["Heading3"]))
        rows = [["Kode MK", "Nama MK", "SKS", "Nilai", "Mutu"]]
        for row in semester["rows"]:
            rows.append([
                text(row["course_code"]),
                text(row["course_name"] + (" *" if row["counted"] else "")),
                str(row["sks"]), row["letter"] or "-",
                "-" if row["mutu"] is None else f'{row["mutu"]:.1f}',
            ])
        table = Table(rows, colWidths=[23*mm, 101*mm, 15*mm, 18*mm, 25*mm], repeatRows=1)
        table.setStyle(TableStyle([
            ("FONTNAME", (0, 0), (-1, 0), "TranscriptBold"),
            ("FONTNAME", (0, 1), (-1, -1), "TranscriptRegular"),
            ("FONTSIZE", (0, 0), (-1, -1), 10),
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eeeeee")),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#bbbbbb")),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("ALIGN", (2, 1), (-1, -1), "CENTER"),
            ("TOPPADDING", (0, 0), (-1, -1), 7),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ]))
        story.extend([table, text(f'IPS: {semester["ips"]:.2f}'), Spacer(1, 4*mm)])
    story.extend([
        text("* Menandai percobaan mata kuliah yang dihitung dalam IPK."),
        text("Total SKS lulus tanpa duplikasi: " + str(data["total_sks"])),
        text(f'IPK: {data["ipk"]:.2f}'),
        text("Predikat berdasarkan IPK: " + data["predicate"]),
        Spacer(1, 5*mm),
        text("Predikat ini belum menyatakan kelulusan; syarat lain belum diperiksa."),
        Spacer(1, 8*mm), text("Dekan"), Spacer(1, 16*mm),
        text("(........................................)"),
    ])
    doc.build(story, onFirstPage=header, onLaterPages=header)
    output.seek(0)
    return output


@app.get("/transcript/<nim>/pdf")
@login_required()
def transcript_pdf(nim):
    check_student_access(nim)
    return send_file(build_pdf(get_transcript(nim)),
        mimetype="application/pdf", as_attachment=True,
        download_name="transkrip_" + nim + ".pdf")


@app.get("/history/<nim>")
@login_required()
def history(nim):
    check_student_access(nim)
    rows = db().execute("""
        SELECT * FROM student_grade_history WHERE nim=? ORDER BY id DESC
    """, (nim,)).fetchall()
    return render_template("history.html", rows=rows, nim=nim)


@app.template_filter("wib")
def as_wib(value):
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return dt.astimezone(timezone(timedelta(hours=7))).strftime("%d-%m-%Y %H:%M:%S WIB")


TEMPLATES = {}
TEMPLATES["base.html"] = """
<!doctype html><html lang="id"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Modul Nilai dan Transkrip</title>
<style>
*{box-sizing:border-box}body{font:15px Arial,sans-serif;background:#f3f5f8;color:#19283a;margin:0}
main{max-width:1100px;margin:auto;padding:20px}section{background:white;padding:20px;border-radius:10px;margin:18px 0}
h1{font-size:25px}h2{font-size:20px}a{color:#2259ac}button,.button{display:inline-block;background:#245ac6;color:white;border:0;border-radius:5px;padding:10px 14px;text-decoration:none;margin:4px 0;cursor:pointer}
button:disabled{background:#677487;cursor:not-allowed}input,select{max-width:100%;padding:10px;border:1px solid #b9c4d1;border-radius:5px}
label{display:inline-block;margin:5px 10px 5px 0}small{color:#4a5d73}.scroll{overflow-x:auto}
table{width:100%;border-collapse:collapse}td,th{padding:11px 8px;border-bottom:1px solid #ddd;text-align:left;vertical-align:top}
form.inline{display:flex;flex-wrap:wrap;gap:6px;align-items:center}.message{background:#e7efff;padding:12px}
.danger{color:#a82020}.no-wrap{white-space:nowrap}
</style><main>
{% if g.user %}<p>{{g.user.name}} · {{g.user.role}}</p><form method="post" action="/logout"><input type="hidden" name="csrf" value="{{session.csrf}}"><button>Keluar</button></form>{% endif %}
{% for message in get_flashed_messages() %}<p class="message" role="status">{{message}}</p>{% endfor %}
{% block content %}{% endblock %}
</main></html>
"""
TEMPLATES["login.html"] = """
{% extends 'base.html' %}{% block content %}
<section><h1>Nilai dan Transkrip</h1><p>Masuk sebagai dosen atau mahasiswa.</p>
<form method="post"><input type="hidden" name="csrf" value="{{session.csrf}}">
<p><label>ID dosen atau NIM<br><input name="uid" required autocomplete="username"></label></p>
<p><label>Password<br><input name="password" type="password" required autocomplete="current-password"></label></p>
<button>Masuk</button></form>
<p><small>Akun demo: dosen / 23001 / 23002 / 23003. Password: belajar123</small></p></section>
{% endblock %}
"""
TEMPLATES["index.html"] = """
{% extends 'base.html' %}{% block content %}
<h1>Modul Nilai dan Transkrip</h1>
<section><h2>Ringkasan mahasiswa</h2><div class="scroll"><table>
<tr><th>Mahasiswa</th><th>SKS lulus</th><th>IPK</th><th>Predikat berdasarkan IPK</th><th>Dokumen</th></tr>
{% for t in summaries %}<tr><td>{{t.student.name}}<br><small>{{t.student.nim}}</small></td><td>{{t.total_sks}}</td><td>{{'%.2f'|format(t.ipk)}}</td><td>{{t.predicate}}</td><td>
<a href="/transcript/{{t.student.nim}}">Transkrip</a> ·
<a href="/transcript/{{t.student.nim}}/pdf">PDF</a> ·
<a href="/history/{{t.student.nim}}">Riwayat</a></td></tr>{% else %}<tr><td colspan="5">Belum ada data.</td></tr>{% endfor %}
</table></div></section>
<section><h2>Nilai mata kuliah</h2><p><small>Input nilai hanya diizinkan jika presensi minimal 75%. Persentase demo berasal dari data contoh, belum terhubung modul presensi QR.</small></p>
<div class="scroll"><table><tr><th>Mahasiswa</th><th>Mata kuliah</th><th>Semester</th><th>Presensi</th><th>Nilai</th>{% if g.user.role=='dosen' %}<th>Input atau edit</th>{% endif %}</tr>
{% for r in rows %}<tr><td>{{r.student_name}}<br><small>{{r.nim}}</small></td><td>{{r.course_code}}<br>{{r.course_name}}<br><small>{{r.sks}} SKS</small></td><td>{{r.semester}}</td><td class="{{'danger' if r.attendance_percent < 75 else ''}}">{{r.attendance_percent}}%</td><td>{{r.letter or 'Belum ada'}}</td>
{% if g.user.role=='dosen' %}<td><form class="inline" method="post" action="/grades/{{r.id}}">
<input type="hidden" name="csrf" value="{{session.csrf}}">
<select aria-label="Nilai {{r.course_code}} untuk {{r.nim}}" name="letter" required {% if r.attendance_percent < 75 %}disabled{% endif %}><option value="">Pilih nilai</option>{% for letter in points %}<option value="{{letter}}" {% if r.letter==letter %}selected{% endif %}>{{letter}}</option>{% endfor %}</select>
<input name="reason" aria-label="Alasan perubahan {{r.course_code}} untuk {{r.nim}}" placeholder="Alasan input atau koreksi" required {% if r.attendance_percent < 75 %}disabled{% endif %}>
<button {% if r.attendance_percent < 75 %}disabled{% endif %}>Simpan</button></form>{% if r.attendance_percent < 75 %}<small>Presensi belum memenuhi syarat.</small>{% endif %}</td>{% endif %}</tr>{% endfor %}
</table></div></section>{% endblock %}
"""
TEMPLATES["transcript.html"] = """
<!doctype html><html lang="id"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Transkrip {{t.student.nim}}</title>
<style>
@page{size:A4;margin:20mm}*{box-sizing:border-box}body{font:12pt 'Times New Roman',serif;color:#111;margin:0;background:#eee}
article{max-width:210mm;background:white;margin:20px auto;padding:20mm}header{display:flex;align-items:center;gap:16px;border-bottom:2px solid #111;padding-bottom:12px}
.logo{border:2px solid #111;border-radius:50%;width:55px;height:55px;display:flex;align-items:center;justify-content:center;font-size:30px;flex-shrink:0}h1{font-size:18pt;margin:6px 0}h2{font-size:13pt;margin-top:24px}
small{font-size:10pt}table{width:100%;border-collapse:collapse;margin-bottom:10px;table-layout:fixed}thead{display:table-header-group}tr{break-inside:avoid}
th,td{border:1px solid #bbb;padding:8px;overflow-wrap:anywhere}th{background:#eee}td:nth-child(n+3){text-align:center}dl{display:grid;grid-template-columns:115px 1fr;gap:6px}dd{margin:0}
.summary{margin-top:22px}.signature{margin-top:30px;text-align:right;break-inside:avoid}.navigation{font:14px Arial;margin-bottom:18px}a{color:#234f92}
@media(max-width:600px){article{margin:0;padding:16px}dl{grid-template-columns:95px 1fr}th,td{padding:5px}}
@media print{body{background:white}article{padding:0;margin:0;max-width:none}.navigation{display:none}}
</style><article><p class="navigation"><a href="/">Kembali</a> · <a href="/transcript/{{t.student.nim}}/pdf">Unduh PDF</a></p>
<header><div class="logo" role="img" aria-label="Logo kampus contoh">U</div><div><strong>UNIVERSITAS CONTOH</strong><h1>TRANSKRIP AKADEMIK</h1><small>Dokumen demonstrasi untuk tugas perkuliahan</small></div></header>
<dl><dt>NIM</dt><dd>{{t.student.nim}}</dd><dt>Nama</dt><dd>{{t.student.name}}</dd><dt>Program Studi</dt><dd>{{t.student.program}}</dd><dt>Angkatan</dt><dd>{{t.student.cohort}}</dd></dl>
{% for semester in t.semesters %}<h2>Semester {{semester.number}}</h2><table><colgroup><col style="width:15%"><col style="width:46%"><col style="width:11%"><col style="width:13%"><col style="width:15%"></colgroup>
<thead><tr><th>Kode MK</th><th>Nama MK</th><th>SKS</th><th>Nilai</th><th>Mutu</th></tr></thead><tbody>
{% for r in semester.rows %}<tr><td>{{r.course_code}}</td><td>{{r.course_name}}{{' *' if r.counted else ''}}</td><td>{{r.sks}}</td><td>{{r.letter or '-'}}</td><td>{{'%.1f'|format(r.mutu) if r.mutu is not none else '-'}}</td></tr>{% endfor %}
</tbody></table><p>IPS {{'%.2f'|format(semester.ips)}}</p>{% else %}<p>Belum ada mata kuliah.</p>{% endfor %}
<p><small>* Menandai percobaan mata kuliah yang dihitung dalam IPK. Seluruh percobaan tetap ditampilkan.</small></p>
<div class="summary"><p>Total SKS lulus tanpa duplikasi: <strong>{{t.total_sks}}</strong></p><p>IPK: <strong>{{'%.2f'|format(t.ipk)}}</strong></p><p>Predikat berdasarkan IPK: <strong>{{t.predicate}}</strong></p></div>
<p><small>Predikat ini belum menyatakan kelulusan; syarat lain belum diperiksa.</small></p>
<div class="signature">Dekan<br><br><br><br>(........................................)</div></article></html>
"""
TEMPLATES["history.html"] = """
{% extends 'base.html' %}{% block content %}<h1>Riwayat nilai {{nim}}</h1><p><a href="/">Kembali</a></p>
<section><div class="scroll"><table><tr><th>Mata kuliah</th><th>Semester</th><th>Nilai lama</th><th>Nilai baru</th><th>Diubah oleh</th><th>Waktu</th><th>Alasan</th></tr>
{% for r in rows %}<tr><td>{{r.course_code}}<br>{{r.course_name}}</td><td>{{r.semester}}</td><td>{{r.old_value or 'Input awal'}}</td><td>{{r.new_value}}</td><td>{{r.actor_name}}<br><small>{{r.changed_by}}</small></td><td>{{r.changed_at|wib}}</td><td>{{r.reason}}</td></tr>{% else %}<tr><td colspan="7">Belum ada riwayat.</td></tr>{% endfor %}
</table></div></section>{% endblock %}
"""
app.jinja_loader = DictLoader(TEMPLATES)

if __name__ == "__main__":
    with app.app_context():
        init_db()
    app.run(host="127.0.0.1", port=5000, debug=False)

