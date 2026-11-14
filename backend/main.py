from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
import pdfplumber, io, re, time, uuid, os
from collections import deque
from pathlib import Path
from fastapi import Request
from fastapi.staticfiles import StaticFiles
from typing import Optional
from fastapi import HTTPException
import db

BASE_DIR = Path(__file__).resolve().parent
FRONTEND_DIR = BASE_DIR.parent / "frontend"

app = FastAPI(title="ResuNova")

# Allowed browser origins. On a hosted site the page and the API share one address, so CORS is not needed;
# the defaults below only let the local files (file://) and localhost talk to a local server.
ORIGINS = [o.strip() for o in os.getenv("ALLOWED_ORIGINS", "http://127.0.0.1:8000,http://localhost:8000,null").split(",") if o.strip()]
app.add_middleware(CORSMiddleware, allow_origins=ORIGINS, allow_methods=["GET", "POST"], allow_headers=["*"])

@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    return response

@app.get("/api/health")
def health():
    return {"status": "ok"}

# ---------- simple in-memory rate limit (per client IP; nothing is written to disk) ----------
RATE_LIMIT = int(os.getenv("RATE_LIMIT_PER_10MIN", "20"))
HITS = {}

def client_ip(request):
    fwd = request.headers.get("x-forwarded-for", "")
    return fwd.split(",")[0].strip() or (request.client.host if request.client else "unknown")

def check_rate(ip):
    now = time.time()
    q = HITS.setdefault(ip, deque())
    while q and now - q[0] > 600:
        q.popleft()
    if len(q) >= RATE_LIMIT:
        raise HTTPException(429, "Too many requests. Please wait a few minutes and try again.")
    q.append(now)
    if len(HITS) > 5000:
        for k in [k for k, v in HITS.items() if not v or now - v[-1] > 600]:
            HITS.pop(k, None)

# ---------- 1. Skills dictionary ----------
# ---------- 1. Knowledge now comes from the SQLite database (see db.py and seed_data.py) ----------
db.init_db()
KNOW = db.load_knowledge()
SKILLS = KNOW["skills"]          # skill name -> list of aliases
ROLE_SKILLS = KNOW["roles"]      # role -> {"must": [...], "imp": [...]}
ROADMAP = KNOW["roadmap"]        # skill -> (what to learn, mini project, days)
PREREQ = KNOW["prereq"]          # skill -> [prerequisite skills]

def has_word(text, word):
    # whole-word match: "java" will NOT match inside "javascript"
    pattern = r"(?<![a-z0-9+#.])" + re.escape(word) + r"(?![a-z0-9+#])"
    return re.search(pattern, text) is not None

def find_skills(text):
    t = text.lower()
    return [name for name, aliases in SKILLS.items()
            if any(has_word(t, a) for a in aliases)]

# ---------- 2. Resume checks ----------
WEAK_STARTS = ["made", "worked on", "did", "helped", "used", "participated", "responsible for"]
SECTIONS = {"Education": ["education"], "Skills": ["skills"], "Projects": ["projects", "project"],
            "Experience": ["experience", "internship"], "Achievements": ["achievements"],
            "Certifications": ["certifications", "certificates"]}

def get_bullets(text):
    return [re.sub(r"^[\-\u2022*\u25aa\u25cf\s]+", "", l.strip())
            for l in text.split("\n") if re.match(r"^\s*[\-\u2022*\u25aa\u25cf]", l)]

