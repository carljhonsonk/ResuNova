# Knowledge that gets loaded into the SQLite database the first time the server starts.
# To change it: edit this file, delete resunova.db, and restart the server.

# (name, category, aliases, what to learn, mini project, days)
SKILLS = [
 ("Python", "Language", ["python"], "functions, lists, dicts, files, OOP basics", "command-line expense tracker", 10),
 ("Java", "Language", ["java"], None, None, None),
 ("JavaScript", "Language", ["javascript", "js"], "DOM, events, fetch, async/await", "weather app using a public API", 12),
 ("TypeScript", "Language", ["typescript"], "types, interfaces, generics basics", "convert one JavaScript project to TypeScript", 6),
 ("C++", "Language", ["c++"], None, None, None),
 ("C", "Language", ["c"], None, None, None),
 ("HTML", "Web", ["html"], "semantic tags, forms, accessibility basics", "personal portfolio page", 4),
 ("CSS", "Web", ["css"], "flexbox, grid, responsive design", "make the portfolio mobile friendly", 6),
 ("React", "Web", ["react", "reactjs", "react.js"], "components, props, state, hooks", "notes app with React", 12),
 ("Flask", "Backend", ["flask"], "routes, templates, forms, sessions", "mini blog with login", 6),
 ("FastAPI", "Backend", ["fastapi"], "path/query params, validation, auto docs", "rebuild your notes API in FastAPI", 5),
 ("Django", "Backend", ["django"], "models, views, admin, auth", "to-do app with user accounts", 10),
 ("Node.js", "Backend", ["node.js", "nodejs"], "modules, npm, Express basics", "small REST API with Express", 7),
 ("REST API", "Backend", ["rest api", "rest apis", "restful"], "HTTP methods, status codes, JSON, CRUD", "build a notes API with 5 endpoints", 7),
 ("SQL", "Database", ["sql"], "SELECT, JOIN, GROUP BY, indexes", "design a library database and write 15 queries", 7),
 ("MySQL", "Database", ["mysql"], "install MySQL, connect it from Python", "store a project's data in MySQL", 4),
 ("PostgreSQL", "Database", ["postgresql", "postgres"], "tables, constraints, indexes, EXPLAIN", "move one project from MySQL to PostgreSQL", 5),
 ("MongoDB", "Database", ["mongodb"], None, None, None),
 ("Git", "Tool", ["git"], "commit, branch, merge, push to GitHub", "put 2 old projects on GitHub with READMEs", 2),
 ("GitHub", "Tool", ["github"], "repos, README, pull requests", "pin 3 projects on your GitHub profile", 2),
 ("Docker", "DevOps", ["docker"], "images, containers, Dockerfile, compose", "containerise your Flask or FastAPI app", 4),
 ("Pandas", "Data", ["pandas"], "DataFrames, cleaning, groupby, merge", "clean and analyse a Kaggle CSV", 7),
 ("NumPy", "Data", ["numpy"], "arrays, broadcasting, vector maths", "implement linear regression with NumPy", 4),
 ("scikit-learn", "ML", ["scikit-learn", "sklearn"], "pipelines, classifiers, cross-validation", "spam classifier with a report", 8),
 ("PyTorch", "ML", ["pytorch"], "tensors, autograd, training loop", "digit classifier on MNIST", 10),
 ("Machine Learning", "ML", ["machine learning"], "train/test split, overfitting, metrics", "predict house prices end to end", 12),
 ("Excel", "Analytics", ["excel"], "formulas, pivot tables, charts", "analyse a sales sheet with a pivot dashboard", 5),
 ("Power BI", "Analytics", ["power bi", "powerbi"], "data model, DAX basics, dashboards", "build a 1-page sales dashboard", 7),
 ("Tableau", "Analytics", ["tableau"], "charts, filters, dashboards", "publish a public dashboard", 6),
]

# role: (description, must-have skills in learning order, important skills in learning order)
ROLES = {
 "Backend Developer": ("Builds server-side applications, APIs and databases",
    ["Python", "Git", "SQL", "REST API", "Docker"], ["PostgreSQL", "MySQL", "Flask", "FastAPI", "Django", "Node.js"]),
 "Frontend Developer": ("Builds the user interface of websites and web apps",
    ["HTML", "CSS", "JavaScript", "React", "Git"], ["TypeScript", "Node.js", "REST API", "GitHub"]),
 "Data Analyst": ("Cleans data, finds insights and builds dashboards",
    ["Python", "SQL", "Excel", "Pandas"], ["Power BI", "Tableau", "NumPy", "Machine Learning"]),
 "ML Engineer": ("Trains, evaluates and ships machine learning models",
    ["Python", "NumPy", "Pandas", "scikit-learn"], ["PyTorch", "Machine Learning", "SQL", "Docker"]),
}

# (skill, prerequisite): learn the prerequisite first
PREREQS = [
 ("Flask", "Python"), ("FastAPI", "Python"), ("FastAPI", "REST API"), ("Django", "Python"), ("Django", "SQL"),
 ("Pandas", "Python"), ("NumPy", "Python"), ("scikit-learn", "Python"), ("scikit-learn", "NumPy"),
 ("scikit-learn", "Pandas"), ("PyTorch", "Python"), ("PyTorch", "NumPy"), ("Machine Learning", "Python"),
 ("Node.js", "JavaScript"), ("React", "JavaScript"), ("React", "HTML"), ("React", "CSS"),
 ("TypeScript", "JavaScript"), ("CSS", "HTML"), ("JavaScript", "HTML"),
 ("MySQL", "SQL"), ("PostgreSQL", "SQL"), ("GitHub", "Git"), ("Power BI", "Excel"), ("Tableau", "Excel"),
]
