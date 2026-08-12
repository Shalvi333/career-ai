"""Career AI — interactive Streamlit career mentor.

Career-intake and personality questions are based on the supplied Career
Mentor Question Bank. Answers stay only in this Streamlit browser session.
"""

from __future__ import annotations

from html import escape
import json
import os
import random
import re
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import streamlit as st


# Transparent butterfly logo: it blends into the page instead of appearing
# as a screenshot with a dark square behind it.
LOGO_PATH = str(Path(__file__).parent / "assets" / "career-ai-logo-clean.png")
JOB_CATALOG_PATH = Path(__file__).parent / "data" / "all_jobs.txt"
UNIVERSITY_DATA_PATH = Path(__file__).parent / "data" / "universities_scholarships.txt"
# Change this if your FastAPI server uses a different host, port, or route.
# You can also set PROFILE_API_URL in your terminal or Streamlit secrets.
DEFAULT_PROFILE_API_URL = "http://127.0.0.1:8000/profile"
DEFAULT_CAREERS_API_URL = "http://127.0.0.1:8000/careers"
DEFAULT_CHAT_API_URL = "http://127.0.0.1:8000/mentor/chat"
DEFAULT_ROADMAP_API_URL = "http://127.0.0.1:8000/roadmap"
DEFAULT_SCORE_API_URL = "http://127.0.0.1:8000/score"
DEFAULT_AUTH_API_URL = "http://127.0.0.1:8000/auth"
st.set_page_config(page_title="Career AI", page_icon=LOGO_PATH, layout="wide", initial_sidebar_state="expanded")

PAGES = ("Dashboard", "Explore Careers", "Skill Roadmap", "Scholarships", "Universities", "AI Mentor")
PAGE_ICONS = {"Dashboard": "⌂", "Explore Careers": "⌕", "Skill Roadmap": "↗", "Scholarships": "🦋", "Universities": "♜", "AI Mentor": "🦋"}
GLOBAL_UNIVERSITY_COUNTRIES = (
    "Afghanistan", "Albania", "Algeria", "Andorra", "Angola", "Antigua and Barbuda", "Argentina", "Armenia", "Australia", "Austria",
    "Azerbaijan", "Bahamas", "Bahrain", "Bangladesh", "Barbados", "Belarus", "Belgium", "Belize", "Benin", "Bhutan", "Bolivia",
    "Bosnia and Herzegovina", "Botswana", "Brazil", "Brunei", "Bulgaria", "Burkina Faso", "Burundi", "Cambodia", "Cameroon", "Canada",
    "Cape Verde", "Central African Republic", "Chad", "Chile", "China", "Colombia", "Comoros", "Congo", "Costa Rica", "Croatia", "Cuba",
    "Cyprus", "Czech Republic", "Denmark", "Djibouti", "Dominica", "Dominican Republic", "Ecuador", "Egypt", "El Salvador", "Estonia",
    "Eswatini", "Ethiopia", "Fiji", "Finland", "France", "Gabon", "Gambia", "Georgia", "Germany", "Ghana", "Greece", "Grenada",
    "Guatemala", "Guinea", "Guyana", "Haiti", "Honduras", "Hong Kong", "Hungary", "Iceland", "India", "Indonesia", "Iran", "Iraq",
    "Ireland", "Israel", "Italy", "Jamaica", "Japan", "Jordan", "Kazakhstan", "Kenya", "Kuwait", "Kyrgyzstan", "Laos", "Latvia",
    "Lebanon", "Lesotho", "Liberia", "Libya", "Liechtenstein", "Lithuania", "Luxembourg", "Madagascar", "Malawi", "Malaysia", "Maldives",
    "Mali", "Malta", "Mauritius", "Mexico", "Moldova", "Monaco", "Mongolia", "Montenegro", "Morocco", "Mozambique", "Myanmar", "Namibia",
    "Nepal", "Netherlands", "New Zealand", "Nicaragua", "Niger", "Nigeria", "North Korea", "North Macedonia", "Norway", "Oman", "Pakistan",
    "Palestine", "Panama", "Papua New Guinea", "Paraguay", "Peru", "Philippines", "Poland", "Portugal", "Qatar", "Romania", "Russia",
    "Rwanda", "Saint Kitts and Nevis", "Saint Lucia", "Saint Vincent and the Grenadines", "Saudi Arabia", "Senegal", "Serbia", "Seychelles",
    "Sierra Leone", "Singapore", "Slovakia", "Slovenia", "Somalia", "South Africa", "South Korea", "Spain", "Sri Lanka", "Sudan", "Suriname",
    "Sweden", "Switzerland", "Syria", "Taiwan", "Tajikistan", "Tanzania", "Thailand", "Timor-Leste", "Togo", "Tonga", "Trinidad and Tobago",
    "Tunisia", "Turkey", "Turkmenistan", "Uganda", "Ukraine", "United Arab Emirates", "United Kingdom", "United States", "Uruguay", "Uzbekistan",
    "Vanuatu", "Venezuela", "Vietnam", "Yemen", "Zambia", "Zimbabwe",
)
QUOTES = (
    "The future depends on what you do today.",
    "Choose a path that lets your strengths grow.",
    "A career is explored one thoughtful step at a time.",
    "Your interests are clues, not limits.",
)

# The full intake bank, grouped as in the supplied document. All prompts are
# intentionally open text so students can answer in their own words.
INTAKE_SECTIONS = (
    ("Basic profile & background", (
        "Tell us your full name, age, and current grade or year of study.",
        "What is your school or institution, board/curriculum, and stream?",
        "Where do you currently live (city, state, and country)?",
        "Are you the first person in your immediate family to pursue higher education?",
        "Which languages are you most comfortable studying and communicating in?",
        "Is there any community, category, or group information you would like us to consider for targeted scholarships? (optional)",
        "Are there physical, learning, or health-related considerations we should account for in recommendations? (optional)",
        "Who most influences your academic and career decisions?",
    )),
    ("Academic performance", (
        "What is your most recent overall percentage, GPA, or CGPA?",
        "Describe your marks or grades in individual subjects over the last two to three academic years.",
        "Which subjects do you consistently score highest in?",
        "Which subjects do you find most difficult or score lowest in?",
        "Which entrance or aptitude tests have you taken or plan to take, and what are your scores or targets?",
        "What academic honours, olympiads, competitions, or subject awards have you received?",
        "Have you repeated a grade, taken a gap year, or faced a disruption in your academic timeline? (optional)",
        "How would you rate your academic performance relative to your effort: underperforming, on par, or overperforming?",
    )),
    ("Interests & passions", (
        "If you had a completely free afternoon, what would you choose to do?",
        "Which school subjects genuinely interest you, even if they are not your highest-scoring ones?",
        "Name up to five topics, fields, or industries you enjoy reading, watching, or talking about.",
        "Is there a career, role, or public figure whose day-to-day work you admire? What appeals to you about it?",
        "Rank your preference for working with people, data/information, physical objects/tools, and abstract ideas.",
        "Would you rather create something new, analyse a problem, help a person, lead a group, or organise a system? Why?",
        "What subjects or industries are you curious about but have not had a chance to explore?",
        "How have your interests changed in the last two or three years?",
        "On a scale of 1–5, how strongly do your interests align with what you think you should pursue for a stable career? Explain briefly.",
    )),
    ("Skills & strengths", (
        "What do teachers, family, or friends say you are naturally good at?",
        "List any technical skills you have, such as coding, design tools, lab work, writing, public speaking, music, or sport.",
        "List soft skills you consider strengths, such as leadership, communication, teamwork, problem-solving, or creativity.",
        "List any certifications, formal training, or online courses you have completed.",
        "Describe a project, assignment, or task you are proud of. What made it successful?",
        "Which skills are you actively trying to build right now?",
        "Rate your confidence (1–5) in analytical reasoning, communication, creativity, maths, interpersonal skills, and digital literacy.",
        "Do you see yourself as more of a generalist or specialist? Why?",
    )),
    ("Hobbies & activities", (
        "What are your current hobbies, and how many hours per week do you spend on each?",
        "Are you part of clubs, teams, student councils, or societies?",
        "Describe any competitions, hackathons, debates, sports tournaments, exhibitions, or performances you have joined.",
        "Do you do volunteering, community service, or social-impact work?",
        "Have you had internships, part-time jobs, shadowing, or freelance experience?",
        "Do you contribute to personal projects outside school, such as a blog, app, channel, small business, or team?",
        "Which activity would you continue even if it never helped your resume or application?",
        "How do your hobbies overlap with your interests?",
    )),
    ("Drive, motivation & work values", (
        "Rank your top three motivators: solving problems, recognition, income, creative freedom, helping others, or status.",
        "Do you prefer a fast-paced, high-pressure environment or a steady, predictable one? Why?",
        "Would you rather work independently, in a small close-knit team, or in a large organisation?",
        "On a scale of 1–5, how important is work-life balance compared with career advancement?",
        "How comfortable are you with uncertainty, entrepreneurship, or unconventional paths compared with stability?",
        "Describe a time you kept working on something difficult. What kept you going?",
        "Would you rather become an expert in one field or work across different areas?",
        "How important is visible positive impact on people or society in your future work?",
        "Where do you see yourself in ten years? Describe it freely.",
    )),
    ("Career awareness & aspirations", (
        "Do you already have a career or field in mind? How did you arrive at it?",
        "If you are undecided, which two or three broad fields are you considering?",
        "Have you spoken with, shadowed, or interviewed anyone in a field you are considering?",
        "What concerns or fears do you have about choosing the wrong career path?",
        "Are there careers you feel pushed toward that do not excite you?",
        "Are there careers you are excited about but hesitant to pursue due to family, financial, or social pressure?",
        "How much importance should recommendations give to salary and job-market demand versus personal interest?",
        "Would you be open to an emerging or unconventional career if it matched your profile well?",
    )),
    ("University & location preferences", (
        "Which countries would you prefer for higher education?",
        "Which states, regions, or cities would you prefer within your home country?",
        "Would you prefer to study close to home or are you open to relocating or studying abroad?",
        "Which campus environment suits you: large research university, small liberal-arts college, specialised institute, or any?",
        "Do you prefer an urban, suburban, or rural/residential campus?",
        "Do you prefer public/government or private institutions, or are you open to both?",
        "On a scale of 1–5, how important is prestige compared with programme fit, cost, and location?",
        "Do you prefer a large student body or a smaller close-knit community?",
        "Are you interested in accreditations, exchanges, or study-abroad opportunities?",
        "What climate, culture, language, safety, or lifestyle preferences matter to you?",
    )),
    ("Financial considerations", (
        "What is your approximate annual budget for tuition and living expenses? A range is fine.",
        "Will you rely on family funding, loans, scholarships, work, or a combination?",
        "Are you open to an education loan, and what is a comfortable maximum amount?",
        "Which merit, need-based, community, sports, or arts scholarships may you qualify for?",
        "Would you consider part-time work, a co-op, or work-study during your studies?",
        "Is cost a hard constraint or a softer preference?",
        "Would you consider a lower-cost institution with a transfer plan later?",
    )),
    ("Learning style", (
        "Do you learn best through hands-on work, visuals, reading/writing, or listening/discussion?",
        "Do you prefer structured coursework or open-ended, self-directed projects?",
        "Do you perform better with continuous assessment or high-stakes exams?",
        "Do you prefer small interactive classes or large lecture-based courses?",
        "Do you prefer interdisciplinary programs or a single focused major?",
        "How comfortable are you with online, hybrid, or remote learning compared with in-person learning?",
        "Would you prefer a standard-length program or flexible programs that let you change direction?",
    )),
    ("Support & constraints", (
        "Do family responsibilities affect your location, course length, or work-study choices?",
        "Do you have mentors or counsellors, and would you like to share recommendations with them?",
        "Are there timeline constraints for starting or finishing your studies?",
        "Do visa, immigration, or citizenship considerations affect where you can study or work?",
        "Is there anything else you want Career AI to know before it creates recommendations?",
    )),
)

SHORT_INTAKE = tuple((title, questions[0]) for title, questions in INTAKE_SECTIONS)
LONG_INTAKE = tuple((title, question) for title, questions in INTAKE_SECTIONS for question in questions)