def check_resume(text):
    t = text.lower()
    lacking = []
    if not re.search(r"github\.com/\S+", t) and not re.search(r"linkedin\.com/in/\S+", t):
        lacking.append(["No GitHub or LinkedIn link found", "bad"])
    if not any(re.search(r"^\W*" + w + r"\b", t, re.M) for w in ["summary", "objective", "profile", "about me"]):
        lacking.append(["No professional summary at the top", "warn"])
    if not re.search(r"[\w.+-]+@[\w-]+\.[\w.]+", t):
        lacking.append(["No email address found", "bad"])
    if not re.search(r"\d[\d\s-]{8,}", t):
        lacking.append(["No phone number found", "warn"])
    for name, keys in SECTIONS.items():
        if name in ("Experience", "Certifications"):
            continue
        # a heading is a short line containing the keyword, e.g. "TECHNICAL SKILLS"
        found = any(len(l.split()) <= 4 and any(k in l for k in keys) for l in t.split("\n"))
        if not found:
            lacking.append([f"No '{name}' section found", "warn"])
    bullets = get_bullets(text)
    weak = [b for b in bullets if any(b.lower().startswith(w) for w in WEAK_STARTS)]
    with_numbers = [b for b in bullets if re.search(r"\d", b)]
    if bullets and len(with_numbers) < max(1, len(bullets) // 3):
        lacking.append(["Most bullet points have no numbers (users, speed, accuracy)", "bad"])
    if weak:
        lacking.append([f"{len(weak)} bullet(s) start with weak verbs like 'made' or 'worked on'", "warn"])
    if len(text.split()) < 120:
        lacking.append(["Resume looks very short (under 120 words)", "warn"])
    return lacking, weak[:3]

# ---------- Reading resumes (PDF and DOCX) ----------
MAX_BYTES = 5 * 1024 * 1024

def _read_pdf(data):
    text, pages, tables, images = "", 0, 0, 0
    with pdfplumber.open(io.BytesIO(data)) as pdf:
        for p in pdf.pages:
            pages += 1
            text += (p.extract_text() or "") + "\n"
            tables += len(p.find_tables())
            images += len(p.images)
    return text, (pages, tables, images)

def _read_docx(data):
    from docx import Document
    doc = Document(io.BytesIO(data))
    lines = []
    for p in doc.paragraphs:
        t = p.text.strip()
        if not t:
            continue
        style = (p.style.name if p.style is not None else "").lower()
        if "list" in style and not re.match(r"^[\-\u2022*]", t):
            t = "- " + t
        lines.append(t)
    for table in doc.tables:
        for row in table.rows:
            lines.append(" ".join(c.text.strip() for c in row.cells))
    return "\n".join(lines) + "\n", (1, len(doc.tables), len(doc.inline_shapes))

def read_resume(data):
    """Returns (text, (pages, tables, images)). Raises ValueError with a friendly message."""
    if not data:
        raise ValueError("The file is empty.")
    if len(data) > MAX_BYTES:
        raise ValueError("The file is larger than 5 MB.")
    try:
        if data[:4] == b"%PDF":
            return _read_pdf(data)
        if data[:2] == b"PK":
            return _read_docx(data)
    except Exception:
        raise ValueError("Could not read this file. It may be damaged or password-protected.")
    raise ValueError("Unsupported file type. Please upload a PDF or DOCX resume.")

ALL_SECTIONS = {**SECTIONS, "Summary": ["summary", "objective", "profile", "about me"]}

def detect_sections(text):
    t = text.lower()
    out = {}
    for name, keys in ALL_SECTIONS.items():
        if name == "Summary":
            out[name] = re.search(r"^\W*(summary|objective|profile|about me)\b", t, re.M) is not None
        else:
            out[name] = any(len(l.split()) <= 4 and any(k in l for k in keys) for l in t.split("\n"))
    return out

# ---------- 3. Role profiles come from the database ----------
WEIGHTS = [20, 25, 20, 20, 15]

def clip(x):
    return max(0, min(100, round(x)))

def score_resume(text, skills, role, meta):
    t = text.lower()
    pages, tables, images = meta
    bullets = get_bullets(text)
    weak = [b for b in bullets if any(b.lower().startswith(w) for w in WEAK_STARTS)]
    nums = [b for b in bullets if re.search(r"\d", b)]
    def has_section(keys):
        return any(len(l.split()) <= 4 and any(k in l for k in keys) for l in t.split("\n"))
    reasons = [[], [], [], [], []]

    # 1. Structure and completeness
    st = 100
    for name in ("Education", "Skills", "Projects"):
        if not has_section(SECTIONS[name]): st -= 15; reasons[0].append(f"-15: no {name} section")
    if not re.search(r"[\w.+-]+@[\w-]+\.[\w.]+", t): st -= 15; reasons[0].append("-15: no email")
    if not re.search(r"\d[\d\s-]{8,}", t): st -= 10; reasons[0].append("-10: no phone number")
    if not re.search(r"github\.com/\S+|linkedin\.com/in/\S+", t): st -= 15; reasons[0].append("-15: no GitHub/LinkedIn link")
    if not any(re.search(r"^\W*" + w + r"\b", t, re.M) for w in ["summary", "objective", "profile", "about me"]):
        st -= 10; reasons[0].append("-10: no professional summary")
    if len(text.split()) < 120: st -= 15; reasons[0].append("-15: resume is very short")

    # 2. Content quality
    if not bullets:
        ct = 40; reasons[1].append("-60: no bullet points found")
    else:
        pn = len(nums) / len(bullets); pw = len(weak) / len(bullets)
        ct = 100 - (1 - pn) * 45 - pw * 35
        if pn < 1: reasons[1].append(f"-{round((1-pn)*45)}: only {len(nums)} of {len(bullets)} bullets have numbers")
        if weak: reasons[1].append(f"-{round(pw*35)}: {len(weak)} of {len(bullets)} bullets start with weak verbs")

    # 3. ATS compatibility
    at = 100
    if tables: at -= 20; reasons[2].append("-20: tables found (ATS may misread them)")
    if images: at -= 10; reasons[2].append("-10: images found")
    if pages > 2: at -= 15; reasons[2].append("-15: more than 2 pages")
    if len(text) < 300: at -= 40; reasons[2].append("-40: almost no text extracted (scanned PDF?)")
    if sum(has_section(k) for k in SECTIONS.values()) < 3: at -= 15; reasons[2].append("-15: fewer than 3 standard headings")

    # 4. Technical depth
    in_bullets = find_skills(" ".join(bullets))
    td = min(100, len(skills) * 9) * 0.6 + min(100, len(in_bullets) * 20) * 0.4
    reasons[3].append(f"{len(skills)} skills found, {len(in_bullets)} used inside project/experience bullets")
    if len(skills) < 11: reasons[3].append("more skills (up to 11) raise this score")

    # 5. Role alignment
    prof = ROLE_SKILLS.get(role, ROLE_SKILLS["Backend Developer"])
    mu = [s for s in prof["must"] if s in skills]; mi = [s for s in prof["imp"] if s in skills]
    ra = 100 * (0.7 * len(mu) / len(prof["must"]) + 0.3 * len(mi) / len(prof["imp"]))
    reasons[4].append(f"{len(mu)} of {len(prof['must'])} must-have skills for {role}")
    missing = [s for s in prof["must"] if s not in skills]
    if missing: reasons[4].append("missing: " + ", ".join(missing))

    cats = [clip(st), clip(ct), clip(at), clip(td), clip(ra)]
    total = round(sum(c * w for c, w in zip(cats, WEIGHTS)) / 100)
    return cats, reasons, total


# ---------- 4. Learning roadmap (ordered by the skill_prerequisites table) ----------
def build_roadmap(skills, role):
    prof = ROLE_SKILLS.get(role, ROLE_SKILLS["Backend Developer"])
    order = {s: i for i, s in enumerate(prof["must"] + prof["imp"])}
    prio = {**{s: "Medium" for s in prof["imp"]}, **{s: "High" for s in prof["must"]}}
    need = {s for s in prio if s not in skills and s in ROADMAP}
    stack = list(need)
    while stack:                                   # also add missing prerequisites (transitively)
        for p in PREREQ.get(stack.pop(), []):
            if p not in skills and p in ROADMAP and p not in need:
                need.add(p); prio.setdefault(p, "Prerequisite"); stack.append(p)
    rank = {"High": 0, "Prerequisite": 0, "Medium": 1}
    remaining, out = set(need), []
    while remaining:                               # topological sort: prerequisites always come first
        ready = [s for s in remaining if not any(p in remaining for p in PREREQ.get(s, []))] or list(remaining)
        s = min(ready, key=lambda x: (rank[prio[x]], order.get(x, 99), x))
        remaining.discard(s)
        learn, proj, days = ROADMAP[s]
        out.append({"skill": s, "priority": prio[s], "learn": learn, "project": proj, "days": days,
                    "requires": [p for p in PREREQ.get(s, []) if p in need]})
    return out

# ---------- 5. Free rule-based bullet rewriter (no AI, no cost) ----------
VERB_MAP = [("worked on", "Developed"), ("responsible for", "Managed"), ("participated in", "Contributed to"),
            ("participated", "Contributed to"), ("helped", "Supported"), ("made", "Built"),
            ("did", "Completed"), ("used", "Applied")]
METRICS = [
    (["website", "web app", "app", "platform", "dashboard", "portal"], "used by [N] users"),
    (["api", "speed", "load time", "cach", "quer", "optimi"], "reducing [time/cost] by [X]%"),
    (["model", "classifier", "predict", "machine learning"], "reaching [X]% accuracy"),
    (["hackathon", "competition", "contest"], "among [N] teams"),
    (["team", "group", "club"], "with a team of [N]"),
]

def rewrite_bullet(b):
    s = b.strip().rstrip(".")
    low = s.lower()
    for old, new in VERB_MAP:
        if low.startswith(old + " "):
            if old.startswith("participated") and any(k in low for k in ("hackathon", "competition", "contest")):
                new = "Competed in"
            s = new + s[len(old):]
            break
    if not re.search(r"\d", s):
        for keys, tail in METRICS:
            if any(k in low for k in keys):
                s += ", " + tail
                break
        else:
            s += ", with [add a measurable result: users, time saved, accuracy]"
    return s[0].upper() + s[1:] + "."

def make_rewrites(text):
    bullets = get_bullets(text)
    weak = [b for b in bullets if any(b.lower().startswith(w) for w in WEAK_STARTS)]
    nonum = [b for b in bullets if not re.search(r"\d", b) and b not in weak]
    return [{"before": b, "after": rewrite_bullet(b)} for b in (weak + nonum)[:4]]

# ---------- 6. Pipeline and API endpoints ----------
UPLOADS = {}   # upload_id -> (time, file bytes, role). Memory only, deleted after analysis or after 10 minutes.

def purge_uploads():
    now = time.time()
    for k in [k for k, v in UPLOADS.items() if now - v[0] > 600]:
        UPLOADS.pop(k, None)

def run_pipeline(data, role):
    if role not in ROLE_SKILLS:
        raise ValueError("Unknown role. Choose one of: " + ", ".join(ROLE_SKILLS))
    text, meta = read_resume(data)
    skills = find_skills(text)
    lacking, weak = check_resume(text)
    cats, reasons, total = score_resume(text, skills, role, meta)
    return {"role": role, "characters": len(text), "skills": skills, "sections": detect_sections(text),
            "lacking": lacking, "weak_bullets": weak, "cats": cats, "reasons": reasons, "score": total,
            "roadmap": build_roadmap(skills, role), "rewrites": make_rewrites(text)}

@app.get("/api/roles")
def roles():
    return db.list_roles()

@app.post("/api/upload")
async def upload(request: Request, file: UploadFile = File(...), role: str = Form("Backend Developer")):
    check_rate(client_ip(request))
    data = await file.read(MAX_BYTES + 1)
    if role not in ROLE_SKILLS:
        raise HTTPException(400, "Unknown role. Choose one of: " + ", ".join(ROLE_SKILLS))
    if len(data) > MAX_BYTES:
        raise HTTPException(413, "The file is larger than 5 MB.")
    if data[:4] != b"%PDF" and data[:2] != b"PK":
        raise HTTPException(400, "Unsupported file type. Please upload a PDF or DOCX resume.")
    purge_uploads()
    uid = uuid.uuid4().hex[:12]
    UPLOADS[uid] = (time.time(), data, role)
    return {"upload_id": uid, "role": role, "filename": file.filename, "size_kb": round(len(data) / 1024)}

@app.post("/api/analyze")
async def analyze(request: Request, file: Optional[UploadFile] = File(None), role: Optional[str] = Form(None),
                  upload_id: Optional[str] = Form(None)):
    check_rate(client_ip(request))
    purge_uploads()
    if upload_id:
        item = UPLOADS.pop(upload_id, None)
        if not item:
            raise HTTPException(404, "Upload expired or not found. Please upload again.")
        data, role = item[1], role or item[2]
    elif file:
        data = await file.read(MAX_BYTES + 1)
    else:
        raise HTTPException(400, "Send a resume file or an upload_id.")
    try:
        report = run_pipeline(data, role or "Backend Developer")
    except ValueError as e:
        raise HTTPException(400, str(e))
    report["id"] = db.save_analysis(report["role"], report)
    return report

@app.get("/api/report/{analysis_id}")
def report(analysis_id: int):
    r = db.get_analysis(analysis_id)
    if not r:
        raise HTTPException(404, "Report not found.")
    return r

@app.get("/api/roadmap/{analysis_id}")
def roadmap(analysis_id: int):
    r = db.get_analysis(analysis_id)
    if not r:
        raise HTTPException(404, "Report not found.")
    return {"id": r["id"], "role": r["role"], "roadmap": r["roadmap"],
            "total_days": sum(x["days"] for x in r["roadmap"])}

# ---------- the website itself (must be registered last, so the API routes win) ----------
if FRONTEND_DIR.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")
