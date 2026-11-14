import sqlite3, json, os
from pathlib import Path
import seed_data

DB_PATH = Path(os.getenv("RESUNOVA_DB", str(Path(__file__).parent / "resunova.db")))

SCHEMA = """
CREATE TABLE IF NOT EXISTS skills(
    id INTEGER PRIMARY KEY, name TEXT UNIQUE, category TEXT, aliases TEXT,
    learn TEXT, project TEXT, days INTEGER);
CREATE TABLE IF NOT EXISTS roles(
    id INTEGER PRIMARY KEY, name TEXT UNIQUE, description TEXT);
CREATE TABLE IF NOT EXISTS role_skills(
    role_id INTEGER, skill_id INTEGER, importance REAL, frequency REAL, position INTEGER,
    PRIMARY KEY (role_id, skill_id));
CREATE TABLE IF NOT EXISTS skill_cooccurrence(
    skill_a INTEGER, skill_b INTEGER, support REAL, confidence REAL);
CREATE TABLE IF NOT EXISTS skill_prerequisites(
    skill_id INTEGER, prerequisite_id INTEGER, PRIMARY KEY (skill_id, prerequisite_id));
CREATE TABLE IF NOT EXISTS analyses(
    id INTEGER PRIMARY KEY AUTOINCREMENT, role TEXT, score INTEGER, report_json TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP);
"""

def connect():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con

def init_db():
    con = connect()
    con.executescript(SCHEMA)
    if con.execute("SELECT COUNT(*) FROM skills").fetchone()[0] == 0:
        seed(con)
    con.commit()
    con.close()

def seed(con):
    ids = {}
    for name, cat, aliases, learn, project, days in seed_data.SKILLS:
        cur = con.execute("INSERT INTO skills(name,category,aliases,learn,project,days) VALUES (?,?,?,?,?,?)",
                          (name, cat, "|".join(aliases), learn, project, days))
        ids[name] = cur.lastrowid
    for rname, (desc, must, imp) in seed_data.ROLES.items():
        rid = con.execute("INSERT INTO roles(name,description) VALUES (?,?)", (rname, desc)).lastrowid
        for pos, sk in enumerate(must + imp):
            # importance: 1.0 = must-have, 0.5 = important. frequency stays empty until job data is mined.
            con.execute("INSERT INTO role_skills VALUES (?,?,?,?,?)",
                        (rid, ids[sk], 1.0 if sk in must else 0.5, None, pos))
    for skill, pre in seed_data.PREREQS:
        con.execute("INSERT INTO skill_prerequisites VALUES (?,?)", (ids[skill], ids[pre]))

def load_knowledge():
    con = connect()
    skills, roadmap, prereq, roles = {}, {}, {}, {}
    for r in con.execute("SELECT * FROM skills ORDER BY id"):
        skills[r["name"]] = r["aliases"].split("|")
        if r["learn"]:
            roadmap[r["name"]] = (r["learn"], r["project"], r["days"])
    for r in con.execute("""SELECT s.name AS skill, p.name AS pre FROM skill_prerequisites sp
                            JOIN skills s ON s.id = sp.skill_id JOIN skills p ON p.id = sp.prerequisite_id"""):
        prereq.setdefault(r["skill"], []).append(r["pre"])
    for r in con.execute("SELECT * FROM roles ORDER BY id"):
        rows = con.execute("""SELECT s.name, rs.importance FROM role_skills rs JOIN skills s ON s.id = rs.skill_id
                              WHERE rs.role_id = ? ORDER BY rs.position""", (r["id"],)).fetchall()
        roles[r["name"]] = {"must": [x["name"] for x in rows if x["importance"] >= 1.0],
                            "imp": [x["name"] for x in rows if x["importance"] < 1.0],
                            "description": r["description"]}
    con.close()
    return {"skills": skills, "roadmap": roadmap, "prereq": prereq, "roles": roles}

def list_roles():
    k = load_knowledge()["roles"]
    return [{"name": n, "description": v["description"], "must": v["must"], "important": v["imp"]} for n, v in k.items()]

def save_analysis(role, report):
    # the resume text and the bullets taken from it are NOT saved, only the derived results
    safe = {k: v for k, v in report.items() if k not in ("rewrites", "weak_bullets", "id")}
    con = connect()
    cur = con.execute("INSERT INTO analyses(role, score, report_json) VALUES (?,?,?)",
                      (role, report["score"], json.dumps(safe)))
    con.commit()
    new_id = cur.lastrowid
    con.close()
    return new_id

def get_analysis(analysis_id):
    con = connect()
    row = con.execute("SELECT * FROM analyses WHERE id = ?", (analysis_id,)).fetchone()
    con.close()
    if not row:
        return None
    report = json.loads(row["report_json"])
    report["id"] = row["id"]
    report["created_at"] = row["created_at"]
    return report