RIASEC = {
    "R": ("Realistic", "🔧", ("I enjoy fixing or building things with my hands.", "I would rather work outdoors than sit in an office all day.", "I like understanding how machines, engines, or systems work.", "I prefer clear, practical tasks over abstract theory.", "I enjoy working with tools, equipment, or technology in a hands-on way.", "I like sports, physical activity, or working with my body.", "I would enjoy a job that involves building, repairing, or operating something.", "I prefer concrete results I can see and touch over abstract ideas.", "I am comfortable working in labs, workshops, or field settings.", "I like solving practical, real-world problems rather than theoretical ones.")),
    "I": ("Investigative", "🔬", ("I enjoy analyzing data, patterns, or complex problems.", "I like asking why and digging deep to understand root causes.", "I enjoy science subjects more than most.", "I would rather figure something out myself than be told the answer.", "I like reading research, studies, or in-depth articles on topics that interest me.", "I enjoy puzzles, logic problems, or strategy games.", "I am comfortable working with numbers, formulas, or statistics.", "I like designing experiments or testing hypotheses.", "I prefer careful, evidence-based reasoning over gut instinct.", "I would enjoy a career centered on research or discovery.")),
    "A": ("Artistic", "🎨", ("I enjoy expressing myself through writing, art, music, or design.", "I get bored with rigid rules and prefer creative freedom.", "I often come up with original or unconventional ideas.", "I enjoy imagining new possibilities more than following a set process.", "I like activities such as drawing, photography, film, theatre, or music.", "I value beauty, style, and aesthetics in things I create or use.", "I would enjoy a career that lets me express my own point of view.", "I prefer open-ended projects over highly structured ones.", "I enjoy storytelling through words, images, or performance.", "I like environments where non-traditional thinking is encouraged.")),
    "S": ("Social", "🤝", ("I enjoy helping people solve personal or academic problems.", "I find it rewarding to teach or explain something to someone else.", "I am good at listening to and understanding other people's feelings.", "I enjoy working in teams and collaborating with others.", "I would enjoy a career focused on healthcare, counselling, or education.", "People often come to me for advice or support.", "I care more about my work's impact on people than prestige or pay.", "I enjoy volunteering or community-oriented activities.", "I am comfortable resolving conflicts or mediating between people.", "I would rather work closely with people than alone with data or objects.")),
    "E": ("Enterprising", "🚀", ("I enjoy convincing or persuading others toward an idea or goal.", "I like taking charge and leading a group or project.", "I am comfortable with competition and enjoy trying to win.", "I would enjoy starting my own business or venture someday.", "I like setting ambitious goals and pushing to achieve them.", "I am comfortable with public speaking or presenting to a group.", "I enjoy negotiating deals or managing a team's decisions.", "I am motivated by status, achievement, or financial success.", "I like taking initiative rather than waiting to be told what to do.", "I would enjoy a career in business, law, politics, or sales or marketing.")),
    "C": ("Conventional", "📋", ("I enjoy organizing information, files, or schedules.", "I like following clear rules, processes, and procedures.", "I am detail-oriented and rarely miss small errors.", "I feel satisfied when things are neat, accurate, and well-structured.", "I am comfortable working with spreadsheets, records, or databases.", "I prefer predictable, well-defined tasks over ambiguous ones.", "I am reliable about deadlines, checklists, and routines.", "I would enjoy a career in accounting, administration, or operations.", "I like double-checking my work to make sure it is accurate.", "I am comfortable with repetitive tasks if they lead to a well-organized outcome.")),
}

RIASEC_QUESTIONS = tuple((code, statement) for code, (_, _, statements) in RIASEC.items() for statement in statements)
# Quick RIASEC: two representative statements from each of the six themes.
SHORT_RIASEC_QUESTIONS = tuple(
    (code, statement)
    for code, (_, _, statements) in RIASEC.items()
    for statement in statements[:2]
)
# These IDs must match the keys in the backend QUESTION_DIMENSIONS dictionary.
# Example: QUESTION_DIMENSIONS = {"q1": "R", "q2": "R", ..., "q60": "C"}.
# The quick quiz keeps the IDs from the complete 60-question bank.
BACKEND_QUESTION_ID_BY_STATEMENT = {
    statement: f"q{index + 1}" for index, (_, statement) in enumerate(RIASEC_QUESTIONS)
}

CAREER_MAP = {
    "R": ("Mechanical Engineer", "Civil Engineer", "Architect", "Environmental Scientist", "Automotive Engineer", "Pilot", "Industrial Designer", "Forensic Scientist"),
    "I": ("Data Scientist", "Software Engineer", "Physician", "Biotechnologist", "Research Scientist", "Cybersecurity Analyst", "Economist", "Clinical Researcher"),
    "A": ("Actor", "Theatre Artist", "UX Designer", "Writer", "Animator", "Graphic Designer", "Film Maker", "Fashion Designer", "Game Designer", "Content Strategist"),
    "S": ("Psychologist", "Teacher", "Healthcare Professional", "Counsellor", "Social Worker", "Nurse", "Speech Therapist", "Education Consultant"),
    "E": ("Entrepreneur", "Product Manager", "Lawyer", "Marketing Manager", "Management Consultant", "Sales Manager", "Public Relations Specialist", "Business Development Manager"),
    "C": ("Data Analyst", "Accountant", "Operations Manager", "Financial Analyst", "Actuarial Analyst", "Supply Chain Manager", "Project Coordinator", "Compliance Officer"),
    "RI": ("Robotics Engineer", "Aerospace Engineer", "Environmental Scientist", "Biomedical Engineer", "Cybersecurity Analyst"),
    "IA": ("UX Researcher", "Product Designer", "Science Journalist", "Human-Computer Interaction Researcher", "Data Visualisation Specialist"),
    "AS": ("Art Therapist", "Communications Specialist", "Teacher", "Museum Educator", "Creative Arts Therapist"),
    "SE": ("HR Manager", "Corporate Trainer", "Nonprofit Director", "Community Manager", "Healthcare Administrator"),
    "EC": ("Financial Manager", "Supply Chain Manager", "Business Analyst", "Investment Analyst", "Operations Consultant"),
    "CI": ("Actuarial Analyst", "Statistician", "Risk Analyst", "Business Intelligence Analyst", "Database Administrator"),
}

CAREER_CATALOG = tuple(sorted({career for careers in CAREER_MAP.values() for career in careers}))
CAREER_THEME_CODES: dict[str, tuple[str, ...]] = {}
for _theme_code, _careers in CAREER_MAP.items():
    for _career in _careers:
        CAREER_THEME_CODES[_career] = tuple(sorted(set(CAREER_THEME_CODES.get(_career, ()) + tuple(_theme_code))))

SKILLS_BY_THEME = {
    "R": ("hands-on projects", "technical drawing or CAD", "lab or field experience"),
    "I": ("data analysis", "research methods", "Python or scientific tools"),
    "A": ("portfolio projects", "visual storytelling", "design tools"),
    "S": ("communication", "active listening", "volunteering or mentoring"),
    "E": ("presentation skills", "leadership", "business fundamentals"),
    "C": ("spreadsheets", "attention to detail", "project organisation"),
}

# The career-discovery answers are free text, so use only clear, career-related
# words as an early signal. The RIASEC quiz remains the more accurate profile.
INTAKE_THEME_KEYWORDS = {
    "R": ("build", "repair", "machine", "engine", "robot", "mechanical", "workshop", "hardware", "sport", "field work", "outdoor", "tool"),
    "I": ("data", "science", "research", "analysis", "problem solving", "coding", "programming", "math", "technology", "experiment", "physics"),
    "A": ("acting", "actor", "actress", "theatre", "theater", "perform", "performance", "drama", "stage", "audition", "art", "design", "draw", "creative", "writing", "music", "film", "content", "photography", "story", "visual"),
    "S": ("help", "teach", "people", "care", "counsel", "health", "community", "team", "psychology", "education", "volunteer"),
    "E": ("business", "lead", "leadership", "management", "entrepreneur", "marketing", "sales", "law", "finance", "public speaking", "company"),
    "C": ("organise", "organize", "plan", "detail", "account", "spreadsheet", "system", "structure", "admin", "logistics", "records"),
}

# Direct mentions in the written career quiz should be stronger evidence than a
# generic category. These careers appear before broader RIASEC suggestions.
# The complete job directory remains available in Explore Careers.
DIRECT_CAREER_KEYWORDS = {
    "acting": ("Actor", "Theatre Artist", "Film Maker"), "actor": ("Actor", "Theatre Artist"), "theatre": ("Theatre Artist", "Actor"), "drama": ("Actor", "Theatre Artist"),
    "film": ("Film Maker", "Video Editor", "Screenwriter"), "music": ("Musician", "Music Producer", "Sound Engineer"), "dance": ("Dancer", "Choreographer", "Dance Teacher"),
    "fashion": ("Fashion Designer", "Fashion Stylist", "Textile Designer"), "photography": ("Photographer", "Photojournalist", "Visual Artist"),
    "animation": ("Animator", "Game Designer", "Illustrator"), "game": ("Game Designer", "Game Developer", "Animator"),
    "writing": ("Writer", "Journalist", "Content Strategist"), "writer": ("Writer", "Technical Writer", "Journalist"),
    "design": ("UX Designer", "Graphic Designer", "Product Designer"), "art": ("Graphic Designer", "Illustrator", "Visual Artist"),
    "coding": ("Software Engineer", "Front-End Developer", "Back-End Developer"), "programming": ("Software Engineer", "Full-Stack Developer", "Mobile App Developer"),
    "software": ("Software Engineer", "Full-Stack Developer", "Cloud Engineer"), "cybersecurity": ("Cybersecurity Analyst", "Penetration Tester / Ethical Hacker", "Information Security Manager"),
    "ai": ("Machine Learning Engineer", "AI Research Scientist", "Data Scientist"), "data": ("Data Analyst", "Data Scientist", "Data Engineer"),
    "robot": ("Robotics Engineer", "Robotics Software Engineer", "Mechatronics Engineer"),
    "doctor": ("Physician", "Surgeon", "Healthcare Professional"), "medicine": ("Physician", "Clinical Researcher", "Pharmacist"), "nurse": ("Nurse", "Healthcare Professional", "Nurse Practitioner"),
    "psychology": ("Psychologist", "Counsellor", "Clinical Psychologist"), "therapy": ("Psychologist", "Speech Therapist", "Occupational Therapist"),
    "teacher": ("Teacher", "Education Consultant", "Corporate Trainer"), "education": ("Teacher", "Education Consultant", "School Counsellor"),
    "law": ("Lawyer", "Legal Advisor", "Policy Analyst"), "lawyer": ("Lawyer", "Corporate Lawyer", "Legal Advisor"),
    "business": ("Entrepreneur", "Business Analyst", "Management Consultant"), "entrepreneur": ("Entrepreneur", "Business Development Manager", "Product Manager"),
    "marketing": ("Marketing Manager", "Brand Manager", "Public Relations Specialist"), "finance": ("Financial Analyst", "Investment Banker", "Accountant"),
    "accounting": ("Accountant", "Auditor (Internal/External)", "Financial Analyst"), "economics": ("Economist", "Financial Analyst", "Policy Analyst"),
    "engineering": ("Mechanical Engineer", "Civil Engineer", "Electrical Engineer"), "architecture": ("Architect", "Urban Planner", "Interior Designer"),
    "environment": ("Environmental Scientist", "Sustainability Consultant", "Conservation Scientist"), "science": ("Research Scientist", "Biotechnologist", "Laboratory Technician"),
    "sports": ("Sports Coach", "Sports Psychologist", "Physiotherapist"), "cricket": ("Cricketer", "Sports Coach", "Sports Journalist"),
    "chef": ("Chef", "Food Scientist", "Restaurant Manager"), "travel": ("Travel Consultant", "Hotel Manager", "Tourism Manager"),
    "pilot": ("Pilot", "Aerospace Engineer", "Air Traffic Controller"),
    "social work": ("Social Worker", "Community Manager", "Nonprofit Director"), "politics": ("Policy Analyst", "Diplomat", "Public Relations Specialist"),
}

CAREER_FIELD_SIGNALS = {
    "acting": ("Media", "Arts"), "theatre": ("Media", "Arts"), "film": ("Media", "Arts"), "music": ("Media", "Arts"), "dance": ("Media", "Arts"),
    "fashion": ("Arts", "Design"), "photography": ("Arts", "Media"), "animation": ("Arts", "Media"), "game": ("Technology", "Media"), "design": ("Arts", "Design"), "writing": ("Writing", "Media"),
    "coding": ("Technology",), "programming": ("Technology",), "software": ("Technology",), "cybersecurity": ("Technology",), "data": ("Technology", "Science"), "ai": ("Technology", "Science"), "robot": ("Engineering", "Technology"),
    "doctor": ("Healthcare", "Medicine"), "medicine": ("Healthcare", "Medicine"), "nurse": ("Healthcare",), "psychology": ("Healthcare", "Social Services"), "therapy": ("Healthcare", "Social Services"),
    "teacher": ("Education",), "education": ("Education",), "law": ("Law",), "business": ("Business",), "marketing": ("Marketing", "Business"), "finance": ("Business", "Finance"), "accounting": ("Business", "Finance"),
    "engineering": ("Engineering", "Technology"), "architecture": ("Engineering", "Arts"), "environment": ("Environment", "Science"), "science": ("Science", "Research"),
    "sports": ("Sports", "Healthcare"), "cricket": ("Sports",), "chef": ("Hospitality",), "travel": ("Hospitality", "Tourism"), "pilot": ("Transportation", "Engineering"),
    "social work": ("Social Services",), "politics": ("Government", "Public Policy"),
}


def load_job_catalog() -> dict[str, tuple[str, ...]]:
    """Read the full user-provided job catalogue, organised by category."""
    categories: dict[str, list[str]] = {}
    current_category = "Career paths"
    categories[current_category] = []
    for raw_line in JOB_CATALOG_PATH.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if re.match(r"^\d+\.\s+", line):
            current_category = re.sub(r"^\d+\.\s+", "", line)
            categories.setdefault(current_category, [])
        else:
            categories[current_category].append(line)
    return {category: tuple(dict.fromkeys(jobs)) for category, jobs in categories.items() if jobs}


JOB_CATALOG = load_job_catalog()
ALL_JOBS = tuple(sorted({job for jobs in JOB_CATALOG.values() for job in jobs}))


