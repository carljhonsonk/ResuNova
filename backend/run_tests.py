"""ResuNova tests: performance, edge cases, section detection. Run:  python run_tests.py
Needs:  pip install reportlab python-docx   (reportlab is only used here, to make test files)"""
import io, os, time, statistics
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors
from PIL import Image
from docx import Document
import main

GOOD = ["Aarav Sharma", "aarav@example.com | 98XXXXXX00 | github.com/aarav-demo | linkedin.com/in/aarav-demo",
 "SUMMARY", "First-year CSE student building backend web apps with Python, Flask and SQL.",
 "EDUCATION", "B.Tech in Computer Science, Demo University (2025 - 2029)",
 "TECHNICAL SKILLS", "Python, C++, JavaScript, SQL, Flask, FastAPI, REST API, MySQL, PostgreSQL, Git, GitHub, Docker, Pandas",
 "PROJECTS", "Notes Platform",
 "- Built and deployed a Flask and MySQL web app used by 120 classmates.",
 "- Designed 6 REST API endpoints and cut page load time by 35% with SQL indexing.",
 "- Containerised the app with Docker and tracked changes in Git on GitHub.",
 "ACHIEVEMENTS", "- Solved 150 problems on LeetCode and ranked in the top 10 at the college hackathon.",
 "CERTIFICATIONS", "- Python for Everybody - online course certificate, 2026"]
WEAK = ["Aarav Sharma", "aarav@example.com | 98XXXXXX00 | Gurugram",
 "EDUCATION", "B.Tech in Computer Science, Demo University (2025 - 2029)",
 "TECHNICAL SKILLS", "Python, C++, JavaScript, HTML, CSS, Flask, MySQL, Git",
 "PROJECTS", "- Made a website using Flask and MySQL for sharing class notes.", "- Worked on login page and database tables.",
 "- Built a weather app using JavaScript, HTML and CSS.", "- Used an open API to show the temperature of cities.",
 "ACHIEVEMENTS", "- Solved 80 problems on LeetCode.", "- Participated in the college hackathon.",
 "CERTIFICATIONS", "- Python for Beginners - online course certificate"]

def pdf(lines, repeat=1):
    buf = io.BytesIO(); c = canvas.Canvas(buf, pagesize=A4); y = 800
    for _ in range(repeat):
        for l in lines:
            if y < 60: c.showPage(); y = 800
            c.drawString(50, y, l[:110]); y -= 16
    c.save(); return buf.getvalue()

def table_pdf():
    buf = io.BytesIO(); st = getSampleStyleSheet()
    rows = [[Paragraph(x, st["Normal"]) for x in ("EDUCATION", "TECHNICAL SKILLS")],
            [Paragraph("B.Tech CSE, Demo University", st["Normal"]), Paragraph("Python, Flask, SQL, Git, Docker", st["Normal"])],
            [Paragraph("PROJECTS", st["Normal"]), Paragraph("ACHIEVEMENTS", st["Normal"])],
            [Paragraph("- Built a Flask app used by 100 users", st["Normal"]), Paragraph("- Solved 150 LeetCode problems", st["Normal"])]]
    t = Table(rows, colWidths=[250, 250]); t.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 1, colors.black)]))
    SimpleDocTemplate(buf, pagesize=A4).build([t]); return buf.getvalue()

def image_pdf():
    img = Image.new("RGB", (600, 800), "white"); b = io.BytesIO(); img.save(b, "PNG"); b.seek(0)
    from reportlab.lib.utils import ImageReader
    buf = io.BytesIO(); c = canvas.Canvas(buf, pagesize=A4); c.drawImage(ImageReader(b), 0, 0, 595, 842); c.save()
    return buf.getvalue()

def docx_bytes():
    d = Document(); d.add_paragraph("Aarav Sharma")
    for l in GOOD[1:]:
        if l.startswith("- "): d.add_paragraph(l[2:], style="List Bullet")
        else: d.add_paragraph(l)
    b = io.BytesIO(); d.save(b); return b.getvalue()

def run(data, role="Backend Developer"):
    return main.run_pipeline(data, role)

results = []
def case(name, expectation, fn):
    try:
        ok, note = fn()
    except Exception as e:
        ok, note = False, f"crashed: {type(e).__name__}: {e}"
    results.append((name, expectation, "PASS" if ok else "FAIL", note))

def expect_error(data):
    try: run(data); return False, "no error raised"
    except ValueError as e: return True, f"clean error: {e}"

def c_short():
    r = run(pdf(["Rahul", "CSE student", "Python, Flask"]))
    return any("short" in x[0] for x in r["lacking"]) and 0 <= r["score"] <= 100, f"score {r['score']}"
