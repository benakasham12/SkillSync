# SkillSync: Student Skill & Project Team Finder

> **Innovation & Design Thinking (IDT) Project**  
> **Institution & Cohort:** BMS Institute of Technology and Management (BMSIT&M) - CSE 13  
> **Team:** Harsh Tiwari, Benaka Sham, Goral Chhabra, and Akansha  
> **PRD Implementation:** Complete functional MVP corresponding to `PRD.md` (v1.0)

---

## 1. Overview & Core Product Thesis

College students forming project teams often default to existing friendship circles. This leaves project-critical skills uncovered and can lead to uneven contribution and friction. 

**SkillSync** implements a student-started, requirement-first matching platform:
1. Students create verified profiles with self-reported capabilities, weekly availability blocks, and interests.
2. Project owners post course projects with required skills tagged as **must-have** or **preferred** (with weights).
3. The system computes **explainable, deterministic candidate recommendations** (Match Score = 65% Skill Fit + 25% Availability Fit + 10% Interest Fit).
4. Project owners send invitations; candidates accept or decline explicitly.
5. The project dashboard visualizes **team skill coverage** in real time, making remaining capability gaps visible before finalizing.

---

## 2. PRD Requirement Mapping & Features

| PRD Item | Requirement | Implementation Status | Highlights |
|---|---|---|---|
| **FR-01** | Student registration & sign-in | Complete | Institutional email check, hashed passwords (`werkzeug.security`), role support (`student`, `admin`). |
| **FR-02** | Student profile | Complete | Display name, USN, branch, year, section, bio, match-readiness validation. |
| **FR-03** | Skills and proficiency | Complete | Controlled skills taxonomy, self-reported proficiency (`beginner`, `intermediate`, `advanced`). |
| **FR-04** | Interests & availability | Complete | 7-day &times; 4-block weekly schedule grid, interest tag selection. |
| **FR-05** | Create & publish project | Complete | Draft, published, and closed lifecycle states. Drafts excluded from general discovery. |
| **FR-06** | Skill requirements | Complete | Must-have (weight 3.0) and preferred (weight 1.0) requirements. Guard prevents publishing without required skills. |
| **FR-07** | Ranked suggestions | Complete | Deterministic ranking using composite score formula. |
| **FR-08** | Match explanation | Complete | Component breakdown (Skill, Availability, Interest), matched skills list, missing must-have alerts. |
| **FR-09** | Search and filters | Complete | Filter by skill, branch/section, minimum match score, and "fills unmet team gap". |
| **FR-10** | Invitations lifecycle | Complete | Pending, accepted, declined states. Duplicate pending invites prevented. Enforces team capacity limits. |
| **FR-11** | Team roster & coverage | Complete | Live team coverage meter (% must-haves covered, member breakdown, gap identification). |
| **FR-12** | Privacy controls | Complete | `public`, `cohort_only`, and `private` visibility; contact info hidden until invitation accepted; profile deactivation. |
| **FR-13** | Reporting & moderation | Complete | Report inappropriate profiles/projects; admin resolution queue with user deactivation or project closure. |
| **FR-14** | External portfolio links | Complete | GitHub, LinkedIn, portfolio links (labelled self-reported). |
| **Sec 6** | Matching Formula | Complete | 100% faithful to PRD Section 6.3 worked example (verified by automated tests). |
| **Sec 9** | Product Analytics | Complete | Real-time calculation of North Star Metric, completion rates, publish rates, and audit event stream. |

---

## 3. Matching Algorithm (PRD Section 6)

$$\text{Match Score} = 0.65 \times \text{Skill Fit} + 0.25 \times \text{Availability Fit} + 0.10 \times \text{Interest Fit}$$

1. **Skill Fit (65%):**  
   $$\text{Skill Fit} = \frac{\sum \text{Weights of matched required skills}}{\sum \text{Weights of all required skills}} \times 100$$
2. **Availability Fit (25%):**  
   $$\text{Availability Fit} = \frac{\text{Candidate overlapping time blocks}}{\text{Project required time blocks}} \times 100$$
   *(If project schedule is not declared, system labels "Not enough availability data" rather than awarding 100%)*
3. **Interest Fit (10%):**  
   $$\text{Interest Fit} = \frac{\text{Candidate shared interest tags}}{\text{Project interest tags}} \times 100$$
4. **Ranking Safeguards:**  
   - Critical must-have gaps are highlighted separately on candidate cards.
   - Self-reported proficiency is visibly labeled.
   - Candidates who fulfill a capability missing from current team members receive a **"Fills Missing Team Skill"** indicator.