def load_university_data() -> tuple[tuple[dict[str, str], ...], tuple[dict[str, str], ...]]:
    """Read university recommendations and the master scholarship directory."""
    lines = [line.strip() for line in UNIVERSITY_DATA_PATH.read_text(encoding="utf-8").splitlines()]
    scholarships: list[dict[str, str]] = []
    universities: list[dict[str, str]] = []
    current_field = ""
    in_master_directory = False
    for line in lines:
        if not line:
            continue
        if line == "Master Scholarship Directory (Applies Across Sectors)":
            in_master_directory = True
            continue
        if line.startswith("1. ") and not in_master_directory:
            continue
        if re.match(r"^\d+\.\s+", line):
            in_master_directory = False
            current_field = re.sub(r"^\d+\.\s+", "", line)
            continue
        if line.startswith("Scholarship\tFunded By") or line.startswith("University\tCountry") or line.startswith("University/Institute\tCountry") or line.startswith("Institute\tCountry"):
            continue
        cells = [cell.strip() for cell in line.split("\t")]
        if in_master_directory and len(cells) == 4:
            scholarships.append({"name": cells[0], "funded_by": cells[1], "coverage": cells[2], "best_for": cells[3]})
        elif current_field and len(cells) == 4:
            universities.append({"field": current_field, "name": cells[0], "country": cells[1], "reputation": cells[2], "scholarships": cells[3]})
    return tuple(universities), tuple(scholarships)


UNIVERSITY_CATALOG, SCHOLARSHIP_CATALOG = load_university_data()


@st.cache_data(ttl=60 * 60 * 24, show_spinner=False)
def search_worldwide_universities(query: str, country: str) -> tuple[dict[str, str], ...]:
    """Use OpenAlex's public institution index for a broad worldwide search.

    It supplements the hand-curated recommendation data above. Results are
    intentionally labelled as directory matches, not rankings or endorsements.
    """
    search = query.strip()
    if not search and country == "All countries":
        return ()
    filters = ["types:education"]
    if country != "All countries":
        filters.append(f"country_code:{country_code(country)}")
    params = {"per-page": "50", "filter": ",".join(filters)}
    if search:
        params["search"] = search
    endpoint = "https://api.openalex.org/institutions?" + urlencode(params)
    try:
        request = Request(endpoint, headers={"User-Agent": "Career-AI-Student-Project/1.0"})
        with urlopen(request, timeout=12) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, OSError, json.JSONDecodeError):
        return ()
    results: list[dict[str, str]] = []
    for item in payload.get("results", []):
        if item.get("type") != "education":
            continue
        location = item.get("geo") or {}
        results.append({
            "name": str(item.get("display_name") or "Unnamed institution"),
            "country": str(item.get("country_code") or "").upper(),
            "city": str(location.get("city") or ""),
            "website": str(item.get("homepage_url") or ""),
        })
    return tuple(results)


def country_code(country: str) -> str:
    """Country names used in the UI mapped to ISO codes for OpenAlex."""
    codes = {
        "Afghanistan":"AF","Albania":"AL","Algeria":"DZ","Andorra":"AD","Angola":"AO","Antigua and Barbuda":"AG","Argentina":"AR","Armenia":"AM","Australia":"AU","Austria":"AT","Azerbaijan":"AZ","Bahamas":"BS","Bahrain":"BH","Bangladesh":"BD","Barbados":"BB","Belarus":"BY","Belgium":"BE","Belize":"BZ","Benin":"BJ","Bhutan":"BT","Bolivia":"BO","Bosnia and Herzegovina":"BA","Botswana":"BW","Brazil":"BR","Brunei":"BN","Bulgaria":"BG","Burkina Faso":"BF","Burundi":"BI","Cambodia":"KH","Cameroon":"CM","Canada":"CA","Cape Verde":"CV","Central African Republic":"CF","Chad":"TD","Chile":"CL","China":"CN","Colombia":"CO","Comoros":"KM","Congo":"CG","Costa Rica":"CR","Croatia":"HR","Cuba":"CU","Cyprus":"CY","Czech Republic":"CZ","Denmark":"DK","Djibouti":"DJ","Dominica":"DM","Dominican Republic":"DO","Ecuador":"EC","Egypt":"EG","El Salvador":"SV","Estonia":"EE","Eswatini":"SZ","Ethiopia":"ET","Fiji":"FJ","Finland":"FI","France":"FR","Gabon":"GA","Gambia":"GM","Georgia":"GE","Germany":"DE","Ghana":"GH","Greece":"GR","Grenada":"GD","Guatemala":"GT","Guinea":"GN","Guyana":"GY","Haiti":"HT","Honduras":"HN","Hong Kong":"HK","Hungary":"HU","Iceland":"IS","India":"IN","Indonesia":"ID","Iran":"IR","Iraq":"IQ","Ireland":"IE","Israel":"IL","Italy":"IT","Jamaica":"JM","Japan":"JP","Jordan":"JO","Kazakhstan":"KZ","Kenya":"KE","Kuwait":"KW","Kyrgyzstan":"KG","Laos":"LA","Latvia":"LV","Lebanon":"LB","Lesotho":"LS","Liberia":"LR","Libya":"LY","Liechtenstein":"LI","Lithuania":"LT","Luxembourg":"LU","Madagascar":"MG","Malawi":"MW","Malaysia":"MY","Maldives":"MV","Mali":"ML","Malta":"MT","Mauritius":"MU","Mexico":"MX","Moldova":"MD","Monaco":"MC","Mongolia":"MN","Montenegro":"ME","Morocco":"MA","Mozambique":"MZ","Myanmar":"MM","Namibia":"NA","Nepal":"NP","Netherlands":"NL","New Zealand":"NZ","Nicaragua":"NI","Niger":"NE","Nigeria":"NG","North Korea":"KP","North Macedonia":"MK","Norway":"NO","Oman":"OM","Pakistan":"PK","Palestine":"PS","Panama":"PA","Papua New Guinea":"PG","Paraguay":"PY","Peru":"PE","Philippines":"PH","Poland":"PL","Portugal":"PT","Qatar":"QA","Romania":"RO","Russia":"RU","Rwanda":"RW","Saint Kitts and Nevis":"KN","Saint Lucia":"LC","Saint Vincent and the Grenadines":"VC","Saudi Arabia":"SA","Senegal":"SN","Serbia":"RS","Seychelles":"SC","Sierra Leone":"SL","Singapore":"SG","Slovakia":"SK","Slovenia":"SI","Somalia":"SO","South Africa":"ZA","South Korea":"KR","Spain":"ES","Sri Lanka":"LK","Sudan":"SD","Suriname":"SR","Sweden":"SE","Switzerland":"CH","Syria":"SY","Taiwan":"TW","Tajikistan":"TJ","Tanzania":"TZ","Thailand":"TH","Timor-Leste":"TL","Togo":"TG","Tonga":"TO","Trinidad and Tobago":"TT","Tunisia":"TN","Turkey":"TR","Turkmenistan":"TM","Uganda":"UG","Ukraine":"UA","United Arab Emirates":"AE","United Kingdom":"GB","United States":"US","Uruguay":"UY","Uzbekistan":"UZ","Vanuatu":"VU","Venezuela":"VE","Vietnam":"VN","Yemen":"YE","Zambia":"ZM","Zimbabwe":"ZW",
    }
    return codes.get(country, "")

THEMES = {
    "Dark": {"bg":"radial-gradient(circle at 70% 2%,#34206c 0,#170b31 38%,#0d0820 100%)", "text":"#fbfaff", "muted":"#bdb4d4", "card":"linear-gradient(145deg,rgba(37,24,76,.96),rgba(16,10,42,.96))", "soft":"rgba(35,23,71,.84)", "line":"rgba(190,156,255,.22)", "sidebar":"#0d0824", "input":"#211542", "input_text":"#ffffff", "shadow":"rgba(0,0,0,.27)", "score":"linear-gradient(135deg,#4d26c5,#1e4eaa)", "mentor":"linear-gradient(145deg,rgba(69,29,93,.86),rgba(18,11,45,.96))"},
    "Light": {"bg":"radial-gradient(circle at 72% 5%,#fff 0,#f0edff 43%,#e5e0ff 100%)", "text":"#28184d", "muted":"#71628d", "card":"linear-gradient(145deg,rgba(255,255,255,.98),rgba(248,246,255,.98))", "soft":"rgba(255,255,255,.9)", "line":"rgba(124,58,237,.20)", "sidebar":"#201153", "input":"#ffffff", "input_text":"#15121d", "shadow":"rgba(67,37,128,.12)", "score":"linear-gradient(135deg,#7542df,#5e94ef)", "mentor":"linear-gradient(145deg,#fff,#f8f5ff)"},
}


def init_state() -> None:
    defaults = {"app_stage":"login", "auth_mode":"create", "light_mode":False, "nav_page":"Dashboard", "student_name":"", "student_email":"", "quiz_name":"", "intake_mode":None, "intake_index":0, "intake_answers":{}, "personality_mode":None, "personality_index":0, "personality_answers":{}, "personality_complete":False, "backend_profile":None, "backend_error":"", "top_matches":[], "career_insights":{}, "score_error":"", "local_roadmap_completed":set(), "mentor_history":[]}
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)


def log_out() -> None:
    """Clear the active profile but retain browser-only demo accounts for login."""
    local_accounts = st.session_state.get("local_demo_accounts", {})
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.session_state.local_demo_accounts = local_accounts
    st.session_state.app_stage = "login"
    st.session_state.auth_mode = "create"
    st.session_state.light_mode = False
    st.session_state.nav_page = "Dashboard"


def theme_name() -> str:
    return "Light" if st.session_state.light_mode else "Dark"