def c_long():
    t = time.time(); r = run(pdf(GOOD, repeat=8)); dt = time.time() - t
    return any("2 pages" in x for x in r["reasons"][2]) and dt < 5, f"score {r['score']}, {dt:.2f}s"
def c_table():
    r = run(table_pdf()); return any("table" in x for x in r["reasons"][2]), f"score {r['score']}"
def c_image():
    r = run(image_pdf()); return any("no text" in x or "almost no text" in x for x in r["reasons"][2]), f"score {r['score']}"
def c_docx():
    r = run(docx_bytes()); return len(r["skills"]) >= 8, f"{len(r['skills'])} skills, score {r['score']}"

case("Very short resume (3 lines)", "scores it and flags 'very short'", c_short)
case("Very long resume (6+ pages)", "flags >2 pages, under 5 s", c_long)
case("Table / two-column layout", "flags tables for ATS", c_table)
case("Scanned / image-only PDF", "no crash, flags missing text", c_image)
case("DOCX resume", "reads it, finds >= 8 skills", c_docx)
case("Plain text renamed .pdf", "clean error, no crash", lambda: expect_error(b"just some plain text, not a resume"))
case("Corrupted PDF", "clean error, no crash", lambda: expect_error(b"%PDF-1.4 this is garbage"))
case("Empty file", "clean error, no crash", lambda: expect_error(b""))

print("\nEDGE CASES")
print(f"{'Case':32} {'Expected':36} {'Result':6} Note")
for r in results: print(f"{r[0]:32} {r[1]:36} {r[2]:6} {r[3]}")
print(f"\n{sum(r[2]=='PASS' for r in results)} of {len(results)} edge cases passed")

good = pdf(GOOD); times = []
run(good)
for _ in range(10):
    t = time.time(); run(good); times.append(time.time() - t)
print(f"\nPERFORMANCE (10 runs, 1-page PDF): average {statistics.mean(times):.2f} s, slowest {max(times):.2f} s per resume")

MARKS = {"GOOD": (good, {"Education": 1, "Skills": 1, "Projects": 1, "Experience": 0, "Achievements": 1, "Certifications": 1, "Summary": 1}),
         "WEAK": (pdf(WEAK), {"Education": 1, "Skills": 1, "Projects": 1, "Experience": 0, "Achievements": 1, "Certifications": 1, "Summary": 0})}
ok = tot = 0
for name, (data, marks) in MARKS.items():
    found = main.detect_sections(main.read_resume(data)[0])
    for k, v in marks.items():
        tot += 1; ok += int(found[k]) == v
        if int(found[k]) != v: print(f"  section mismatch in {name}: {k} expected {v}")
print(f"\nSECTION DETECTION: {ok} of {tot} manual marks matched = {100*ok/tot:.0f}% (tiny sample: 2 resumes)")

# ---- rate limiter ----
from fastapi import HTTPException
blocked = 0
for _ in range(main.RATE_LIMIT + 5):
    try: main.check_rate("203.0.113.9")
    except HTTPException as e: blocked += int(e.status_code == 429)
rate_ok = blocked == 5
print(f"\nRATE LIMIT: {blocked} of 5 extra requests blocked -> {'PASS' if rate_ok else 'FAIL'}")

# ---- API ----
api_ok = True
try:
    from fastapi.testclient import TestClient
    c = TestClient(main.app); checks = []
    checks.append(("GET /api/health", c.get("/api/health").json() == {"status": "ok"}))
    checks.append(("GET /api/roles returns 4 roles", len(c.get("/api/roles").json()) == 4))
    checks.append(("GET / serves the web page", "ResuNova" in c.get("/").text))
    up = c.post("/api/upload", files={"file": ("a.pdf", good)}, data={"role": "Backend Developer"}).json()
    an = c.post("/api/analyze", data={"upload_id": up.get("upload_id", "")}).json()
    checks.append(("upload then analyze returns a score", 0 <= an.get("score", -1) <= 100))
    rep_ = c.get(f"/api/report/{an.get('id', 0)}")
    checks.append(("GET /api/report/{id}", rep_.status_code == 200))
    checks.append(("resume sentences are not stored in the report", "rewrites" not in rep_.json()))
    checks.append(("unsupported file type returns 400", c.post("/api/analyze", files={"file": ("a.txt", b"hello")}, data={"role": "Backend Developer"}).status_code == 400))
    print("\nAPI TESTS")
    for n, passed in checks:
        print(f"  {'PASS' if passed else 'FAIL'}  {n}"); api_ok = api_ok and passed
except ImportError:
    print("\nAPI TESTS skipped (pip install httpx to run them)")

import sys
failed = sum(x[2] != "PASS" for x in results) + (not rate_ok) + (not api_ok) + (ok != tot)
print("\nALL TESTS PASSED" if not failed else f"\n{failed} CHECK(S) FAILED")
sys.exit(1 if failed else 0)
