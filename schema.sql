DROP TABLE IF EXISTS join_requests;
DROP TABLE IF EXISTS projects;
DROP TABLE IF EXISTS users;

CREATE TABLE users(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password VARCHAR NOT NULL,
    email VARCHAR UNIQUE NOT NULL,
    role TEXT NOT NULL,
    skills TEXT NOT NULL,
    experience_level TEXT NOT NULL,
    last_seen TIMESTAMP
);

CREATE TABLE projects(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_name TEXT NOT NULL,
    project_description TEXT NOT NULL,
    project_status INTEGER NOT NULL,
    skills_needed TEXT NOT NULL,
    total_member_required INTEGER NOT NULL,
    contact_link TEXT NOT NULL,
    user_id INTEGER NOT NULL,
    update_count INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY (user_id) REFERENCES users (id)
);

CREATE TABLE join_requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL,
    applicant_id INTEGER NOT NULL,
    status TEXT DEFAULT 'pending',
    UNIQUE (project_id, applicant_id),
    FOREIGN KEY (project_id) REFERENCES projects (id),
    FOREIGN KEY (applicant_id) REFERENCES users (id)
);