def inject_styles() -> None:
    t = THEMES[theme_name()]
    st.markdown(f"""<style>
    @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Space+Grotesk:wght@500;600;700&display=swap');
    :root{{--bg:{t['bg']};--text:{t['text']};--muted:{t['muted']};--card:{t['card']};--soft:{t['soft']};--line:{t['line']};--sidebar:{t['sidebar']};--input:{t['input']};--input-text:{t['input_text']};--shadow:{t['shadow']};--score:{t['score']};--mentor:{t['mentor']};--violet:#7c3aed;--pink:#ef5e7d;--mint:#15bfa2}} *{{font-family:'DM Sans',sans-serif}} .stApp{{background:var(--bg);color:var(--text)}} #MainMenu,footer{{visibility:hidden}} header,[data-testid='stHeader']{{background:transparent!important;height:2.8rem!important;pointer-events:none!important}} [data-testid='stHeader'] button{{pointer-events:auto!important}} [data-testid='stToolbar']{{display:none!important}} .block-container{{max-width:1500px;padding-top:2.2rem;padding-bottom:2.5rem}} [data-testid='stSidebar']{{background:var(--sidebar)!important;border-right:1px solid rgba(211,193,255,.24)!important;min-width:270px!important}} section[data-testid='stSidebar'][aria-expanded='false']{{min-width:270px!important;transform:translateX(0)!important;margin-left:0!important}} [data-testid='stSidebar'] *{{color:#f8f5ff!important}} h1,h2,h3{{font-family:'Space Grotesk',sans-serif;color:var(--text)}}
    .brand{{display:flex;align-items:center;gap:10px;margin:3px 0 20px}}.brand-name{{color:#fff;font:700 1.35rem 'Space Grotesk',sans-serif;white-space:nowrap}}.brand-name span{{color:#ff6b81}}.sidebar-tagline{{color:#cfc4eb;font-size:.73rem;white-space:nowrap}}.top-title{{font:700 2.25rem 'Space Grotesk',sans-serif;color:var(--text);letter-spacing:-1.4px;margin:0 0 3px}}.top-subtitle{{color:var(--muted);margin-bottom:18px}}.panel{{background:var(--card);border:1px solid var(--line);border-radius:18px;padding:20px;box-shadow:0 15px 38px var(--shadow);box-sizing:border-box}}.panel h3{{margin:0 0 8px}}.muted{{color:var(--muted)!important}}.accent{{color:#8b5cf6;font-weight:700}}.mint{{color:var(--mint);font-weight:700}}
    .choice-card{{background:var(--card);border:1px solid var(--line);border-radius:20px;padding:27px;min-height:250px;text-align:center;box-shadow:0 15px 38px var(--shadow)}}.choice-icon{{font-size:2.6rem;margin-bottom:9px}}.quiz-step{{color:#8b5cf6;font-size:.85rem;font-weight:700;margin-bottom:10px}}.question-card{{background:var(--card);border:1px solid var(--line);border-radius:20px;padding:29px;box-shadow:0 15px 38px var(--shadow)}}.question-number{{color:#8b5cf6;font-weight:700}}.question-text{{font:600 1.6rem 'Space Grotesk',sans-serif;color:var(--text);line-height:1.35;margin:13px 0 21px}}.progress-shell{{height:8px;background:rgba(124,58,237,.16);border-radius:999px;overflow:hidden;margin:11px 0 25px}}.progress-fill{{height:100%;background:linear-gradient(90deg,#7c3aed,#ef5e7d);border-radius:999px}}.result-code{{font:700 3.2rem 'Space Grotesk',sans-serif;color:#8b5cf6;letter-spacing:4px}}.result-number{{font:700 2.7rem 'Space Grotesk',sans-serif;color:var(--text)}}.match-grid{{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:11px}}.match-card{{background:var(--soft);border:1px solid var(--line);border-radius:13px;padding:15px;min-height:160px}}.match-pill{{float:right;color:var(--mint);background:rgba(21,191,162,.13);padding:4px 8px;border-radius:8px;font-size:.74rem;font-weight:700}}.icon-bubble{{width:43px;height:43px;display:grid;place-items:center;border-radius:14px;background:linear-gradient(145deg,rgba(255,71,88,.34),rgba(19,12,31,.9));border:1px solid rgba(255,99,111,.62);box-shadow:inset 0 1px rgba(255,255,255,.2),0 0 14px rgba(255,48,73,.45);font-size:1.35rem}}.butterfly-mark{{color:#ff5066;text-shadow:0 0 8px #ff324c,0 0 18px rgba(255,50,76,.74);font-size:1.35rem}}.score-panel{{background:var(--score);border-radius:18px;padding:23px;color:#fff;min-height:228px}}.score-panel *{{color:#fff}}.big-score{{font:700 3.2rem 'Space Grotesk',sans-serif;margin:22px 0 8px}}.ai-card{{background:var(--mentor);border:1px solid rgba(236,91,122,.38);border-radius:18px;padding:20px;margin-bottom:17px}}.ai-card p{{color:var(--muted)}}
    .login-visual{{position:relative;min-height:610px;display:flex;align-items:center;justify-content:center;overflow:hidden}}.login-orbit{{position:absolute;width:470px;height:470px;border:1px dashed rgba(154,105,255,.34);border-radius:50%}}.login-message{{position:relative;z-index:2;max-width:500px;text-align:center;font:700 3.1rem/1.05 'Space Grotesk',sans-serif;color:var(--text);letter-spacing:-2px}}.login-message span{{color:#ef5e7d}}.float-career{{position:absolute;z-index:3;display:grid;place-items:center;width:93px;height:93px;border-radius:27px;border:1px solid var(--line);background:var(--soft);box-shadow:0 13px 32px var(--shadow);font-size:3rem;animation:career-drift 4s ease-in-out infinite}}.career-1{{top:48px;left:15%}}.career-2{{top:48px;right:15%;animation-delay:-1s}}.career-3{{top:235px;left:2%;animation-delay:-2s}}.career-4{{top:235px;right:2%;animation-delay:-.5s}}.career-5{{bottom:46px;left:17%;animation-delay:-2.5s}}.career-6{{bottom:46px;right:17%;animation-delay:-1.5s}}@keyframes career-drift{{50%{{transform:translateY(-12px) rotate(3deg)}}}}
    .st-key-ai_mentor_card{{background:var(--mentor);border:1px solid rgba(236,91,122,.44)!important;border-radius:17px;padding:12px 13px 16px;box-shadow:0 15px 38px var(--shadow);text-align:center}}[data-testid='stImage'] img{{filter:drop-shadow(0 0 7px rgba(163,99,255,.9)) drop-shadow(0 0 18px rgba(236,91,122,.42));animation:logo-glow 2.8s ease-in-out infinite;object-fit:contain!important}}@keyframes logo-glow{{50%{{filter:drop-shadow(0 0 12px rgba(181,114,255,1)) drop-shadow(0 0 30px rgba(255,91,141,.7))}}}}
    div[data-baseweb='input'],div[data-baseweb='input']>div,div[data-baseweb='textarea'],div[data-baseweb='textarea']>div{{background:var(--input)!important;border-color:var(--line)!important}}[data-testid='stTextInput'] input,[data-testid='stTextArea'] textarea,.stTextInput input,.stTextArea textarea,div[data-baseweb='input'] input,div[data-baseweb='textarea'] textarea{{background-color:var(--input)!important;color:var(--input-text)!important;-webkit-text-fill-color:var(--input-text)!important;caret-color:var(--input-text)!important;opacity:1!important;font-weight:600!important}}[data-testid='stTextInput'] input::placeholder,[data-testid='stTextArea'] textarea::placeholder,.stTextInput input::placeholder,.stTextArea textarea::placeholder{{color:var(--input-text)!important;-webkit-text-fill-color:var(--input-text)!important;opacity:.62!important}}.stButton>button,button[kind='primary'],[data-testid='stFormSubmitButton'] button{{background:linear-gradient(90deg,#7c3aed,#ef5e7d)!important;color:#fff!important;border:1px solid rgba(255,255,255,.16);border-radius:12px;font-weight:700;min-height:43px;box-shadow:0 8px 18px rgba(95,45,199,.24);transition:.24s}}.stButton>button *,[data-testid='stFormSubmitButton'] button *{{color:#fff!important;-webkit-text-fill-color:#fff!important;opacity:1!important}}.stButton>button:hover,button[kind='primary']:hover{{transform:translateY(-2px);color:#fff!important;background:linear-gradient(135deg,#8e50ef,#f1678c)!important;border-color:rgba(255,255,255,.68);box-shadow:inset 0 1px rgba(255,255,255,.82),0 12px 28px rgba(110,55,220,.32);backdrop-filter:blur(16px)}}[data-testid='stAlert'] p,[data-testid='stAlert'] div{{color:#342447!important;-webkit-text-fill-color:#342447!important;opacity:1!important}}[data-testid='stSidebar'] .stRadio label{{padding:7px 5px;border-radius:10px;background:linear-gradient(145deg,rgba(255,255,255,.1),rgba(145,98,255,.08));border:1px solid rgba(255,255,255,.1)}}
    @media(max-width:900px){{.block-container{{padding:1rem}}.match-grid{{grid-template-columns:1fr}}.top-title{{font-size:1.9rem}}.question-text{{font-size:1.3rem}}}}
    </style>""", unsafe_allow_html=True)


def reset_quiz(mode: str) -> None:
    st.session_state.intake_mode = mode
    st.session_state.intake_index = 0
    st.session_state.intake_answers = {}
    st.session_state.backend_profile = None
    st.session_state.backend_error = ""
    st.session_state.top_matches = []
    st.session_state.career_insights = {}
    st.session_state.score_error = ""
    st.session_state.app_stage = "intake"


def start_personality(mode: str) -> None:
    st.session_state.personality_mode = mode
    st.session_state.personality_index = 0
    st.session_state.personality_answers = {}
    st.session_state.backend_profile = None
    st.session_state.backend_error = ""
    st.session_state.top_matches = []
    st.session_state.career_insights = {}
    st.session_state.score_error = ""
    # Clear old widget values so a new quiz always starts fresh.
    for key in list(st.session_state):
        if key.startswith("radio_p_") or key.startswith("slider_p_"):
            del st.session_state[key]
    st.session_state.app_stage = "personality"


def intake_questions() -> tuple[tuple[str, str], ...]:
    return SHORT_INTAKE if st.session_state.intake_mode == "short" else LONG_INTAKE


def personality_questions() -> tuple[tuple[str, str], ...]:
    return SHORT_RIASEC_QUESTIONS if st.session_state.personality_mode == "riasec_short" else RIASEC_QUESTIONS


def local_riasec_scores() -> dict[str, int]:
    scores = {code: 0 for code in RIASEC}
    for index, (code, _) in enumerate(personality_questions()):
        scores[code] += int(st.session_state.personality_answers.get(f"p_{index}", 3))
    return scores


def intake_theme_scores() -> dict[str, int]:
    """Return lightweight interest signals from completed open-text answers."""
    answers = st.session_state.intake_answers.values()
    combined = " ".join(str(answer).lower() for answer in answers)
    scores: dict[str, int] = {code: 0 for code in RIASEC}
    for code, keywords in INTAKE_THEME_KEYWORDS.items():
        scores[code] = sum(combined.count(keyword) for keyword in keywords)
    return scores


def active_theme_ranking() -> list[str]:
    """Use RIASEC after it is completed; otherwise use the discovery answers."""
    if st.session_state.personality_complete:
        scores = riasec_scores()
    else:
        scores = intake_theme_scores()
    return sorted(scores, key=scores.get, reverse=True)


def dashboard_suitability_score() -> int:
    """Show a career-fit score, never a static quiz-completion percentage."""
    matches = displayed_career_matches()
    if matches:
        raw_score = matches[0].get("score") or matches[0].get("match_score") or matches[0].get("percentage")
        try:
            return max(0, min(100, round(float(str(raw_score).replace("%", "")))))
        except (TypeError, ValueError):
            pass
    return 0


def riasec_scores() -> dict[str, int]:
    """Prefer the scores calculated by FastAPI after the profile is saved."""
    saved_profile = st.session_state.backend_profile or {}
    saved_scores = saved_profile.get("riasec_scores", {}) if isinstance(saved_profile, dict) else {}
    if isinstance(saved_scores, dict) and all(code in saved_scores for code in RIASEC):
        try:
            return {code: int(saved_scores[code]) for code in RIASEC}
        except (TypeError, ValueError):
            pass
    return local_riasec_scores()


def profile_api_url() -> str:
    try:
        return str(st.secrets.get("PROFILE_API_URL", os.getenv("PROFILE_API_URL", DEFAULT_PROFILE_API_URL))).rstrip("/")
    except FileNotFoundError:
        return os.getenv("PROFILE_API_URL", DEFAULT_PROFILE_API_URL).rstrip("/")


def careers_api_url() -> str:
    """URL for the FastAPI route that calls list_careers()."""
    try:
        return str(st.secrets.get("CAREERS_API_URL", os.getenv("CAREERS_API_URL", DEFAULT_CAREERS_API_URL))).rstrip("/")
    except FileNotFoundError:
        return os.getenv("CAREERS_API_URL", DEFAULT_CAREERS_API_URL).rstrip("/")


def chat_api_url() -> str:
    """Base URL for POST /chat and GET /chat/{student_id}."""
    try:
        return str(st.secrets.get("CHAT_API_URL", os.getenv("CHAT_API_URL", DEFAULT_CHAT_API_URL))).rstrip("/")
    except FileNotFoundError:
        return os.getenv("CHAT_API_URL", DEFAULT_CHAT_API_URL).rstrip("/")


def roadmap_api_url() -> str:
    """Base URL for GET /roadmap/{student_id} and its step PATCH endpoint."""
    try:
        return str(st.secrets.get("ROADMAP_API_URL", os.getenv("ROADMAP_API_URL", DEFAULT_ROADMAP_API_URL))).rstrip("/")
    except FileNotFoundError:
        return os.getenv("ROADMAP_API_URL", DEFAULT_ROADMAP_API_URL).rstrip("/")


def score_api_url() -> str:
    """Base URL for POST /score and POST /score/insights."""
    try:
        return str(st.secrets.get("SCORE_API_URL", os.getenv("SCORE_API_URL", DEFAULT_SCORE_API_URL))).rstrip("/")
    except FileNotFoundError:
        return os.getenv("SCORE_API_URL", DEFAULT_SCORE_API_URL).rstrip("/")


def auth_api_url() -> str:
    try:
        return str(st.secrets.get("AUTH_API_URL", os.getenv("AUTH_API_URL", DEFAULT_AUTH_API_URL))).rstrip("/")
    except FileNotFoundError:
        return os.getenv("AUTH_API_URL", DEFAULT_AUTH_API_URL).rstrip("/")


def active_student_id() -> str:
    profile = st.session_state.backend_profile or {}
    return str(profile.get("student_id", ""))


def post_json(url: str, payload: dict[str, object], action: str) -> tuple[dict[str, object] | None, str]:
    request = Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=25) as response:
            data = json.loads(response.read().decode("utf-8"))
        if not isinstance(data, dict):
            return None, f"{action} API did not return an object."
        return data, ""
    except HTTPError as error:
        details = error.read().decode("utf-8", errors="replace")
        return None, f"{action} API rejected the request ({error.code}): {details}"
    except URLError:
        return None, f"Could not reach the {action.lower()} backend at {url}."
    except (OSError, json.JSONDecodeError) as error:
        return None, f"Could not load {action.lower()}: {error}"


def auth_post(endpoint: str, payload: dict[str, str]) -> tuple[dict[str, object] | None, str]:
    return post_json(f"{auth_api_url()}/{endpoint}", payload, "Authentication")


def backend_unavailable(error: str) -> bool:
    """True only for a network failure, never for a rejected password/account."""
    return error.startswith("Could not reach the authentication backend")


def local_demo_account(email: str, name: str = "") -> dict[str, str]:
    """Create a browser-only account for the free public Streamlit demo."""
    accounts = st.session_state.setdefault("local_demo_accounts", {})
    key = email.strip().lower()
    if name:
        account = {
            "student_id": f"demo-{abs(hash(key))}",
            "name": name.strip().title(),
            "email": key,
        }
        accounts[key] = account
        return account
    saved = accounts.get(key)
    return saved if isinstance(saved, dict) else {}


def built_in_mentor_reply(question: str) -> str:
    """Give useful career guidance in the free public app without an LLM/API."""
    text = question.lower()
    careers = career_suggestions()[:3]
    ranked = active_theme_ranking()
    primary = ranked[0]
    strengths = ", ".join(SKILLS_BY_THEME[primary][:3])
    universities = university_recommendations()[:3]
    scholarships = recommended_scholarships()[:3]

    if any(word in text for word in ("scholarship", "financial aid", "funding", "fee", "afford")):
        options = "; ".join(item["name"] for item in scholarships)
        return f"For your current profile, start by checking: {options}. Also visit each university's official financial-aid page, note eligibility and deadlines, and prepare your marksheets, activity list, and income documents early."
    if any(word in text for word in ("university", "universities", "college", "colleges", "campus", "admission", "apply")):
        options = "; ".join(f"{item['name']} ({item['field']})" for item in universities)
        return f"Based on your interests, good places to research first are: {options}. Compare the course curriculum, location, entry requirements, total cost, scholarships, and placement/internship opportunities before applying."
    if any(word in text for word in ("skill", "skills", "learn", "learning", "certification", "certificate", "roadmap")):
        return f"Your strongest direction currently is {RIASEC[primary][0]} work. Build these first: {strengths}. Choose one beginner course, make one small project, and add it to a portfolio or evidence folder. That is more valuable than collecting many certificates without practice."
    if any(word in text for word in ("resume", "cv", "interview", "portfolio", "linkedin")):
        return "Keep your resume to one clear page: education, relevant skills, projects/activities, achievements, and contact details. For interviews, prepare a 30-second introduction and two examples that show a skill, challenge, action, and result. Tailor both to the role you apply for."
    if any(word in text for word in ("course", "degree", "subject", "subjects", "stream", "major", "study")):
        return f"For your profile, explore courses connected to {', '.join(careers)}. Open each course syllabus and look for modules you genuinely enjoy. A good choice balances interest, your current strengths, entry requirements, and the kind of day-to-day work you want."
    if any(word in text for word in ("career", "job", "profession", "work", "role", "future", "coding", "design", "acting", "doctor", "engineer", "business", "psychology", "writer", "artist")):
        return f"Your current profile suggests these paths: {', '.join(careers)}. To choose between them, try one small real activity for each—such as a project, club, shadowing opportunity, short course, or conversation with someone in that field—and notice which work you keep wanting to return to."
    return "I’m here for career and education guidance. Ask me about careers, courses, skills, universities, scholarships, resumes, interviews, or a learning roadmap, and I’ll help you plan the next step."