---

## 4. Technology Stack & Architecture

- **Backend:** Python 3.15, Flask 3.1, Werkzeug
- **Database:** SQLite (`skillsync.db`) with foreign key constraints and index optimizations
- **Frontend:** Semantic HTML5, modern SaaS CSS design system (blue/purple/white gradients, glassmorphism, responsive mobile-first layout), vanilla JavaScript micro-interactions
- **Testing:** `pytest` (11 comprehensive unit and integration test suites covering all PRD specifications and landing routes)

```
SkillSync-1/
├── app/
│   ├── __init__.py           # Application factory & context processors
│   ├── models.py             # Relational schema (PRD Sec 7.1) & query helpers
│   ├── matching.py           # Ranking engine & team skill coverage (PRD Sec 6)
│   ├── analytics.py          # Event logging & North Star metrics (PRD Sec 9)
│   ├── seed_data.py          # BMSIT&M CSE 13 cohort and project seed data
│   ├── routes/
│   │   ├── auth.py           # Registration, authentication, quick persona switch
│   │   ├── profile.py        # Profile, skills, availability grid, privacy
│   │   ├── projects.py       # Projects CRUD, requirements, candidate matching
│   │   ├── invitations.py    # Send, accept, decline invitations
│   │   ├── admin.py          # Coordinator dashboard & moderation queue
│   │   └── api.py            # Taxonomy endpoints
│   ├── static/
│   │   ├── css/style.css     # Modern SaaS design system (gradients, glassmorphism, responsive)
│   │   └── js/app.js         # Mobile nav toggle & client-side micro-interactions
│   └── templates/            # Jinja2 templates for all core user journeys
│       ├── landing.html      # High-impact opening SaaS landing page
│       └── base.html         # Sticky blurred navbar & comprehensive footer
├── tests/
│   ├── test_landing.py       # Landing page & navigation route verification
│   ├── test_matching.py      # PRD Section 6.3 worked example verification
│   ├── test_coverage.py      # Team skill coverage and gap filling
│   ├── test_invitations.py   # Invitation lifecycle & duplicate safeguards
│   ├── test_projects.py      # Publishing guards & requirements
│   ├── test_auth_profile.py  # Profile readiness & privacy guards
│   └── test_admin_and_filters.py # Filter controls & moderation
├── seed.py                   # CLI database reset & seed tool
├── run.py                    # Web server entrypoint
└── requirements.txt          # Python dependencies
```

---

## 5. Quick Start Guide

### Option A: 1-Click Launch (Recommended)
Simply double-click **`start.bat`** (or run `.\start.bat` in command prompt / terminal). It will:
1. Verify / configure your virtual environment and dependencies automatically.
2. Initialize and seed the SQLite database with the BMSIT&M CSE 13 cohort.
3. Start the Flask server and open your default browser to `http://127.0.0.1:5000`.

---

### Option B: Manual Setup
```bash
# 1. Activate Virtual Environment
.\venv\Scripts\activate

# 2. Seed or Reset the Database
python seed.py

# 3. Run the Automated Test Suite (11 Tests)
python -m pytest -v

# 4. Start Web Server
python run.py
```
Open your browser to: **`http://127.0.0.1:5000`**

---

## 6. Demo Accounts & Personas

The application includes a **1-Click Persona Switcher** on the Sign-In page (`/login`) allowing reviewers and faculty mentors to test any perspective immediately:

| Persona | Email | Role / Context | Key Capabilities |
|---|---|---|---|
| **Benaka Sham** | `benaka@bmsit.in` | Student (Project Owner) | Python, Flask, REST API, Database Modeling |
| **Harsh Tiwari** | `harsh@bmsit.in` | Student | Python, Machine Learning, Data Analysis, SQLite |
| **Goral Chhabra** | `goral@bmsit.in` | Student | UI/UX, Figma, Wireframing, Tailwind CSS |
| **Akansha** | `akansha@bmsit.in` | Student | Testing/QA, PostgreSQL, Technical Writing |
| **Rohan Kulkarni**| `rohan@bmsit.in` | Student (IoT Project Owner)| IoT & Hardware, Microcontrollers, Python |
| **Priya Sharma**  | `priya@bmsit.in` | Student | Presentation/Pitching, Project Management |
| **Faculty Admin**| `faculty@bmsit.in`| Coordinator / Mentor | Access to PRD Section 9 Analytics & Moderation |

*Password for all student accounts:* `password123`  
*Password for faculty admin:* `admin123`