def fetch_scores_and_insights(student_id: str) -> tuple[list[dict[str, object]], dict[str, object], str]:
    """Calls score_profile, then score_insights so the roadmap is saved."""
    score_response, error = post_json(score_api_url(), {"student_id": student_id}, "Career scoring")
    if error or not score_response:
        return [], {}, error
    matches = score_response.get("top_matches", [])
    if not isinstance(matches, list):
        return [], {}, "Career scoring API did not return top_matches."
    clean_matches = [match for match in matches if isinstance(match, dict)]
    insight_response, insight_error = post_json(
        f"{score_api_url()}/insights",
        {"student_id": student_id, "top_matches": clean_matches},
        "Career insights",
    )
    return clean_matches, insight_response or {}, insight_error


def match_title(match: dict[str, object]) -> str:
    return str(match.get("career") or match.get("career_name") or match.get("name") or match.get("title") or "Career path")


def match_score(match: dict[str, object]) -> str:
    score = match.get("score", match.get("match_score", match.get("suitability_score")))
    if score is None:
        return "Strong match"
    try:
        number = float(score)
        return f"{number:.0f}%" if number <= 100 else f"{number:.0f}"
    except (TypeError, ValueError):
        return str(score)


def send_chat_to_backend(student_id: str, message: str) -> tuple[str, str]:
    """Calls your FastAPI chat(payload: ChatRequest) endpoint."""
    request = Request(
        chat_api_url(),
        data=json.dumps({"student_id": student_id, "message": message}).encode("utf-8"),
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=20) as response:
            payload = json.loads(response.read().decode("utf-8"))
        reply = payload.get("reply")
        if not reply:
            return "", "The chat API did not return a reply."
        return str(reply), ""
    except HTTPError as error:
        details = error.read().decode("utf-8", errors="replace")
        return "", f"Chat backend rejected the message ({error.code}): {details}"
    except URLError:
        return "", f"Could not reach the chat backend at {chat_api_url()}."
    except (OSError, json.JSONDecodeError) as error:
        return "", f"Could not send message: {error}"


@st.cache_data(ttl=15, show_spinner=False)
def load_chat_history(student_id: str, url: str) -> tuple[list[dict[str, object]], str]:
    """Calls GET /chat/{student_id} and normalizes its messages array."""
    request = Request(f"{url}/{student_id}", headers={"Accept": "application/json"}, method="GET")
    try:
        with urlopen(request, timeout=10) as response:
            payload = json.loads(response.read().decode("utf-8"))
        messages = payload.get("messages", [])
        if not isinstance(messages, list):
            return [], "The chat history API did not return a messages list."
        return [message for message in messages if isinstance(message, dict)], ""
    except HTTPError as error:
        return [], f"Could not load chat history ({error.code})."
    except URLError:
        return [], f"Could not reach the chat backend at {url}."
    except (OSError, json.JSONDecodeError) as error:
        return [], f"Could not load chat history: {error}"


def chat_message_text(message: dict[str, object]) -> str:
    return str(message.get("message") or message.get("content") or message.get("text") or "")


def chat_message_role(message: dict[str, object]) -> str:
    role = str(message.get("role") or message.get("sender") or "ai").lower()
    return "student" if role in {"student", "user"} else "ai"


@st.cache_data(ttl=15, show_spinner=False)
def load_roadmap(student_id: str, url: str) -> tuple[list[dict[str, object]], str]:
    """Calls GET /roadmap/{student_id} and returns the saved roadmap steps."""
    request = Request(f"{url}/{student_id}", headers={"Accept": "application/json"}, method="GET")
    try:
        with urlopen(request, timeout=10) as response:
            payload = json.loads(response.read().decode("utf-8"))
        steps = payload.get("steps", [])
        if not isinstance(steps, list):
            return [], "The roadmap API did not return a steps list."
        return [step for step in steps if isinstance(step, dict)], ""
    except HTTPError as error:
        return [], f"Could not load your roadmap ({error.code})."
    except URLError:
        return [], f"Could not reach the roadmap backend at {url}."
    except (OSError, json.JSONDecodeError) as error:
        return [], f"Could not load roadmap: {error}"


def roadmap_step_id(step: dict[str, object]) -> int | None:
    value = step.get("step_id", step.get("id"))
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def roadmap_step_title(step: dict[str, object], position: int) -> str:
    return str(step.get("title") or step.get("name") or step.get("step") or f"Roadmap step {position}")


def update_roadmap_step(student_id: str, step_id: int, completed: bool) -> str:
    """Calls PATCH /roadmap/{student_id}/steps/{step_id}."""
    request = Request(
        f"{roadmap_api_url()}/{student_id}/steps/{step_id}",
        data=json.dumps({"completed": completed}).encode("utf-8"),
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="PATCH",
    )
    try:
        with urlopen(request, timeout=10):
            return ""
    except HTTPError as error:
        details = error.read().decode("utf-8", errors="replace")
        return f"Could not update this step ({error.code}): {details}"
    except URLError:
        return f"Could not reach the roadmap backend at {roadmap_api_url()}."
    except OSError as error:
        return f"Could not update roadmap: {error}"


@st.cache_data(ttl=60, show_spinner=False)
def load_careers_from_backend(url: str) -> tuple[list[dict[str, object]], str]:
    """Fetches GET /careers, which should return db.get_all_careers()."""
    request = Request(url, headers={"Accept": "application/json"}, method="GET")
    try:
        with urlopen(request, timeout=8) as response:
            careers = json.loads(response.read().decode("utf-8"))
        if not isinstance(careers, list):
            return [], "The careers API did not return a list."
        return [career for career in careers if isinstance(career, dict)], ""
    except HTTPError as error:
        return [], f"Career API returned {error.code}."
    except URLError:
        return [], f"Could not reach the careers backend at {url}."
    except (OSError, json.JSONDecodeError) as error:
        return [], f"Could not load careers: {error}"


def career_title(career: dict[str, object]) -> str:
    """Supports common database field names without breaking the UI."""
    for key in ("name", "title", "career_name", "role"):
        value = career.get(key)
        if value:
            return str(value)
    return "Career path"


def career_description(career: dict[str, object]) -> str:
    for key in ("description", "summary", "about", "overview"):
        value = career.get(key)
        if value:
            return str(value)
    return "Explore this career path, its required skills, and study options."


def intake_answers_by_section() -> dict[str, list[str]]:
    grouped: dict[str, list[str]] = {}
    for index, (section, _) in enumerate(intake_questions()):
        answer = st.session_state.intake_answers.get(f"intake_{index}", "").strip()
        if answer:
            grouped.setdefault(section, []).append(answer)
    return grouped


def build_profile_payload() -> dict[str, object]:
    """Build the exact fields consumed by the ProfileIntake backend model."""
    grouped = intake_answers_by_section()
    # Backend scores two ratings per theme in R, I, A, S, E, C order.
    # For the 60-question UI, average the ten ratings per theme and repeat it
    # twice; for quick mode, it simply preserves the two chosen ratings.
    answers_by_theme: dict[str, list[int]] = {code: [] for code in RIASEC}
    for index, (code, _) in enumerate(personality_questions()):
        answers_by_theme[code].append(int(st.session_state.personality_answers.get(f"p_{index}", 3)))
    riasec_answers = [
        rating
        for code in RIASEC
        for rating in (
            answers_by_theme[code][:2]
            if st.session_state.personality_mode == "riasec_short"
            else [round(sum(answers_by_theme[code]) / len(answers_by_theme[code]))] * 2
        )
    ]
    return {
        "name": st.session_state.student_name.strip(),
        "email": st.session_state.student_email.strip(),
        "interests": grouped.get("Interests & passions", []),
        "hobbies": grouped.get("Hobbies & activities", []),
        # The current UI collects written answers, so these remain empty until
        # numeric subject marks/skill ratings are added to the quiz.
        "academics": {},
        "self_rated_skills": {},
        "riasec_answers": riasec_answers,
    }


def save_profile_to_backend() -> tuple[dict[str, object] | None, str]:
    """POST the quiz profile to FastAPI's create_profile endpoint."""
    if not st.session_state.student_name.strip():
        return None, "Please enter your name in the first career-quiz question."
    if not st.session_state.student_email.strip():
        return None, "Please enter an email address in the first career-quiz question."
    payload = build_profile_payload()
    request = Request(
        profile_api_url(),
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=10) as response:
            return json.loads(response.read().decode("utf-8")), ""
    except HTTPError as error:
        details = error.read().decode("utf-8", errors="replace")
        return None, f"Backend rejected the profile ({error.code}): {details}"
    except URLError:
        return None, f"Could not reach the profile backend at {profile_api_url()}."
    except (OSError, json.JSONDecodeError) as error:
        return None, f"Could not save the profile: {error}"


def career_suggestions() -> tuple[str, ...]:
    ranked = active_theme_ranking()
    code = "".join(ranked[:2])
    theme_careers = CAREER_MAP.get(code) or CAREER_MAP.get(code[::-1]) or CAREER_MAP[ranked[0]]
    written_answers = " ".join(str(answer).lower() for answer in st.session_state.intake_answers.values())
    direct: list[str] = []
    # Check longest phrases first so "social work" is not lost inside another match.
    for keyword in sorted(DIRECT_CAREER_KEYWORDS, key=len, reverse=True):
        if re.search(rf"(?<!\w){re.escape(keyword)}(?!\w)", written_answers):
            direct.extend(DIRECT_CAREER_KEYWORDS[keyword])
    # Do not show unexplained defaults ahead of explicitly written interests.
    return tuple(dict.fromkeys(direct + list(theme_careers)))


def relevant_career_results() -> tuple[dict[str, object], ...]:
    """Create broad, theme-based results from the full UI career map.

    The backend seed currently has only six careers, whereas the UI has many
    more career paths. These results preserve the student's RIASEC direction
    instead of letting the small seed list dominate the dashboard.
    """
    ranked = active_theme_ranking()
    primary, secondary = ranked[:2]
    careers = career_suggestions()[:5]
    written_answers = " ".join(str(answer).lower() for answer in st.session_state.intake_answers.values())
    results: list[dict[str, object]] = []
    for position, career in enumerate(careers):
        themes = CAREER_THEME_CODES.get(career, (primary,))
        direct_match = any(career in options and re.search(rf"(?<!\w){re.escape(keyword)}(?!\w)", written_answers) for keyword, options in DIRECT_CAREER_KEYWORDS.items())
        alignment = 97 if direct_match else 94 if primary in themes and secondary in themes else 90 if primary in themes else 78
        results.append({
            "career": career,
            "score": max(60, alignment - position * 3),
            "reason": "Directly matches an interest you wrote in your quiz." if direct_match else f"Matches your strongest themes: {RIASEC[primary][0]} and {RIASEC[secondary][0]}.",
        })
    return tuple(results)


def displayed_career_matches() -> tuple[dict[str, object], ...]:
    """Prefer a broad local result set if backend results are too limited."""
    local = relevant_career_results()
    backend = tuple(st.session_state.top_matches)
    if not backend:
        return local
    # Backend careers are reliable for score breakdown, but only six are
    # seeded. Keep the broader local ordering, replacing a local card only
    # when the backend contains that same relevant career.
    by_name: dict[str, dict[str, object]] = {match_title(match): match for match in backend}
    return tuple(by_name.get(match_title(local_match), local_match) for local_match in local)


def personalized_roadmap_steps() -> tuple[dict[str, object], ...]:
    """Useful non-random fallback steps when the backend roadmap is unavailable."""
    ranked = active_theme_ranking()
    first, second = ranked[:2]
    careers = career_suggestions()[:3]
    return (
        {"id": 1, "title": f"Explore {RIASEC[first][0]} careers", "description": f"Compare {', '.join(careers)} and note the entry requirements.", "completed": False},
        {"id": 2, "title": f"Build {RIASEC[first][0]} strengths", "description": f"Start with {', '.join(SKILLS_BY_THEME[first][:2])}.", "completed": False},
        {"id": 3, "title": f"Add {RIASEC[second][0]} experience", "description": f"Try {SKILLS_BY_THEME[second][2]} through a club, course, project, or internship.", "completed": False},
        {"id": 4, "title": "Create a career evidence folder", "description": "Save projects, certificates, reflections, and achievements for your preferred career paths.", "completed": False},
    )


def university_recommendations() -> tuple[dict[str, str], ...]:
    """Match university fields to the student's strongest RIASEC themes."""
    ranked = active_theme_ranking()
    # Keep the ranking order: using a set here made equally rated themes appear
    # in an unpredictable order and led to the same three default suggestions.
    themes = tuple(RIASEC[code][0] for code in ranked[:2])
    field_keywords = {
        "Realistic": ("Engineering", "Skilled Trades", "Manufacturing", "Transportation", "Energy", "Agriculture"),
        "Investigative": ("Technology", "Engineering", "Healthcare", "Science", "Environment", "Emerging"),
        "Artistic": ("Arts", "Media", "Writing", "Beauty", "Skilled Craft"),
        "Social": ("Healthcare", "Education", "Social Services", "Hospitality", "Sports"),
        "Enterprising": ("Business", "Marketing", "Law", "Government", "Real Estate", "Retail", "Freelance"),
        "Conventional": ("Business", "Technology", "Manufacturing", "Transportation", "Retail"),
    }
    written_answers = " ".join(str(answer).lower() for answer in st.session_state.intake_answers.values())
    preferred_countries = {
        "us": "USA", "usa": "USA", "united states": "USA", "uk": "UK", "united kingdom": "UK",
        "india": "India", "canada": "Canada", "australia": "Australia", "germany": "Germany",
        "singapore": "Singapore", "japan": "Japan", "france": "France", "switzerland": "Switzerland",
    }
    country_choices = tuple(country for phrase, country in preferred_countries.items() if re.search(rf"(?<!\w){re.escape(phrase)}(?!\w)", written_answers))
    direct_fields = [
        field for keyword, fields in CAREER_FIELD_SIGNALS.items()
        if re.search(rf"(?<!\w){re.escape(keyword)}(?!\w)", written_answers)
        for field in fields
    ]
    theme_fields = [field for theme in themes for field in field_keywords[theme]]
    preferred_fields = tuple(dict.fromkeys(direct_fields + theme_fields))

    def field_score(university: dict[str, str]) -> int:
        field = university["field"].lower()
        subject_score = sum(4 if signal in direct_fields else 1 for signal in preferred_fields if signal.lower() in field)
        country_score = 8 if university["country"] in country_choices else 0
        return country_score + subject_score

    ranked_matches = sorted(UNIVERSITY_CATALOG, key=field_score, reverse=True)
    return tuple((ranked_matches or list(UNIVERSITY_CATALOG))[:3])


def recommendation_career_text() -> str:
    """Relevant career names are additional evidence for courses and funding."""
    return " ".join(match_title(match).lower() for match in displayed_career_matches())


def recommended_scholarships() -> tuple[dict[str, str], ...]:
    """Rank scholarships against the student's matched careers and profile themes."""
    ranked = active_theme_ranking()
    themes = " ".join(RIASEC[code][0].lower() for code in ranked[:2])
    context = recommendation_career_text() + " " + themes + " " + " ".join(
        str(answer).lower() for answer in st.session_state.intake_answers.values()
    )
    scholarship_signals = {
        "stem": ("coding", "software", "data", "ai", "robot", "engineering", "science", "environment"),
        "arts": ("acting", "actor", "theatre", "film", "music", "dance", "fashion", "photography", "animation", "design", "writing"),
        "health": ("doctor", "medicine", "nurse", "psychology", "therapy"),
        "business": ("business", "entrepreneur", "marketing", "finance", "accounting"),
        "law": ("law", "lawyer", "politics"),
        "sports": ("sports", "cricket"),
        "education": ("teacher", "education", "social work"),
    }
    keywords = tuple(
        label for label, triggers in scholarship_signals.items()
        if any(re.search(rf"(?<!\w){re.escape(trigger)}(?!\w)", context) for trigger in triggers)
    )
    university_aid = [
        {
            "name": f"{university['name']} financial aid",
            "funded_by": university["name"],
            "coverage": university["scholarships"],
            "best_for": f"{university['field']} · {university['country']}",
        }
        for university in university_recommendations()
    ]
    if not keywords:
        return tuple(university_aid + list(SCHOLARSHIP_CATALOG[:2]))
    ranked_scholarships = sorted(
        SCHOLARSHIP_CATALOG,
        key=lambda scholarship: sum(keyword in " ".join(scholarship.values()).lower() for keyword in keywords),
        reverse=True,
    )
    # Pair subject-aligned university aid with broader external scholarships.
    return tuple((university_aid + ranked_scholarships)[:5])


def university_recommendation_reason() -> str:
    """Explain the exact profile signal used for the university cards."""
    ranked = active_theme_ranking()
    top_themes = " and ".join(RIASEC[code][0] for code in ranked[:2])
    if st.session_state.personality_complete:
        return f"Matched to your strongest RIASEC themes: {top_themes}."
    if any(intake_theme_scores().values()):
        return f"Matched to interests in your written career-quiz answers: {top_themes}. Complete RIASEC to refine this further."
    return "Complete the career quiz to receive recommendations based on your own answers."


def profile_name() -> str:
    return st.session_state.student_name or "Student"


def is_valid_email(email: str) -> bool:
    """Validates a realistic email format before the app accepts it."""
    pattern = r"^[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?)+$"
    return bool(re.fullmatch(pattern, email.strip()))


def is_meaningful_answer(answer: str) -> bool:
    """Reject blank/placeholders while allowing brief factual quiz answers."""
    cleaned = answer.strip().lower()
    compact = re.sub(r"\s+", "", cleaned)
    letters = re.sub(r"[^a-z]", "", cleaned)
    blocked = {"asdf", "asdfgh", "qwerty", "qwertyuiop", "test", "testing", "none", "na", "n/a", "idk", "xxx", "abc", "abcd"}
    if not cleaned or cleaned in blocked:
        return False
    # Many profile questions genuinely need concise factual responses.
    if cleaned in {"yes", "no", "y", "n", "true", "false", "maybe"}:
        return True
    if re.fullmatch(r"[+-]?\d+(?:\.\d+)?\s*%?", cleaned):
        return True
    # Short country abbreviations (US, UK, UAE, etc.) are valid answers to
    # the university-location question. The repeated-letter check still blocks
    # obvious placeholders such as "aaa".
    if re.fullmatch(r"[a-z]{2,3}", cleaned):
        return True
    if len(cleaned) < 3 or (letters and len(set(letters)) == 1):
        return False
    if len(letters) < 2:
        return False
    return True


def render_theme_toggle() -> None:
    _, col = st.columns([5, 1])
    with col:
        label = "🌙 Dark mode" if st.session_state.light_mode else "☀️ Light mode"
        if st.button(label, key="theme_mode_button", use_container_width=True):
            st.session_state.light_mode = not st.session_state.light_mode
            st.rerun()


def render_login() -> None:
    render_theme_toggle()
    left, right = st.columns([.92, 1.08], gap="large")
    with left:
        creating_account = st.session_state.auth_mode == "create"
        st.image(LOGO_PATH, width=86)
        heading = "Create your account" if creating_account else "Welcome back"
        subtitle = "Start exploring your future." if creating_account else "Log in to continue your career journey."
        st.markdown(f"<div class='panel'><div class='brand'><div class='brand-name'>Career <span>AI</span></div></div><h1 class='top-title'>{heading}</h1><p class='top-subtitle'>{subtitle}</p>", unsafe_allow_html=True)
        email = st.text_input("Email address", placeholder="you@example.com", key="email_input")
        display_name = ""
        if creating_account:
            display_name = st.text_input("What should we call you?", placeholder="Enter your name", key="name_input")
        password = st.text_input("Password", placeholder="Enter your password", type="password", key="password_input")
        if creating_account:
            st.caption("Create your own password.")
        st.checkbox("Remember me")
        submit_label = "Create account  →" if creating_account else "Log in  →"
        if st.button(submit_label, use_container_width=True):
            clean_email = email.strip()
            if not is_valid_email(clean_email):
                st.error("Please enter a valid email address, for example you@example.com.")
            elif not password:
                st.error("Please enter your password.")
            elif creating_account and not display_name.strip():
                st.error("Please enter the name you would like us to use.")
            elif creating_account and len(password) < 8:
                st.error("Your password must contain at least 8 characters.")
            else:
                endpoint = "register" if creating_account else "login"
                payload = {"email": clean_email, "password": password}
                if creating_account:
                    payload["name"] = display_name.strip().title()
                with st.spinner("Setting up your account…"):
                    account, error = auth_post(endpoint, payload)
                if error and backend_unavailable(error):
                    # Streamlit Community Cloud cannot call a server on the
                    # developer's laptop.  Keep the public demo useful even
                    # before an online API is deployed.
                    if creating_account:
                        account = local_demo_account(clean_email, display_name)
                        st.info("Free demo mode: your account works in this browser. Your quiz results stay private to this session.")
                    else:
                        account = local_demo_account(clean_email)
                        if not account:
                            st.error("No browser-only demo account was found for this email. Please create an account first.")
                elif error:
                    st.error(error)

                if account:
                    st.session_state.student_name = str(account["name"])
                    st.session_state.student_email = str(account["email"])
                    student_id = account.get("student_id")
                    if student_id:
                        st.session_state.backend_profile = {
                            "student_id": str(student_id),
                            "name": st.session_state.student_name,
                            "email": st.session_state.student_email,
                        }
                    # New accounts take the quiz; login can resume the dashboard.
                    st.session_state.app_stage = "welcome" if creating_account else "dashboard"
                    st.rerun()
        switch_label = "Already have an account? Log in" if creating_account else "New to Career AI? Create an account"
        if st.button(switch_label, use_container_width=True, key="switch_auth_mode"):
            st.session_state.auth_mode = "login" if creating_account else "create"
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)
    with right:
        st.markdown("""
        <div class='login-visual'>
          <div class='login-orbit'></div>
          <div class='float-career career-1'>🩺</div>
          <div class='float-career career-2'>💻</div>
          <div class='float-career career-3'>🏏</div>
          <div class='float-career career-4'>🎓</div>
          <div class='float-career career-5'>🎨</div>
          <div class='float-career career-6'>🔬</div>
          <div class='login-message'>Every interest<br>can become a <span>future.</span></div>
        </div>
        """, unsafe_allow_html=True)


def render_welcome() -> None:
    render_theme_toggle()
    st.markdown(f"<div class='top-title'>Hello, {escape(profile_name())}! 👋</div><div class='top-subtitle'>Let’s start by learning what matters to you.</div>", unsafe_allow_html=True)
    st.markdown(f"<div class='panel' style='text-align:center;max-width:900px;margin:0 auto 23px'><div class='butterfly-mark' style='font-size:2.3rem'>🦋</div><h2>“{random.choice(QUOTES)}”</h2><p class='muted'>Choose a quiz length. You can pause and return during this browser session.</p></div>", unsafe_allow_html=True)
    short, long = st.columns(2, gap="large")
    with short:
        st.markdown("<div class='choice-card'><div class='choice-icon'>⚡</div><h2>Quick Career Quiz</h2><p class='muted'>11 thoughtful questions — one from each important area. Great for a fast first recommendation.</p><p class='accent'>About 8–10 minutes</p></div>", unsafe_allow_html=True)
        st.button("Start quick quiz  →", use_container_width=True, on_click=reset_quiz, args=("short",))
    with long:
        st.markdown("<div class='choice-card'><div class='choice-icon'>🧭</div><h2>Complete Career Quiz</h2><p class='muted'>The full question bank covering academics, interests, skills, preferences, finances, and support needs.</p><p class='accent'>About 30–40 minutes</p></div>", unsafe_allow_html=True)
        st.button("Start complete quiz  →", use_container_width=True, on_click=reset_quiz, args=("long",))


def render_intake() -> None:
    render_theme_toggle()
    questions = intake_questions()
    index = st.session_state.intake_index
    section, prompt = questions[index]
    percent = round((index + 1) * 100 / len(questions))
    st.markdown(f"<div class='top-title'>Career Discovery Quiz</div><div class='top-subtitle'>{'Quick' if st.session_state.intake_mode == 'short' else 'Complete'} version · Answer honestly — there are no right answers.</div><div class='quiz-step'>{section}</div><div class='progress-shell'><div class='progress-fill' style='width:{percent}%'></div></div>", unsafe_allow_html=True)
    st.markdown(f"<div class='question-card'><div class='question-number'>QUESTION {index + 1} OF {len(questions)}</div><div class='question-text'>{escape(prompt)}</div>", unsafe_allow_html=True)
    quiz_name = st.session_state.student_name
    quiz_email = st.session_state.student_email
    if index == 0:
        quiz_name = st.text_input(
            "What should we call you?",
            value=st.session_state.student_name,
            placeholder="Enter your name",
            key="quiz_display_name",
        )
        quiz_email = st.text_input(
            "Email address",
            value=st.session_state.student_email,
            placeholder="you@example.com",
            key="quiz_email",
        )
    key = f"intake_{index}"
    answer = st.text_area("Your answer", value=st.session_state.intake_answers.get(key, ""), placeholder="Write your answer here…", height=175, key=f"widget_{key}")
    st.markdown("</div>", unsafe_allow_html=True)
    previous, spacer, next_col = st.columns([1, 2, 1])
    with previous:
        if index and st.button("← Previous", use_container_width=True):
            st.session_state.intake_answers[key] = answer
            st.session_state.intake_index -= 1
            st.rerun()
    with next_col:
        next_label = "Finish quiz  →" if index == len(questions) - 1 else "Next question  →"
        if st.button(next_label, use_container_width=True):
            if not is_meaningful_answer(answer):
                st.error("Please enter a real answer. Short answers such as yes/no, a score like 85, or 92% are accepted; placeholders like “asdf” are not.")
                return
            if index == 0:
                if not quiz_name.strip():
                    st.error("Please enter the name you would like us to use.")
                    return
                if not is_valid_email(quiz_email):
                    st.error("Please enter a valid email address, for example you@example.com.")
                    return
                st.session_state.student_name = quiz_name.strip().title()
                st.session_state.student_email = quiz_email.strip()
            st.session_state.intake_answers[key] = answer.strip()
            if index == len(questions) - 1:
                st.session_state.app_stage = "intake_results"
            else:
                st.session_state.intake_index += 1
            st.rerun()


def render_intake_results() -> None:
    render_theme_toggle()
    answered = sum(bool(value.strip()) for value in st.session_state.intake_answers.values())
    total = len(intake_questions())
    st.markdown("<div class='top-title'>Your Career Profile is Ready</div><div class='top-subtitle'>Here is your first overall summary. Complete a personality quiz next for a deeper career-fit view.</div>", unsafe_allow_html=True)
    stat1, stat2, stat3 = st.columns(3)
    for col, icon, number, label in ((stat1, "🦋", f"{answered}/{total}", "Questions answered"), (stat2, "🧭", "Career profile", "Saved in this session"), (stat3, "🧠", "Next: personality", "Refine your matches")):
        with col: st.markdown(f"<div class='panel' style='text-align:center'><div class='icon-bubble' style='margin:auto'>{icon}</div><div class='result-number'>{number}</div><p class='muted'>{label}</p></div>", unsafe_allow_html=True)
    st.markdown("<h2 style='margin-top:28px'>Refine your results with a RIASEC personality quiz</h2><p class='muted'>Choose one version. Both provide a Holland Code and career-family suggestions.</p>", unsafe_allow_html=True)
    short, long = st.columns(2, gap="large")
    with short:
        st.markdown("<div class='choice-card'><div class='choice-icon'>⚡</div><h2>Quick RIASEC Quiz</h2><p class='muted'>12 short statements — two for each career-interest theme. Get a fast career-direction summary.</p><p class='accent'>About 3–5 minutes</p></div>", unsafe_allow_html=True)
        st.button("Start quick RIASEC quiz  →", use_container_width=True, on_click=start_personality, args=("riasec_short",))
    with long:
        st.markdown("<div class='choice-card'><div class='choice-icon'>🧠</div><h2>Full RIASEC Quiz</h2><p class='muted'>60 statements measuring Realistic, Investigative, Artistic, Social, Enterprising, and Conventional themes.</p><p class='accent'>About 15–20 minutes</p></div>", unsafe_allow_html=True)
        st.button("Start full personality quiz  →", use_container_width=True, on_click=start_personality, args=("riasec_long",))
    if st.button("Skip for now and open dashboard", use_container_width=True):
        st.session_state.app_stage = "dashboard"
        st.rerun()


def render_personality() -> None:
    render_theme_toggle()
    questions = personality_questions()
    index = st.session_state.personality_index
    code, statement = questions[index]
    name, icon, _ = RIASEC[code]
    value_key = f"p_{index}"
    quiz_title = "Quick RIASEC Personality Quiz" if st.session_state.personality_mode == "riasec_short" else "Full RIASEC Personality Quiz"
    st.markdown(f"<div class='top-title'>{quiz_title}</div><div class='top-subtitle'>Rate each statement based on how you actually feel. 1 = strongly disagree · 5 = strongly agree.</div><div class='progress-shell'><div class='progress-fill' style='width:{round((index+1)*100/len(questions))}%'></div></div>", unsafe_allow_html=True)
    st.markdown(f"<div class='question-card'><div class='question-number'>{icon} {name.upper()} · QUESTION {index+1} OF {len(questions)}</div><div class='question-text'>{escape(statement)}</div>", unsafe_allow_html=True)
    saved_value = st.session_state.personality_answers.get(value_key)
    value = st.radio("Your rating", (1, 2, 3, 4, 5), index=int(saved_value) - 1 if saved_value else None, horizontal=True, format_func=lambda number: {1:"1 · Strongly disagree",2:"2 · Disagree",3:"3 · Neutral",4:"4 · Agree",5:"5 · Strongly agree"}[number], key=f"radio_{value_key}")
    st.markdown("</div>", unsafe_allow_html=True)
    previous, _, next_col = st.columns([1, 2, 1])
    with previous:
        if index and st.button("← Previous", use_container_width=True, key="personality_previous"):
            st.session_state.personality_answers[value_key] = value
            st.session_state.personality_index -= 1
            st.rerun()
    with next_col:
        final = index == len(questions) - 1
        if st.button("See results  →" if final else "Next question  →", use_container_width=True, key="personality_next"):
            if value is None:
                st.error("Please select a rating before continuing.")
                return
            st.session_state.personality_answers[value_key] = value
            if final:
                st.session_state.personality_complete = True
                with st.spinner("Saving your profile and generating recommendations…"):
                    saved_profile, error = save_profile_to_backend()
                st.session_state.backend_profile = saved_profile
                st.session_state.backend_error = error
                student_id = str((saved_profile or {}).get("student_id", ""))
                if student_id:
                    with st.spinner("Finding your strongest career matches…"):
                        matches, insights, score_error = fetch_scores_and_insights(student_id)
                    st.session_state.top_matches = matches
                    st.session_state.career_insights = insights
                    st.session_state.score_error = score_error
                st.session_state.app_stage = "personality_results"
            else:
                st.session_state.personality_index += 1
            st.rerun()


def render_personality_results() -> None:
    render_theme_toggle()
    scores = riasec_scores()
    ranked = sorted(scores, key=scores.get, reverse=True)
    code = "".join(ranked[:2])
    scored_matches = displayed_career_matches()
    suggestions = tuple(match_title(match) for match in scored_matches[:3]) or career_suggestions()
    max_score = 10 if st.session_state.personality_mode == "riasec_short" else 50
    summary_title = "Your Quick RIASEC Career Profile" if st.session_state.personality_mode == "riasec_short" else "Your RIASEC Career Profile"
    st.markdown(f"<div class='top-title'>{summary_title}</div><div class='top-subtitle'>Your strongest themes point to work environments and career families that may feel naturally engaging.</div>", unsafe_allow_html=True)
    saved_profile = st.session_state.backend_profile or {}
    if saved_profile.get("student_id"):
        st.success(f"Profile saved successfully · Student ID: {saved_profile['student_id']}")
    elif st.session_state.backend_error:
        st.warning(f"Your on-screen summary is ready, but it was not saved to the backend. {st.session_state.backend_error}")
    if st.session_state.score_error:
        st.warning(f"Your local results are shown below. {st.session_state.score_error}")
    st.markdown(f"<div class='panel' style='text-align:center;max-width:780px;margin:0 auto 22px'><div class='result-code'>{code}</div><h2>{RIASEC[ranked[0]][1]} {RIASEC[ranked[0]][0]} + {RIASEC[ranked[1]][1]} {RIASEC[ranked[1]][0]}</h2><p class='muted'>Your Holland Code is a starting point for exploration, not a final decision.</p></div>", unsafe_allow_html=True)
    score_cols = st.columns(3)
    for col, type_code in zip(score_cols, ranked[:3]):
        with col:
            name, icon, _ = RIASEC[type_code]
            st.markdown(f"<div class='panel' style='text-align:center'><div class='icon-bubble' style='margin:auto'>{icon}</div><h3>{name}</h3><div class='result-number'>{scores[type_code]}/{max_score}</div></div>", unsafe_allow_html=True)
    st.markdown("<h2 style='margin-top:28px'>Career families to explore</h2>", unsafe_allow_html=True)
    if scored_matches:
        cards = "".join(
            f"<div class='match-card'><span class='match-pill'>{escape(match_score(match))}</span><div class='icon-bubble butterfly-mark'>🦋</div><h3>{escape(match_title(match))}</h3><p class='muted'>{escape(str(match.get('reason') or match.get('description') or 'A strong match based on your profile.'))}</p></div>"
            for match in scored_matches[:3]
        )
    else:
        cards = "".join(f"<div class='match-card'><div class='icon-bubble butterfly-mark'>🦋</div><h3>{escape(career)}</h3><p class='muted'>Explore courses, skills, and university paths related to this direction.</p></div>" for career in suggestions)
    st.markdown("<div class='match-grid'>" + cards + "</div>", unsafe_allow_html=True)
    insights = st.session_state.career_insights
    insight_items = insights.get("insights") or insights.get("recommendations") or insights.get("key_insights") or []
    if isinstance(insight_items, list) and insight_items:
        st.markdown("<h2 style='margin-top:28px'>Your AI insights</h2>", unsafe_allow_html=True)
        st.markdown("<div class='panel'>" + "".join(f"<p>🦋 {escape(str(item))}</p>" for item in insight_items[:4]) + "</div>", unsafe_allow_html=True)
    if st.button("Open my dashboard  →", use_container_width=True):
        st.session_state.app_stage = "dashboard"
        st.rerun()


def render_sidebar() -> str:
    with st.sidebar:
        logo_col, name_col = st.columns([.3, .7], gap="small")
        with logo_col: st.image(LOGO_PATH, width=62)
        with name_col: st.markdown("<div style='padding-top:3px'><div class='brand-name'>Career <span>AI</span></div><div class='sidebar-tagline'>Your AI Career Mentor</div></div>", unsafe_allow_html=True)
        st.markdown("---")
        page = st.radio("Navigation", PAGES, format_func=lambda p: f"{PAGE_ICONS[p]}  {p}", key="nav_page", label_visibility="collapsed")
        st.markdown("---")
        if st.button("Log out", use_container_width=True):
            log_out()
            st.rerun()
    return page


def render_dashboard() -> None:
    st.markdown(f"<div class='top-title'>Hello, {escape(profile_name())} 👋</div><div class='top-subtitle'>Here is your growing career profile.</div>", unsafe_allow_html=True)
    if st.session_state.backend_profile and st.session_state.backend_profile.get("student_id"):
        st.caption(f"Profile connected · ID: {st.session_state.backend_profile['student_id']}")
    live_careers, _ = load_careers_from_backend(careers_api_url())
    scored_matches = displayed_career_matches()
    # Before RIASEC scoring, prioritise the student's discovery answers over
    # the backend's generic catalogue order. Once scored, backend matches win.
    local_suggestions = career_suggestions()
    generic_backend_suggestions = tuple(career_title(career) for career in live_careers[:3])
    suggested = (
        tuple(match_title(match) for match in scored_matches[:3])
        or (local_suggestions if not st.session_state.personality_complete else generic_backend_suggestions)
        or generic_backend_suggestions
        or local_suggestions
    )
    score, matches, mentor = st.columns([1, 1.45, .7], gap="medium")
    suitability_score = dashboard_suitability_score()
    score_message = "Your strongest current career match" if not st.session_state.personality_complete else "Your profile has a strong direction!"
    score_detail = "Calculated from your written quiz interests. Complete RIASEC to refine it further." if not st.session_state.personality_complete else "Based on your RIASEC profile and quiz interests."
    with score: st.markdown(f"<div class='score-panel'><h3>Career Suitability Score</h3><div class='big-score'>{suitability_score}%</div><b>{score_message}</b><p>{score_detail}</p></div>", unsafe_allow_html=True)
    with matches:
        match_cards = "".join(
            f"<div class='match-card'><span class='match-pill'>{escape(match_score(match))}</span><div class='icon-bubble butterfly-mark'>🦋</div><h3>{escape(match_title(match))}</h3><p class='muted'>{escape(str(match.get('reason') or 'A promising direction based on your profile.'))}</p></div>"
            for match in scored_matches[:3]
        ) if scored_matches else "".join(f"<div class='match-card'><span class='match-pill'>Profile signal</span><div class='icon-bubble butterfly-mark'>🦋</div><h3>{escape(career)}</h3><p class='muted'>Suggested from the interests in your written quiz answers.</p></div>" for career in suggested)
        st.markdown("<div class='panel'><span class='accent' style='float:right'>View all →</span><h3>Top Career Matches</h3><div class='match-grid'>" + match_cards + "</div></div>", unsafe_allow_html=True)
    with mentor:
        with st.container(border=True, key="ai_mentor_card"):
            st.markdown("### AI Mentor")
            _, logo, _ = st.columns([1, 1.4, 1])
            with logo: st.image(LOGO_PATH, use_container_width=True)
            st.markdown("**Ask your AI Mentor**")
            st.caption("Career and education guidance whenever you need it.")
            if st.button("Start a conversation", use_container_width=True): st.session_state.nav_page = "AI Mentor"; st.rerun()
    universities = university_recommendations()
    scholarships = recommended_scholarships()
    left, middle, right = st.columns(3, gap="medium")
    with left:
        university_rows = "".join(
            f"<p class='muted'>{escape(university['name'])} <span class='mint'>· {escape(university['field'])}</span></p>"
            for university in universities
        )
        st.markdown("<div class='panel'><h3>🎓 Top Universities for You</h3>" + university_rows + "</div>", unsafe_allow_html=True)
    with middle:
        scholarship_rows = "".join(f"<p class='muted'>{escape(item['name'])}<br><span class='mint'>{escape(item['best_for'])}</span></p>" for item in scholarships)
        st.markdown("<div class='panel'><h3>🦋 Scholarships for You</h3>" + scholarship_rows + "</div>", unsafe_allow_html=True)
    with right: st.markdown("<div class='panel'><h3>🦋 Your Learning Roadmap</h3><p class='mint'>● Self discovery</p><p class='muted'>○ Career exploration</p><p class='muted'>○ Skill building</p><p class='muted'>○ Real-world preparation</p></div>", unsafe_allow_html=True)


def render_ai_mentor() -> None:
    st.markdown("<div class='top-title'>AI Mentor</div><div class='top-subtitle'>Career and education guidance only.</div><div class='ai-card'><h3>Ask a career-focused question</h3><p>I can help with careers, skills, courses, universities, scholarships, and internships. For unrelated topics, I’ll politely guide you back.</p></div>", unsafe_allow_html=True)
    student_id = active_student_id()
    if not student_id:
        st.info("Finish the profile and RIASEC quiz for more personalised suggestions.")
    messages: list[dict[str, object]] = []
    if student_id:
        messages, history_error = load_chat_history(student_id, chat_api_url())
        if history_error:
            st.warning(history_error)
    with st.form("mentor_form", clear_on_submit=True):
        question = st.text_input("Ask your question", placeholder="Which skills should I build for UX design?")
        asked = st.form_submit_button("Ask AI Mentor  →", use_container_width=True)
    if asked and question.strip():
        career_words = ("career", "job", "course", "college", "university", "skill", "scholarship", "internship", "study", "degree", "subject", "resume", "interview", "education", "profession")
        is_career_question = any(word in question.lower() for word in career_words)
        if not is_career_question:
            reply = "I’m here to help with career and education guidance. Please ask me about careers, courses, skills, universities, scholarships, internships, or study plans."
            error = ""
        elif student_id:
            with st.spinner("Career AI is thinking…"):
                reply, error = send_chat_to_backend(student_id, question.strip())
        else:
            reply, error = built_in_mentor_reply(question.strip()), ""
        if error:
            # An online backend is optional. The public app remains helpful
            # when it is unavailable by using its private, built-in mentor.
            reply = built_in_mentor_reply(question.strip())
            st.session_state.mentor_history.append({"role": "student", "message": question.strip()})
            st.session_state.mentor_history.append({"role": "ai", "message": reply})
        else:
            if student_id:
                load_chat_history.clear()
            st.session_state.mentor_history.append({"role": "student", "message": question.strip()})
            st.session_state.mentor_history.append({"role": "ai", "message": reply})
        st.rerun()
    for message in messages or st.session_state.mentor_history:
        role = "You" if chat_message_role(message) == "student" else "Career AI"
        st.markdown(f"<div class='panel'><b>{role}:</b> {escape(chat_message_text(message))}</div>", unsafe_allow_html=True)


def render_explore_careers() -> None:
    st.markdown("<div class='top-title'>Explore Careers</div><div class='top-subtitle'>Search hundreds of career paths across every major field.</div>", unsafe_allow_html=True)
    search_col, category_col = st.columns([2, 1])
    with search_col:
        search_term = st.text_input("Search careers", placeholder="Try software engineer, psychologist, chef…")
    with category_col:
        category = st.selectbox("Career category", ("All categories", *JOB_CATALOG.keys()))
    careers, error = load_careers_from_backend(careers_api_url())
    if error:
        st.caption("Showing the full built-in job catalogue. Backend careers will appear here when the API is running.")
        careers = []
    backend_by_name = {career_title(career): career for career in careers}
    selected_categories = JOB_CATALOG.items() if category == "All categories" else ((category, JOB_CATALOG[category]),)
    all_jobs_with_category = [(job, group) for group, jobs in selected_categories for job in jobs]
    query = search_term.strip().lower()
    filtered = [(job, group) for job, group in all_jobs_with_category if not query or query in job.lower()]
    st.caption(f"{len(filtered)} career paths found")
    if not filtered:
        st.info("No careers match that search. Try a broader word or choose All categories.")
        return
    cards = []
    for job, group in filtered:
        backend_job = backend_by_name.get(job, {})
        description = career_description(backend_job) if backend_job else f"{group} · Explore required skills, courses, and opportunities."
        cards.append(
            f"<div class='match-card'><span class='match-pill'>{escape(group)}</span><div class='icon-bubble butterfly-mark'>🦋</div>"
            f"<h3>{escape(job)}</h3><p class='muted'>{escape(description)}</p></div>"
        )
    st.markdown("<div class='match-grid'>" + "".join(cards) + "</div>", unsafe_allow_html=True)


def render_skill_roadmap() -> None:
    st.markdown("<div class='top-title'>Your Learning Roadmap</div><div class='top-subtitle'>Track each career-preparation step as you complete it.</div>", unsafe_allow_html=True)
    student_id = active_student_id()
    steps: list[dict[str, object]] = []
    error = ""
    if student_id:
        steps, error = load_roadmap(student_id, roadmap_api_url())
    if error:
        st.warning(f"{error} Showing a roadmap based on your quiz results.")
    if not steps:
        steps = list(personalized_roadmap_steps())
        if not student_id:
            st.info("Finish the quiz to save this personalized roadmap to your account.")
    using_local_steps = not student_id or bool(error) or not load_roadmap(student_id, roadmap_api_url())[0]
    if using_local_steps:
        for step in steps:
            step_id = roadmap_step_id(step)
            if step_id is not None:
                step["completed"] = step_id in st.session_state.local_roadmap_completed
    completed_count = sum(bool(step.get("completed", False)) for step in steps)
    progress = round(completed_count * 100 / len(steps))
    st.markdown(f"<div class='panel'><h3>{progress}% complete</h3><div class='progress-shell'><div class='progress-fill' style='width:{progress}%'></div></div><p class='muted'>{completed_count} of {len(steps)} steps completed</p></div>", unsafe_allow_html=True)
    for position, step in enumerate(steps, 1):
        step_id = roadmap_step_id(step)
        title = roadmap_step_title(step, position)
        description = str(step.get("description") or step.get("details") or "")
        completed = bool(step.get("completed", False))
        row, check = st.columns([5, 1])
        with row:
            state = "Completed" if completed else "In progress"
            st.markdown(f"<div class='panel'><h3>{position}. {escape(title)}</h3><p class='muted'>{escape(description) if description else state}</p></div>", unsafe_allow_html=True)
        with check:
            st.markdown("<div style='height:18px'></div>", unsafe_allow_html=True)
            if step_id is None:
                st.caption("Missing step ID")
            elif using_local_steps:
                if st.button("✓ Done" if not completed else "↩ Undo", key=f"roadmap_step_{step_id}", use_container_width=True):
                    if completed:
                        st.session_state.local_roadmap_completed.discard(step_id)
                    else:
                        st.session_state.local_roadmap_completed.add(step_id)
                    st.rerun()
            elif st.button("✓ Done" if not completed else "↩ Undo", key=f"roadmap_step_{step_id}", use_container_width=True):
                update_error = update_roadmap_step(student_id, step_id, not completed)
                if update_error:
                    st.error(update_error)
                else:
                    load_roadmap.clear()
                    st.rerun()


def render_universities() -> None:
    st.markdown("<div class='top-title'>Universities Worldwide</div><div class='top-subtitle'>Browse the curated study-path recommendations or search the wider global higher-education directory.</div>", unsafe_allow_html=True)
    source = st.radio(
        "University source",
        ("Curated recommendations", "Worldwide directory"),
        horizontal=True,
        label_visibility="collapsed",
    )
    if source == "Worldwide directory":
        st.markdown("<div class='panel'><h3>🌍 Search worldwide institutions</h3><p class='muted'>Search a broad international directory of universities and higher-education institutions. Results are directory listings from OpenAlex—not rankings or application advice.</p></div>", unsafe_allow_html=True)
        search_col, country_col = st.columns([2, 1])
        with search_col:
            global_query = st.text_input("Search worldwide universities", placeholder="Try engineering, university, design, MIT…", key="global_university_query")
        with country_col:
            country = st.selectbox("Country", ("All countries", *GLOBAL_UNIVERSITY_COUNTRIES), key="global_university_country")
        if not global_query.strip() and country == "All countries":
            st.info("Enter a university name/subject or select a country to search the worldwide directory.")
            return
        with st.spinner("Searching worldwide institutions…"):
            global_results = search_worldwide_universities(global_query, country)
        if not global_results:
            st.warning("No directory results were returned. Check your internet connection or try a broader search.")
            return
        st.caption(f"{len(global_results)} institutions found. Use each university’s official website to verify courses, fees, accreditation, admissions, and scholarships.")
        cards = "".join(
            f"<div class='match-card'><span class='match-pill'>{escape(item['country'])}</span><div class='icon-bubble'>🎓</div>"
            f"<h3>{escape(item['name'])}</h3><p class='muted'>{escape(item['city']) or 'Location not listed'}"
            + (f"<br><span class='mint'>{escape(item['website'])}</span>" if item['website'] else "")
            + "</p></div>"
            for item in global_results
        )
        st.markdown("<div class='match-grid'>" + cards + "</div>", unsafe_allow_html=True)
        return
    recommended = university_recommendations()
    recommended_cards = "".join(
        f"<div class='match-card'><span class='match-pill'>For you</span><div class='icon-bubble'>🎓</div>"
        f"<h3>{escape(university['name'])}</h3><p class='muted'><b>{escape(university['field'])}</b><br>{escape(university['country'])}<br><span class='mint'>{escape(university['scholarships'])}</span></p></div>"
        for university in recommended
    )
    st.markdown(
        "<div class='panel'><h3>🦋 Recommended for you</h3><p class='muted'>"
        + escape(university_recommendation_reason())
        + "</p><div class='match-grid'>" + recommended_cards + "</div></div>",
        unsafe_allow_html=True,
    )
    st.markdown("<h2 style='margin-top:28px'>Browse all curated universities</h2>", unsafe_allow_html=True)
    fields = tuple(sorted({university["field"] for university in UNIVERSITY_CATALOG}))
    search_col, field_col = st.columns([2, 1])
    with search_col:
        query = st.text_input("Search universities", placeholder="Try MIT, IIT, design, medicine…").strip().lower()
    with field_col:
        field = st.selectbox("Study field", ("All fields", *fields))
    filtered = [
        university for university in UNIVERSITY_CATALOG
        if (field == "All fields" or university["field"] == field)
        and (not query or query in " ".join(university.values()).lower())
    ]
    st.caption(f"{len(filtered)} university recommendations found · Rankings are snapshots—check current rankings before applying.")
    if not filtered:
        st.info("No universities match that search.")
        return
    cards = "".join(
        f"<div class='match-card'><span class='match-pill'>{escape(university['country'])}</span><div class='icon-bubble'>🎓</div>"
        f"<h3>{escape(university['name'])}</h3><p class='muted'><b>{escape(university['field'])}</b><br>{escape(university['reputation'])}<br><span class='mint'>{escape(university['scholarships'])}</span></p></div>"
        for university in filtered
    )
    st.markdown("<div class='match-grid'>" + cards + "</div>", unsafe_allow_html=True)


def render_scholarships() -> None:
    st.markdown("<div class='top-title'>Scholarships</div><div class='top-subtitle'>Major funding opportunities for Indian students and international study pathways.</div>", unsafe_allow_html=True)
    recommended = recommended_scholarships()
    recommended_cards = "".join(
        f"<div class='match-card'><span class='match-pill'>For you</span><div class='icon-bubble butterfly-mark'>🦋</div><h3>{escape(item['name'])}</h3>"
        f"<p class='muted'><b>Coverage:</b> {escape(item['coverage'])}<br><span class='mint'>{escape(item['best_for'])}</span></p></div>"
        for item in recommended
    )
    st.markdown("<div class='panel'><h3>🦋 Recommended for your current career direction</h3><p class='muted'>Matched using your strongest quiz themes and career results. Always confirm eligibility and deadlines on the official provider website.</p><div class='match-grid'>" + recommended_cards + "</div></div>", unsafe_allow_html=True)
    st.markdown("<h2 style='margin-top:28px'>Browse all scholarships</h2>", unsafe_allow_html=True)
    query = st.text_input("Search scholarships", placeholder="Try UK, STEM, master's, India…").strip().lower()
    filtered = [
        scholarship for scholarship in SCHOLARSHIP_CATALOG
        if not query or query in " ".join(scholarship.values()).lower()
    ]
    st.caption(f"{len(filtered)} scholarships found · Always confirm current eligibility and deadlines on the official provider website.")
    if not filtered:
        st.info("No scholarships match that search.")
        return
    cards = "".join(
        f"<div class='match-card'><div class='icon-bubble butterfly-mark'>🦋</div><h3>{escape(item['name'])}</h3>"
        f"<p class='muted'><b>Funded by:</b> {escape(item['funded_by'])}<br><b>Coverage:</b> {escape(item['coverage'])}<br><span class='mint'>{escape(item['best_for'])}</span></p></div>"
        for item in filtered
    )
    st.markdown("<div class='match-grid'>" + cards + "</div>", unsafe_allow_html=True)


def render_simple_page(page: str) -> None:
    st.markdown(f"<div class='top-title'>{page}</div><div class='top-subtitle'>This section is ready for the next stage of your app.</div>", unsafe_allow_html=True)
    for row in range(2):
        cols = st.columns(3)
        for number, col in enumerate(cols, 1 + row * 3):
            with col: st.markdown(f"<div class='panel'><div class='icon-bubble butterfly-mark'>🦋</div><h3>{page} card {number}</h3><p class='muted'>Connect live recommendation data here later.</p></div>", unsafe_allow_html=True)


def render_app() -> None:
    render_theme_toggle()
    page = render_sidebar()
    if page == "Dashboard": render_dashboard()
    elif page == "Explore Careers": render_explore_careers()
    elif page == "Skill Roadmap": render_skill_roadmap()
    elif page == "Universities": render_universities()
    elif page == "Scholarships": render_scholarships()
    elif page == "AI Mentor": render_ai_mentor()
    else: render_simple_page(page)


def main() -> None:
    init_state()
    inject_styles()
    stage = st.session_state.app_stage
    if stage == "login": render_login()
    elif stage == "welcome": render_welcome()
    elif stage == "intake": render_intake()
    elif stage == "intake_results": render_intake_results()
    elif stage == "personality": render_personality()
    elif stage == "personality_results": render_personality_results()
    else: render_app()


if __name__ == "__main__":
    main()
