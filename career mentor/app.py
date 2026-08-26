"""Career AI — interactive Streamlit career mentor.

Career-intake and personality questions are based on the supplied Career
Mentor Question Bank. Answers stay only in this Streamlit browser session.
"""

from __future__ import annotations

from difflib import SequenceMatcher, get_close_matches
from html import escape
import base64
import hashlib
import hmac
import json
import os
import random
import re
import sys
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import streamlit as st
import streamlit.components.v1 as components

# The root app.py launches this file with runpy. Include this folder on the
# import path so database.py can be imported both locally and on Streamlit.
APP_DIRECTORY = Path(__file__).resolve().parent
if str(APP_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(APP_DIRECTORY))

from database import (
    authenticate_user,
    create_user,
    delete_user,
    get_user_by_student_id,
    initialise_database,
    list_users,
    load_student_state,
    save_student_state,
    update_user_password,
)

try:
    from openai import OpenAI
    from openai import AuthenticationError, RateLimitError, APIConnectionError
except ImportError:  # Lets the rest of the student project run until deploy installs the SDK.
    OpenAI = None
    AuthenticationError = RateLimitError = APIConnectionError = Exception


# Transparent butterfly logo: it blends into the page instead of appearing
# as a screenshot with a dark square behind it.
LOGO_PATH = str(Path(__file__).parent / "assets" / "career-ai-logo-clean.png")
JOURNAL_COMPONENT_PATH = Path(__file__).parent / "journal_component"
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
DEFAULT_OPENAI_MODEL = "gpt-4o-mini"
DEFAULT_GEMINI_MODEL = "gemini-3.6-flash"
GEMINI_OPENAI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"
DEFAULT_OLLAMA_URL = "http://127.0.0.1:11434"
DEFAULT_OLLAMA_MODEL = "llama3.2"
st.set_page_config(page_title="Career AI", page_icon=LOGO_PATH, layout="wide", initial_sidebar_state="expanded")
career_journal_component = components.declare_component(
    "career_journal",
    path=str(JOURNAL_COMPONENT_PATH),
)
initialise_database()

PAGES = ("Dashboard", "Explore Careers", "Career Quest", "Career Journal", "Skill Roadmap", "Scholarships", "Universities", "AI Mentor", "Change Password")
PAGE_ICONS = {"Dashboard": "⌂", "Explore Careers": "⌕", "Career Quest": "🎮", "Career Journal": "📔", "Skill Roadmap": "↗", "Scholarships": "🦋", "Universities": "♜", "AI Mentor": "🦋", "Change Password": "🔒", "Admin": "⚙"}
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

# A lightweight game that helps students distinguish between careers with
# overlapping skills. Ten questions are selected for each round; the answer
# positions are balanced and shuffled without affecting real quiz results.
CAREER_GAME_QUESTIONS = (
    {
        "clue": "A banking app loses users during registration. I run usability sessions, map the user journey, and redesign the interaction flow—not the visual brand. Which role best fits?",
        "options": ("UX Designer", "UX Researcher", "Graphic Designer", "Product Manager"),
        "answer": "UX Designer",
        "explanation": "UX designers translate user evidence into interaction flows, information architecture, wireframes, and usable product experiences.",
    },
    {
        "clue": "I estimate an endangered cat population from camera-trap captures, study habitat use, and advise a conservation programme. Which specialist am I?",
        "options": ("Wildlife Biologist", "Veterinary Pathologist", "Environmental Engineer", "Agricultural Scientist"),
        "answer": "Wildlife Biologist",
        "explanation": "Wildlife biologists use field observations and population methods to study free-living animals and their habitats.",
    },
    {
        "clue": "A retailer wants to know why repeat purchases fell. I clean transaction data, test patterns, build a dashboard, and explain the evidence to decision-makers. Which role is this?",
        "options": ("Data Analyst", "Data Engineer", "Actuary", "Operations Research Analyst"),
        "answer": "Data Analyst",
        "explanation": "Data analysts examine existing data and communicate findings; data engineers primarily build the pipelines that supply it.",
    },
    {
        "clue": "After knee surgery, I measure joint movement, prescribe progressive exercises, and retrain walking mechanics. Which professional leads this physical rehabilitation?",
        "options": ("Physiotherapist", "Occupational Therapist", "Orthopaedic Surgeon", "Sports Psychologist"),
        "answer": "Physiotherapist",
        "explanation": "Physiotherapists restore movement and physical function; occupational therapists focus more on independence in daily activities.",
    },
    {
        "clue": "For a new public library, I coordinate spatial planning, circulation, accessibility, materials, and the overall building concept while engineers verify structural systems. Who am I?",
        "options": ("Architect", "Structural Engineer", "Urban Planner", "Quantity Surveyor"),
        "answer": "Architect",
        "explanation": "Architects integrate human needs, space, regulations, and design intent while coordinating specialist engineers.",
    },
    {
        "clue": "I create a seasonal menu, cost dishes, supervise kitchen stations, and make the final call on flavour and service consistency. Which role best fits?",
        "options": ("Executive Chef", "Food Technologist", "Restaurant Manager", "Dietitian"),
        "answer": "Executive Chef",
        "explanation": "An executive chef leads culinary production and menu quality; a restaurant manager oversees the wider business and guest operations.",
    },
    {
        "clue": "I compare leaked records with public documents, interview several sources, and give the subjects a chance to respond before publication. Which role is most precise?",
        "options": ("Investigative Journalist", "Public Relations Specialist", "Policy Analyst", "Copy Editor"),
        "answer": "Investigative Journalist",
        "explanation": "Investigative journalists build evidence-based public-interest stories through documents, sources, verification, and fair-response practices.",
    },
    {
        "clue": "An alert shows unusual logins and data transfers. I examine logs, contain the affected machine, preserve evidence, and help close the security gap. Which role am I performing?",
        "options": ("Cybersecurity Analyst", "Network Architect", "Software Tester", "Database Administrator"),
        "answer": "Cybersecurity Analyst",
        "explanation": "Cybersecurity analysts investigate security events and coordinate containment, recovery, and prevention.",
    },
    {
        "clue": "Residents report polluted groundwater near an industrial site. I design sampling, interpret laboratory results, trace likely sources, and prepare a remediation assessment. Who am I?",
        "options": ("Environmental Scientist", "Chemical Engineer", "Hydrologist", "Urban Planner"),
        "answer": "Environmental Scientist",
        "explanation": "Environmental scientists connect field sampling, laboratory evidence, regulations, and human impacts to assess environmental problems.",
    },
    {
        "clue": "Using a rig supplied by another artist, I refine poses, timing, weight, and facial performance so a digital character appears alive. Which role fits best?",
        "options": ("3D Animator", "3D Modeller", "VFX Compositor", "Storyboard Artist"),
        "answer": "3D Animator",
        "explanation": "3D animators create performance through posing and timing; modellers build forms and compositors combine final visual layers.",
    },
    {
        "clue": "I analyse match footage, design tactical drills, select team combinations, and give technical feedback before the next fixture. Which role is this?",
        "options": ("Sports Coach", "Sports Physiotherapist", "Performance Analyst", "Sports Agent"),
        "answer": "Sports Coach",
        "explanation": "A sports coach owns player development and tactical preparation, often using analysis supplied by specialist performance analysts.",
    },
    {
        "clue": "I model airflow over a wing, evaluate stability, and test whether a design meets performance and safety requirements. Which engineer is most directly responsible?",
        "options": ("Aerospace Engineer", "Mechanical Engineer", "Avionics Technician", "Air Traffic Controller"),
        "answer": "Aerospace Engineer",
        "explanation": "Aerospace engineers specialise in flight vehicles and apply aerodynamics, structures, propulsion, controls, and testing.",
    },
    {
        "clue": "I use mortality tables, probability models, and financial assumptions to estimate the long-term cost of insurance promises. Which profession is this?",
        "options": ("Actuary", "Financial Analyst", "Statistician", "Insurance Underwriter"),
        "answer": "Actuary",
        "explanation": "Actuaries quantify long-term financial risk using probability, statistics, finance, and professional judgement.",
    },
    {
        "clue": "I sketch and prototype a handheld medical device, balancing ergonomics, manufacture, appearance, and how a person physically uses it. Who am I?",
        "options": ("Industrial Designer", "Biomedical Engineer", "Mechanical Engineer", "Graphic Designer"),
        "answer": "Industrial Designer",
        "explanation": "Industrial designers shape the form and user interaction of physical products while collaborating with engineers on technical feasibility.",
    },
    {
        "clue": "A family may carry an inherited condition. I explain test options and probabilities, explore their concerns, and support an informed decision without choosing for them. Who am I?",
        "options": ("Genetic Counsellor", "Clinical Geneticist", "Laboratory Technologist", "Clinical Psychologist"),
        "answer": "Genetic Counsellor",
        "explanation": "Genetic counsellors combine genetics knowledge with counselling to support informed, values-based decisions.",
    },
    {
        "clue": "After a stroke, I assess language comprehension, speech production, and swallowing, then design targeted therapy. Which specialist am I?",
        "options": ("Speech-Language Pathologist", "Occupational Therapist", "Audiologist", "Neurologist"),
        "answer": "Speech-Language Pathologist",
        "explanation": "Speech-language pathologists assess and treat communication and swallowing disorders across the lifespan.",
    },
    {
        "clue": "A company suspects money is being hidden through false vendors. I trace transactions, reconstruct records, and prepare financial evidence that may be used in court. Who am I?",
        "options": ("Forensic Accountant", "External Auditor", "Financial Controller", "Investment Analyst"),
        "answer": "Forensic Accountant",
        "explanation": "Forensic accountants investigate financial irregularities and present evidence suitable for disputes, insurance claims, or legal proceedings.",
    },
    {
        "clue": "Several districts report the same unusual illness. I compare incidence rates, identify exposure patterns, and design a study to test what is driving the outbreak. Who am I?",
        "options": ("Epidemiologist", "Infectious-Disease Physician", "Biostatistician", "Public Health Inspector"),
        "answer": "Epidemiologist",
        "explanation": "Epidemiologists study the distribution and causes of health events in populations and test ways to control them.",
    },
    {
        "clue": "Demand is rising but deliveries are late. I analyse forecasts, inventory levels, supplier lead times, and transport data to locate the bottleneck. Which role fits best?",
        "options": ("Supply Chain Analyst", "Procurement Specialist", "Logistics Coordinator", "Operations Manager"),
        "answer": "Supply Chain Analyst",
        "explanation": "Supply chain analysts use data to improve the flow of materials and products across suppliers, inventory, production, and distribution.",
    },
    {
        "clue": "A laboratory produces millions of DNA sequence reads. I build computational workflows to align them, detect variants, and connect patterns with biological questions. Who am I?",
        "options": ("Bioinformatics Scientist", "Molecular Geneticist", "Clinical Data Manager", "Machine Learning Engineer"),
        "answer": "Bioinformatics Scientist",
        "explanation": "Bioinformatics scientists combine programming, statistics, and biology to interpret large molecular datasets such as DNA or gene-expression data.",
    },
)

# Direct websites for frequently recommended institutions. Every other entry
# still receives a safe, targeted official-site search link via the helper
# below, so students can open a source for any university in the catalogue.
OFFICIAL_UNIVERSITY_URLS = {
    "indian institute of science (iisc), bengaluru": "https://iisc.ac.in/",
    "national institute of technology karnataka (nitk), surathkal": "https://www.nitk.ac.in/",
    "international institute of information technology bangalore (iiit-b)": "https://www.iiitb.ac.in/",
    "rv college of engineering, bengaluru": "https://rvce.edu.in/",
    "bms college of engineering, bengaluru": "https://bmsce.ac.in/",
    "ramaiah institute of technology, bengaluru": "https://msrit.edu/",
    "pes university, bengaluru": "https://pes.edu/",
    "kle technological university, hubballi": "https://kletech.ac.in/",
    "national law school of india university (nlsiu), bengaluru": "https://www.nls.ac.in/",
    "national institute of mental health and neuro sciences (nimhans), bengaluru": "https://nimhans.ac.in/",
    "st. john's medical college, bengaluru": "https://stjohns.in/",
    "manipal academy of higher education, manipal": "https://www.manipal.edu/",
    "university of mysore, mysuru": "https://uni-mysore.ac.in/",
    "bangalore university, bengaluru": "https://bangaloreuniversity.karnataka.gov.in/",
    "christ university, bengaluru": "https://christuniversity.in/",
    "st. joseph's university, bengaluru": "https://www.sju.edu.in/",
    "azim premji university, bengaluru": "https://azimpremjiuniversity.edu.in/",
    "srishti manipal institute of art, design and technology, bengaluru": "https://srishtimanipalinstitute.in/",
    "university of agricultural sciences, bengaluru": "https://uasbangalore.edu.in/",
    "karnataka veterinary, animal and fisheries sciences university, bidar": "https://kvafsu.edu.in/",
    "iisc bangalore": "https://iisc.ac.in/",
    "nlsiu bangalore": "https://www.nls.ac.in/",
    "mit": "https://www.mit.edu/",
    "stanford university": "https://www.stanford.edu/",
    "harvard university": "https://www.harvard.edu/",
    "university of oxford": "https://www.ox.ac.uk/",
    "university of cambridge": "https://www.cam.ac.uk/",
    "national university of singapore": "https://nus.edu.sg/",
    "eth zurich": "https://ethz.ch/",
    "iit madras": "https://www.iitm.ac.in/",
    "iit bombay": "https://www.iitb.ac.in/",
    "iit delhi": "https://home.iitd.ac.in/",
    "iim bangalore": "https://www.iimb.ac.in/",
    "iim ahmedabad": "https://www.iima.ac.in/",
    "aiims new delhi": "https://www.aiims.edu/",
    "iisc bangalore": "https://iisc.ac.in/",
}

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
    "A": ("acting", "actor", "actress", "theatre", "theater", "perform", "performance", "drama", "stage", "audition", "art", "design", "draw", "creative", "writing", "music", "instrument", "guitar", "piano", "violin", "drums", "singing", "film", "content", "photography", "story", "visual"),
    "S": ("help", "teach", "people", "care", "counsel", "health", "community", "team", "psychology", "education", "volunteer"),
    "E": ("business", "lead", "leadership", "management", "entrepreneur", "marketing", "sales", "law", "finance", "public speaking", "company"),
    "C": ("organise", "organize", "plan", "detail", "account", "spreadsheet", "system", "structure", "admin", "logistics", "records"),
}

# Direct mentions in the written career quiz should be stronger evidence than a
# generic category. These careers appear before broader RIASEC suggestions.
# The complete job directory remains available in Explore Careers.
DIRECT_CAREER_KEYWORDS = {
    "acting": ("Actor", "Theatre Artist", "Film Maker"), "actor": ("Actor", "Theatre Artist"), "theatre": ("Theatre Artist", "Actor"), "drama": ("Actor", "Theatre Artist"),
    "film": ("Film Maker", "Video Editor", "Screenwriter"), "music": ("Musician", "Music Producer", "Sound Engineer"), "instrument": ("Musician", "Instrumentalist", "Music Teacher"), "dance": ("Dancer", "Choreographer", "Dance Teacher"),
    "fashion": ("Fashion Designer", "Fashion Stylist", "Textile Designer"), "photography": ("Photographer", "Photojournalist", "Visual Artist"),
    "crochet": ("Textile Designer", "Weaver", "Fashion Designer"), "knitting": ("Textile Designer", "Weaver", "Fashion Designer"), "sewing": ("Fashion Designer", "Textile Designer", "Garment Worker"),
    "embroidery": ("Textile Designer", "Fashion Designer", "Weaver"), "weaving": ("Weaver", "Textile Designer", "Fashion Designer"), "craft": ("Craft Artist", "Product Designer", "Textile Designer"), "crafts": ("Craft Artist", "Product Designer", "Textile Designer"),
    "painting": ("Painter (Artist)", "Illustrator", "Visual Artist"), "paint": ("Painter (Artist)", "Illustrator", "Visual Artist"), "drawing": ("Illustrator", "Graphic Designer", "Concept Artist"), "draw": ("Illustrator", "Graphic Designer", "Concept Artist"),
    "animation": ("Animator", "Game Designer", "Illustrator"), "game": ("Game Designer", "Game Developer", "Animator"),
    "writing": ("Writer", "Journalist", "Content Strategist"), "writer": ("Writer", "Technical Writer", "Journalist"),
    "design": ("UX Designer", "Graphic Designer", "Product Designer"), "art": ("Graphic Designer", "Illustrator", "Visual Artist"),
    "coding": ("Software Engineer", "Front-End Developer", "Back-End Developer"), "coder": ("Software Engineer", "Front-End Developer", "Back-End Developer"), "developer": ("Software Engineer", "Full-Stack Developer", "Mobile App Developer"), "programming": ("Software Engineer", "Full-Stack Developer", "Mobile App Developer"),
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
    "sports": ("Sports Coach", "Sports Psychologist", "Physiotherapist"), "sport": ("Sports Coach", "Sports Psychologist", "Physiotherapist"), "cricket": ("Cricketer", "Sports Coach", "Sports Journalist"),
    "football": ("Footballer", "Sports Coach", "Sports Analyst"), "athlete": ("Professional Athlete", "Sports Coach", "Sports Physiotherapist"), "coach": ("Sports Coach", "Sports Analyst", "Sports Psychologist"),
    "physical education": ("Physical Education Teacher", "Sports Coach", "Fitness Instructor"),
    "chef": ("Chef", "Food Scientist", "Restaurant Manager"), "travel": ("Travel Consultant", "Hotel Manager", "Tourism Manager"),
    "cooking": ("Chef", "Food Scientist", "Restaurant Manager"), "cook": ("Chef", "Food Technologist", "Restaurant Manager"), "baking": ("Baker", "Pastry Chef", "Food Scientist"), "baker": ("Baker", "Pastry Chef", "Food Technologist"),
    "pilot": ("Pilot", "Aerospace Engineer", "Air Traffic Controller"),
    "social work": ("Social Worker", "Community Manager", "Nonprofit Director"), "politics": ("Policy Analyst", "Diplomat", "Public Relations Specialist"),
    "poetry": ("Poet", "Author / Novelist", "Editor (Books/Magazines)"), "poet": ("Poet", "Author / Novelist", "Literary Critic"),
    "journalism": ("Journalist", "Photojournalist", "Science Journalist"), "journalist": ("Journalist", "Photojournalist", "Science Journalist"), "translation": ("Translator", "Interpreter", "Language Teacher"),
    "scientist": ("Research Scientist (R&D)", "Biologist", "Chemist"), "biology": ("Biologist", "Microbiologist", "Geneticist"), "chemistry": ("Chemist", "Pharmacologist", "Forensic Scientist"),
    "physics": ("Physicist", "Astrophysicist", "Research Scientist (R&D)"), "space": ("Astronaut", "Space Systems Engineer", "Astrophysicist"), "astronomy": ("Astronomer", "Astrophysicist", "Space Systems Engineer"),
    "animals": ("Veterinarian", "Zoologist", "Wildlife Biologist"), "animal": ("Veterinarian", "Veterinary Technician", "Animal Trainer (Film/Circus)"), "wildlife": ("Wildlife Biologist", "Conservationist", "Park Ranger"),
    "plant": ("Botanist", "Horticulturist", "Plant Scientist"), "plants": ("Botanist", "Horticulturist", "Plant Scientist"), "plansts": ("Botanist", "Horticulturist", "Plant Scientist"),
    "botany": ("Botanist", "Plant Scientist", "Conservationist"), "botanist": ("Botanist", "Plant Scientist", "Ecologist"), "gardening": ("Horticulturist", "Landscape Gardener", "Nursery Worker"), "garden": ("Horticulturist", "Landscape Gardener", "Landscape Architect"),
    "horticulture": ("Horticulturist", "Landscape Gardener", "Agronomist"), "agriculture": ("Agronomist", "Agricultural Engineer", "Farm Manager"), "farming": ("Farmer (Crop)", "Agronomist", "Horticulturist"), "food": ("Food Scientist", "Chef", "Food Technologist"),
    "beauty": ("Makeup Artist (Beauty Industry)", "Cosmetologist", "Esthetician"), "makeup": ("Makeup Artist (Beauty Industry)", "Cosmetologist", "Beauty Content Creator"), "hair": ("Hairstylist / Hairdresser", "Barber", "Cosmetologist"),
    "fitness": ("Personal Trainer", "Fitness Instructor", "Sports Psychologist"), "yoga": ("Yoga Instructor", "Wellness Coach", "Fitness Instructor"),
    "defence": ("Army Officer", "Air Force Officer", "Military Engineer"), "defense": ("Army Officer", "Air Force Officer", "Military Engineer"), "police": ("Police Officer", "Detective", "Forensic Investigator"),
    "security": ("Cybersecurity Analyst", "Private Security Guard", "Security Systems Technician"), "firefighter": ("Firefighter", "Emergency Management Director", "Fire Marshal"),
    "real estate": ("Real Estate Agent", "Property Manager", "Real Estate Developer"), "retail": ("Retail Store Manager", "Visual Merchandiser", "Store Buyer"),
    "marine": ("Marine Biologist", "Marine Engineer", "Ship Captain"), "aviation": ("Commercial Airline Pilot", "Air Traffic Controller", "Aircraft Maintenance Engineer"),
    "car": ("Automotive Engineer", "Auto Mechanic", "Automotive Designer"), "mechanic": ("Mechanical Engineer", "Auto Mechanic", "Aircraft Mechanic"),
    "electrician": ("Electrician", "Electrical Engineer", "Electrical Lineman"), "construction": ("Civil Engineer", "Construction Site Supervisor", "Architect"),
    "climate": ("Climate Change Analyst", "Environmental Scientist", "Sustainability Manager"), "sustainability": ("Sustainability Manager", "Environmental Consultant", "Renewable Energy Engineer"),
    "photographer": ("Photographer", "Photojournalist", "Stock Photographer"), "video": ("Video Editor", "Film Maker", "Content Creator"), "content creator": ("Content Strategist", "Content Creator", "Social Media Manager"),
    "voice": ("Voice Coach", "Radio Host", "Voice Actor"), "gaming": ("Game Developer", "Game Designer", "Esports Player"), "esports": ("Esports Player", "Esports Coach/Analyst", "E-sports Team Manager"),
    "reading": ("Writer", "Editor (Books/Magazines)", "Librarian"), "books": ("Author / Novelist", "Editor (Books/Magazines)", "Librarian"), "languages": ("Translator", "Interpreter", "Language Teacher"), "language": ("Translator", "Interpreter", "Language Teacher"),
    "math": ("Actuary", "Data Analyst", "Economist"), "maths": ("Actuary", "Data Analyst", "Economist"), "mathematics": ("Actuary", "Statistician", "Data Scientist"),
    "pets": ("Veterinarian", "Veterinary Technician", "Animal Groomer"), "nature": ("Environmental Scientist", "Conservationist", "Ecologist"), "ocean": ("Marine Biologist", "Oceanographer", "Marine Engineer"),
    "social media": ("Social Media Manager", "Content Strategist", "Digital Marketing Specialist"), "youtube": ("Content Creator", "Video Editor", "Social Media Manager"), "blogging": ("Blogger", "Content Strategist", "Writer"),
    "interior": ("Interior Designer", "Architect", "Set Designer"), "jewellery": ("Jewellery Designer", "Goldsmith", "Product Designer"), "jewelry": ("Jewellery Designer", "Goldsmith", "Product Designer"),
    "history": ("Historian", "Archaeologist", "Museum Curator"), "archaeology": ("Archaeologist", "Museum Curator", "Anthropologist"),
    "religion": ("Religious Minister / Clergy", "Community Organizer", "Counselor (Mental Health)"), "counselling": ("Counsellor", "Psychologist", "Career Counselor"),
}

# Students naturally use different forms of the same hobby.  Keep one
# canonical career mapping above, then recognise common everyday variants
# here.  For example, "I love dancing and sketching" should surface both
# performing-arts and visual-design careers rather than only a generic Artist.
DIRECT_CAREER_ALIASES = {
    "dance": ("dancing", "dancer", "choreography", "choreograph", "ballet", "hip hop", "hip-hop"),
    "drawing": ("drawings", "sketch", "sketching", "illustration", "illustrating", "digital art"),
    "painting": ("paintings", "painter"),
    "music": ("sing", "singing", "singer", "song", "songs", "songwriting", "songwriter", "vocal", "vocals"),
    "instrument": ("instruments", "instrumental", "guitar", "guitarist", "piano", "pianist", "keyboard", "violin", "violinist", "drum", "drums", "drummer", "flute", "flutist", "tabla", "sitar", "ukulele", "bass", "saxophone", "trumpet"),
    "acting": ("actress", "performing", "performance", "performer", "audition"),
    "photography": ("photographer", "photos", "photo editing"),
    "cooking": ("culinary", "cuisine", "cooked"),
    "coding": ("code", "programmer", "programmers"),
    "sports": ("athletic", "athletics", "sporting"),
    "plant": ("plants", "gardening", "garden", "botany"),
    "animal": ("animals", "pets", "wildlife"),
}

# Specific next skills for common careers. These make the no-cost mentor
# answer the student's actual question instead of repeating a generic reply.
ROLE_SKILL_GUIDANCE = {
    "chef": ("knife skills and food safety", "flavour balancing and recipe development", "kitchen time management"),
    "coder": ("programming fundamentals", "problem-solving and debugging", "Git/GitHub plus small projects"),
    "coding": ("programming fundamentals", "problem-solving and debugging", "Git/GitHub plus small projects"),
    "developer": ("programming fundamentals", "data structures and debugging", "Git/GitHub plus real projects"),
    "actor": ("acting technique and voice training", "audition preparation", "a performance showreel"),
    "acting": ("acting technique and voice training", "audition preparation", "a performance showreel"),
    "poet": ("regular writing practice", "editing and literary analysis", "a small published portfolio"),
    "writer": ("clear writing and editing", "research", "a portfolio of finished pieces"),
    "doctor": ("strong biology and chemistry", "clinical communication", "volunteering or healthcare exposure"),
    "medicine": ("strong biology and chemistry", "clinical communication", "volunteering or healthcare exposure"),
    "scientist": ("scientific method and lab skills", "data analysis", "research projects"),
    "engineer": ("maths and physics foundations", "design/problem-solving", "hands-on technical projects"),
    "designer": ("design fundamentals", "relevant tools such as Figma or Adobe", "a strong visual portfolio"),
    "lawyer": ("reading and legal reasoning", "clear writing and public speaking", "debate or legal-shadowing experience"),
    "law": ("reading and legal reasoning", "clear writing and public speaking", "debate or legal-shadowing experience"),
    "teacher": ("subject expertise", "clear explanation and active listening", "tutoring or classroom experience"),
    "psychology": ("research methods", "active listening and ethics", "relevant volunteering"),
    "business": ("communication and presentation", "basic finance", "leadership through a small project"),
    "entrepreneur": ("problem discovery", "basic finance and marketing", "testing a small real idea"),
    "pilot": ("maths and physics", "situational awareness", "aviation medical and flight-training research"),
    "sports": ("sport-specific training", "fitness and recovery", "teamwork and performance analysis"),
    "cricket": ("batting and bowling technique", "fielding and match awareness", "fitness, recovery, and consistent net practice"),
    "cricketer": ("batting and bowling technique", "fielding and match awareness", "fitness, recovery, and consistent net practice"),
    "football": ("ball control and passing", "speed, stamina, and recovery", "teamwork and tactical awareness"),
    "athlete": ("sport-specific technique", "strength, conditioning, and recovery", "performance analysis and mental resilience"),
    "makeup": ("colour theory and hygiene", "practice on varied looks", "a professional photo portfolio"),
    "photography": ("camera and lighting basics", "editing", "a curated photo portfolio"),
    "music": ("consistent instrument or vocal practice", "music theory", "recorded performances"),
    "nurse": ("biology and patient care", "communication", "clinical observation or volunteering"),
    "veterinarian": ("biology and animal care", "observation skills", "animal-welfare volunteering"),
    "plant": ("plant biology and ecology", "gardening or nursery practice", "a small plant-growing or conservation project"),
    "plants": ("plant biology and ecology", "gardening or nursery practice", "a small plant-growing or conservation project"),
    "botany": ("plant biology and ecology", "field observation", "a small research or conservation project"),
    "gardening": ("plant care and soil basics", "seasonal growing practice", "a small garden or nursery portfolio"),
    "horticulture": ("plant science and soil management", "nursery or greenhouse practice", "garden-design documentation"),
    "crochet": ("pattern reading and stitch techniques", "colour and textile design", "a photographed craft portfolio"),
    "knitting": ("pattern reading and stitch techniques", "textile design", "a photographed craft portfolio"),
    "sewing": ("pattern making", "fabric knowledge", "a garment or textile portfolio"),
    "cooking": ("food safety and knife skills", "recipe development", "kitchen time management"),
    "baking": ("baking science and measurements", "food safety", "a recipe and product portfolio"),
    "painting": ("drawing fundamentals", "colour theory", "a portfolio of finished work"),
    "drawing": ("observation and perspective", "visual storytelling", "a portfolio of finished work"),
    "writing": ("regular writing practice", "editing", "a portfolio of finished pieces"),
}

CAREER_FIELD_SIGNALS = {
    "acting": ("Media", "Arts"), "theatre": ("Media", "Arts"), "film": ("Media", "Arts"), "music": ("Media", "Arts"), "dance": ("Media", "Arts"),
    "fashion": ("Arts", "Design"), "photography": ("Arts", "Media"), "animation": ("Arts", "Media"), "game": ("Technology", "Media"), "design": ("Arts", "Design"), "writing": ("Writing", "Media"),
    "crochet": ("Arts", "Design"), "knitting": ("Arts", "Design"), "sewing": ("Arts", "Design"), "embroidery": ("Arts", "Design"), "weaving": ("Arts", "Design"), "craft": ("Arts", "Design"), "crafts": ("Arts", "Design"), "painting": ("Arts",), "paint": ("Arts",), "drawing": ("Arts", "Design"), "draw": ("Arts", "Design"),
    "coding": ("Technology",), "programming": ("Technology",), "software": ("Technology",), "cybersecurity": ("Technology",), "data": ("Technology", "Science"), "ai": ("Technology", "Science"), "robot": ("Engineering", "Technology"),
    "doctor": ("Healthcare", "Medicine"), "medicine": ("Healthcare", "Medicine"), "nurse": ("Healthcare",), "psychology": ("Healthcare", "Social Services"), "therapy": ("Healthcare", "Social Services"),
    "teacher": ("Education",), "education": ("Education",), "law": ("Law",), "business": ("Business",), "marketing": ("Marketing", "Business"), "finance": ("Business", "Finance"), "accounting": ("Business", "Finance"),
    "engineering": ("Engineering", "Technology"), "architecture": ("Engineering", "Arts"), "environment": ("Environment", "Science"), "science": ("Science", "Research"),
    # Sports interests must first show sports-performance/coaching universities,
    # rather than generic healthcare options. Health is kept only for an
    # explicitly health profession such as physiotherapy or sports medicine.
    "sports": ("Sports",), "sport": ("Sports",), "cricket": ("Sports",), "football": ("Sports",), "athlete": ("Sports",), "coach": ("Sports",), "physical education": ("Sports",), "fitness": ("Sports",), "yoga": ("Sports",), "physiotherapy": ("Sports", "Healthcare"), "sports medicine": ("Sports", "Healthcare"), "chef": ("Hospitality",), "travel": ("Hospitality", "Tourism"), "pilot": ("Transportation", "Engineering"),
    "cooking": ("Hospitality", "Science"), "cook": ("Hospitality",), "baking": ("Hospitality", "Science"), "baker": ("Hospitality",),
    "social work": ("Social Services",), "politics": ("Government", "Public Policy"),
    "poetry": ("Writing", "Media"), "poet": ("Writing", "Media"), "journalism": ("Media", "Writing"), "translation": ("Education", "Writing"),
    "scientist": ("Science", "Research"), "biology": ("Science", "Research"), "chemistry": ("Science", "Research"), "physics": ("Science", "Research"), "space": ("Science", "Engineering"), "astronomy": ("Science", "Research"),
    "plant": ("Agriculture", "Environment", "Science"), "plants": ("Agriculture", "Environment", "Science"), "plansts": ("Agriculture", "Environment", "Science"), "botany": ("Science", "Environment"), "botanist": ("Science", "Environment"), "gardening": ("Agriculture", "Environment"), "garden": ("Agriculture", "Environment"), "horticulture": ("Agriculture", "Environment"),
    "animals": ("Healthcare", "Environment"), "animal": ("Healthcare", "Environment"), "wildlife": ("Environment", "Science"), "agriculture": ("Agriculture", "Science"), "farming": ("Agriculture",), "food": ("Hospitality", "Science"),
    "beauty": ("Beauty", "Arts"), "makeup": ("Beauty", "Arts"), "hair": ("Beauty",),
    "defence": ("Government", "Engineering"), "defense": ("Government", "Engineering"), "police": ("Government", "Security"), "security": ("Security", "Technology"), "firefighter": ("Government", "Security"),
    "real estate": ("Real Estate", "Business"), "retail": ("Retail", "Business"), "marine": ("Science", "Transportation"), "aviation": ("Transportation", "Engineering"),
    "car": ("Engineering", "Transportation"), "mechanic": ("Engineering", "Skilled Trades"), "electrician": ("Engineering", "Skilled Trades"), "construction": ("Engineering", "Skilled Trades"),
    "climate": ("Environment", "Science"), "sustainability": ("Environment", "Science"), "photographer": ("Media", "Arts"), "video": ("Media", "Arts"), "content creator": ("Media", "Marketing"),
    "voice": ("Media", "Arts"), "gaming": ("Technology", "Media"), "esports": ("Sports", "Technology"), "history": ("Education", "Research"), "archaeology": ("Science", "Research"),
    "reading": ("Writing", "Education"), "books": ("Writing", "Education"), "languages": ("Education", "Writing"), "language": ("Education", "Writing"), "math": ("Science", "Technology"), "maths": ("Science", "Technology"), "mathematics": ("Science", "Technology"),
    "pets": ("Healthcare", "Environment"), "nature": ("Environment", "Science"), "ocean": ("Science", "Environment"), "social media": ("Media", "Marketing"), "youtube": ("Media", "Marketing"), "blogging": ("Writing", "Media"),
    "interior": ("Arts", "Design"), "jewellery": ("Arts", "Design"), "jewelry": ("Arts", "Design"),
    "religion": ("Social Services", "Education"), "counselling": ("Healthcare", "Social Services"),
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

# Extra well-known study options make the built-in catalogue more useful when
# the public worldwide directory is offline. They are intentionally labelled
# as programme areas, not rankings, and users can open the official site from
# the app to verify current courses, admissions and funding.
EXTRA_UNIVERSITIES = (
    ("University of Tokyo", "Japan", "Technology, Science, Medicine, Arts", "Major national research university", "MEXT and university scholarships"),
    ("Kyoto University", "Japan", "Science, Engineering, Medicine, Humanities", "Major national research university", "MEXT and university scholarships"),
    ("Osaka University", "Japan", "Engineering, Medicine, Science", "National research university", "MEXT and university scholarships"),
    ("Tohoku University", "Japan", "Engineering, Materials, Science", "National research university", "MEXT and university scholarships"),
    ("Waseda University", "Japan", "Business, Media, Technology, Arts", "Comprehensive private university", "MEXT and university scholarships"),
    ("Seoul National University", "South Korea", "Technology, Science, Medicine, Business", "Major national university", "Global Korea Scholarship and university aid"),
    ("KAIST", "South Korea", "Technology, Engineering, Science", "Science and technology institute", "Global Korea Scholarship and KAIST aid"),
    ("Yonsei University", "South Korea", "Business, Media, Health, Arts", "Comprehensive private university", "Global Korea Scholarship and university aid"),
    ("Tsinghua University", "China", "Engineering, Technology, Science, Business", "Major research university", "Chinese Government Scholarship and university aid"),
    ("Peking University", "China", "Science, Medicine, Humanities, Business", "Major comprehensive university", "Chinese Government Scholarship and university aid"),
    ("Fudan University", "China", "Medicine, Business, Science, Media", "Major comprehensive university", "Chinese Government Scholarship and university aid"),
    ("University of Hong Kong", "Hong Kong", "Business, Medicine, Law, Technology", "Comprehensive university", "Hong Kong PhD Fellowship and university aid"),
    ("University of Malaya", "Malaysia", "Engineering, Medicine, Business, Arts", "Public research university", "Malaysia International Scholarship and university aid"),
    ("Universiti Putra Malaysia", "Malaysia", "Agriculture, Environment, Veterinary, Science", "Public research university", "Malaysia International Scholarship and university aid"),
    ("Chulalongkorn University", "Thailand", "Business, Engineering, Medicine, Arts", "Comprehensive university", "Thai and university scholarships"),
    ("University of Indonesia", "Indonesia", "Medicine, Engineering, Social Sciences, Business", "Public university", "Indonesian and university scholarships"),
    ("University of the Philippines Diliman", "Philippines", "Arts, Engineering, Science, Social Sciences", "Public university", "University and government scholarships"),
    ("National Taiwan University", "Taiwan", "Technology, Medicine, Agriculture, Business", "Comprehensive university", "Taiwan Scholarship and university aid"),
    ("Indian Institute of Technology Kharagpur", "India", "Engineering, Technology, Science", "Institute of national importance", "Institute and government scholarships"),
    ("National Institute of Fashion Technology", "India", "Fashion, Textile, Design", "National design institute", "Merit-cum-means and government scholarships"),
    ("National Institute of Design", "India", "Product, Communication, Textile, Film Design", "National design institute", "Institute and government scholarships"),
    ("University of Delhi", "India", "Arts, Science, Commerce, Law, Social Sciences", "Large public university", "University and government scholarships"),
    ("University of British Columbia", "Canada", "Technology, Science, Arts, Business", "Public research university", "International Scholars and university aid"),
    ("McGill University", "Canada", "Medicine, Science, Arts, Music", "Public research university", "Entrance scholarships and university aid"),
    ("University of Waterloo", "Canada", "Technology, Engineering, Mathematics", "Co-op and research university", "International student scholarships"),
    ("University of Melbourne", "Australia", "Medicine, Arts, Business, Science", "Research university", "Melbourne scholarships and Australia Awards"),
    ("University of Sydney", "Australia", "Health, Technology, Arts, Business", "Research university", "Sydney scholarships and Australia Awards"),
    ("Australian National University", "Australia", "Science, Public Policy, International Relations", "National research university", "ANU and Australia Awards scholarships"),
    ("Technical University of Munich", "Germany", "Engineering, Technology, Science, Business", "Technical research university", "DAAD and university scholarships"),
    ("Heidelberg University", "Germany", "Medicine, Science, Humanities", "Research university", "DAAD and university scholarships"),
    ("RWTH Aachen University", "Germany", "Engineering, Technology, Science", "Technical university", "DAAD and university scholarships"),
    ("Delft University of Technology", "Netherlands", "Engineering, Design, Architecture", "Technical university", "Holland Scholarship and university aid"),
    ("University of Amsterdam", "Netherlands", "Social Sciences, Media, Business, Humanities", "Research university", "Amsterdam Merit Scholarship and university aid"),
    ("KTH Royal Institute of Technology", "Sweden", "Engineering, Technology, Design", "Technical university", "Swedish Institute and KTH scholarships"),
    ("Uppsala University", "Sweden", "Medicine, Science, Humanities", "Research university", "Swedish Institute and university scholarships"),
    ("University of Helsinki", "Finland", "Science, Education, Arts, Technology", "Research university", "Finland scholarships and tuition waivers"),
    ("Aalto University", "Finland", "Design, Architecture, Technology, Business", "Design and technology university", "Finland scholarships and tuition waivers"),
    ("Sciences Po", "France", "Politics, International Relations, Law, Social Sciences", "Specialist social-sciences university", "Eiffel and Sciences Po scholarships"),
    ("École Polytechnique", "France", "Engineering, Mathematics, Technology", "Engineering school", "Eiffel and university scholarships"),
    ("University of Bologna", "Italy", "Arts, Law, Engineering, Medicine", "Historic public university", "Italian government and university scholarships"),
    ("Politecnico di Milano", "Italy", "Architecture, Design, Engineering", "Technical university", "Italian government and university scholarships"),
    ("University of Barcelona", "Spain", "Medicine, Science, Arts, Business", "Public research university", "Spanish and university scholarships"),
    ("University of Lisbon", "Portugal", "Engineering, Arts, Science, Business", "Public university", "Portuguese and university scholarships"),
    ("ETH Lausanne (EPFL)", "Switzerland", "Engineering, Technology, Science", "Technical research university", "Excellence Fellowships and university aid"),
    ("University of Oxford", "UK", "Arts, Science, Medicine, Law, Business", "Comprehensive university", "Rhodes, Clarendon and college scholarships"),
    ("University of Cambridge", "UK", "Arts, Science, Engineering, Medicine", "Comprehensive university", "Gates Cambridge and university scholarships"),
    ("University College London", "UK", "Architecture, Arts, Medicine, Technology", "Comprehensive university", "UCL Global Excellence scholarships"),
    ("University of Manchester", "UK", "Engineering, Science, Business, Social Sciences", "Research university", "University scholarships and Chevening"),
    ("Imperial College London", "UK", "Engineering, Medicine, Science, Business", "STEM-focused university", "Imperial scholarships and Chevening"),
    ("University of Cape Town", "South Africa", "Health, Science, Law, Arts", "Research university", "University and external scholarships"),
    ("University of Nairobi", "Kenya", "Agriculture, Health, Engineering, Business", "Public university", "University and government scholarships"),
    ("University of Ghana", "Ghana", "Health, Science, Business, Social Sciences", "Public university", "University and external scholarships"),
    ("American University in Cairo", "Egypt", "Business, Media, Engineering, Social Sciences", "Comprehensive university", "University scholarships"),
    ("University of São Paulo", "Brazil", "Medicine, Engineering, Arts, Agriculture", "Public research university", "University and government scholarships"),
    ("Tecnológico de Monterrey", "Mexico", "Technology, Business, Design, Engineering", "Private university", "Merit and need-based scholarships"),
    ("University of Buenos Aires", "Argentina", "Medicine, Law, Arts, Science", "Public university", "Public tuition and university support"),
    ("Universidad de Chile", "Chile", "Science, Engineering, Arts, Medicine", "Public research university", "University and government scholarships"),
    ("Middle East Technical University", "Turkey", "Engineering, Technology, Architecture", "Public technical university", "Türkiye Scholarships and university aid"),
    ("Istanbul Technical University", "Turkey", "Engineering, Architecture, Design", "Technical university", "Türkiye Scholarships and university aid"),
    ("Hamad Bin Khalifa University", "Qatar", "Technology, Law, Public Policy, Islamic Studies", "Research university", "Qatar Foundation scholarships"),
    ("United Arab Emirates University", "United Arab Emirates", "Engineering, Medicine, Business, Education", "National university", "University scholarships"),
    ("King Abdullah University of Science and Technology", "Saudi Arabia", "Science, Engineering, Technology", "Graduate research university", "KAUST fellowships"),
    ("University of Auckland", "New Zealand", "Engineering, Health, Arts, Business", "Research university", "University scholarships"),
)

_all_universities = UNIVERSITY_CATALOG + tuple(
    {"field": field, "name": name, "country": country, "reputation": reputation, "scholarships": scholarships}
    for name, country, field, reputation, scholarships in EXTRA_UNIVERSITIES
)
UNIVERSITY_CATALOG = tuple({
    (university["name"].lower(), university["country"].lower()): university
    for university in _all_universities
}.values())

EXTRA_SCHOLARSHIPS = (
    ("Global Korea Scholarship (GKS)", "Government of South Korea", "Typically covers Korean-language study, degree costs, and support; check the current call.", "International degree applicants to South Korea"),
    ("Chinese Government Scholarship (CSC)", "China Scholarship Council", "Coverage and eligible programmes vary by current call and university.", "International applicants to China"),
    ("Stipendium Hungaricum", "Government of Hungary / Tempus Public Foundation", "Tuition, stipend and accommodation support depend on the current sending-partner agreement.", "Eligible applicants for study in Hungary"),
    ("Türkiye Scholarships", "Government of Türkiye", "Support and eligible programmes vary by the annual official call.", "International applicants to Türkiye"),
    ("Taiwan Scholarship", "Government of Taiwan and partner institutions", "Support varies by programme and current call.", "International applicants to Taiwan"),
    ("Swedish Institute Scholarships", "Swedish Institute", "Support varies by programme and annual call.", "Eligible master's applicants to Sweden"),
    ("Holland Scholarship", "Dutch Ministry of Education and participating institutions", "One-time grant and eligibility vary by institution and annual call.", "Eligible non-EEA students in the Netherlands"),
    ("Eiffel Excellence Scholarship", "Government of France", "Support varies by level and current call.", "Eligible master's and doctoral applicants to France"),
    ("New Zealand Scholarships", "Government of New Zealand", "Support and eligible countries vary by current call.", "Eligible international applicants to New Zealand"),
)

_all_scholarships = SCHOLARSHIP_CATALOG + tuple(
    {"name": name, "funded_by": funded_by, "coverage": coverage, "best_for": best_for}
    for name, funded_by, coverage, best_for in EXTRA_SCHOLARSHIPS
)
SCHOLARSHIP_CATALOG = tuple({
    scholarship["name"].lower(): scholarship
    for scholarship in _all_scholarships
}.values())


def university_website(name: str) -> str:
    """Return an official website when known, otherwise an official-site search."""
    direct_url = OFFICIAL_UNIVERSITY_URLS.get(name.strip().lower())
    if direct_url:
        return direct_url
    return "https://www.google.com/search?" + urlencode({"q": f"{name} official website"})


@st.cache_data(ttl=60 * 60 * 24, show_spinner=False)
def search_worldwide_universities(query: str, country: str) -> tuple[dict[str, str], ...]:
    """Use OpenAlex's public institution index for a broad worldwide search.

    It supplements the hand-curated recommendation data above. Results are
    intentionally labelled as directory matches, not rankings or endorsements.
    """
    search = query.strip()
    if not search and country == "All countries":
        return ()
    # OpenAlex no longer supports a ``types`` filter on this endpoint. Filter
    # by country here and keep only ``education`` records after receiving the
    # response below.
    filters: list[str] = []
    if country != "All countries":
        filters.append(f"country_code:{country_code(country)}")
    params = {"per-page": "50"}
    if filters:
        params["filter"] = ",".join(filters)
    if search:
        params["search"] = search
    endpoint = "https://api.openalex.org/institutions?" + urlencode(params)
    try:
        request = Request(endpoint, headers={"User-Agent": "Career-AI-Student-Project/1.0"})
        with urlopen(request, timeout=8) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, OSError, json.JSONDecodeError):
        return built_in_worldwide_university_results(query, country)
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
            "description": "Institution listed in the OpenAlex worldwide higher-education directory.",
            "source": "OpenAlex directory",
        })
    return tuple(results) or built_in_worldwide_university_results(query, country)


def built_in_worldwide_university_results(query: str, country: str) -> tuple[dict[str, str], ...]:
    """Offline searchable directory used whenever the public service is unavailable.

    Streamlit deployments and school networks may block the live OpenAlex
    request.  This fallback keeps Worldwide search useful for university
    names, countries and study fields without depending on an internet API.
    """
    catalogue_country = {
        "United States": "USA",
        "United Kingdom": "UK",
    }.get(country, country)
    candidates = [
        university for university in UNIVERSITY_CATALOG
        if country == "All countries" or university["country"] == catalogue_country
    ]
    search_words = [
        word for word in re.findall(r"[a-z0-9]+", query.lower())
        if word not in {"university", "universities", "college", "colleges", "institution", "institutions", "school", "schools"}
    ]
    if search_words:
        matches = [
            university for university in candidates
            if all(
                word in " ".join(str(value).lower() for value in university.values())
                for word in search_words
            )
        ]
        # A broad subject typed with a university name can fail an exact
        # all-word match. In that case keep every university matching at least
        # one meaningful term rather than displaying an empty page.
        if not matches:
            matches = [
                university for university in candidates
                if any(
                    word in " ".join(str(value).lower() for value in university.values())
                    for word in search_words
                )
            ]
        candidates = matches
    return tuple({
        "name": university["name"],
        "country": university["country"],
        "city": "",
        "website": university_website(university["name"]),
        "description": f"Study areas: {university['field']}. {university['reputation']}",
        "source": "Career AI built-in directory",
    } for university in candidates[:50])


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
    defaults = {"app_stage":"login", "auth_mode":"login", "light_mode":False, "nav_page":"Dashboard", "student_name":"", "student_email":"", "quiz_name":"", "intake_mode":None, "intake_index":0, "intake_answers":{}, "personality_mode":None, "personality_index":0, "personality_answers":{}, "personality_complete":False, "backend_profile":None, "backend_error":"", "top_matches":[], "career_insights":{}, "score_error":"", "local_roadmap_completed":set(), "mentor_history":[], "career_journal":{"version":1, "currentPage":0, "pages":[]}, "journal_last_save_token":""}
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)


def session_secret() -> bytes:
    """Return the app-only signing secret for the optional remember token."""
    try:
        configured = str(st.secrets.get("SESSION_SECRET", "")).strip()
    except Exception:
        configured = ""
    configured = configured or os.getenv("SESSION_SECRET", "").strip()
    # A stable local fallback keeps localhost convenient. Cloud deployments
    # should set SESSION_SECRET in Streamlit Secrets for a private key.
    configured = configured or "career-ai-local-session-secret-change-in-cloud"
    return configured.encode("utf-8")


def make_session_token(student_id: str) -> str:
    """Create a short-lived, tamper-evident token without storing a password."""
    payload = {"sid": str(student_id), "exp": int(time.time()) + 60 * 60 * 24 * 30}
    encoded = base64.urlsafe_b64encode(
        json.dumps(payload, separators=(",", ":")).encode("utf-8")
    ).decode("ascii").rstrip("=")
    signature = hmac.new(session_secret(), encoded.encode("ascii"), hashlib.sha256).digest()
    signed = base64.urlsafe_b64encode(signature).decode("ascii").rstrip("=")
    return f"{encoded}.{signed}"


def restore_session_from_url() -> None:
    """Restore a remembered login after a refresh/browser back navigation."""
    if st.session_state.get("student_email"):
        return
    try:
        token = str(st.query_params.get("session", "")).strip()
    except Exception:
        token = ""
    if not token or "." not in token:
        return
    encoded, supplied_signature = token.split(".", 1)
    expected_signature = base64.urlsafe_b64encode(
        hmac.new(session_secret(), encoded.encode("ascii"), hashlib.sha256).digest()
    ).decode("ascii").rstrip("=")
    if not hmac.compare_digest(supplied_signature, expected_signature):
        return
    try:
        padded = encoded + "=" * (-len(encoded) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded).decode("utf-8"))
        if int(payload.get("exp", 0)) < int(time.time()):
            return
        account = get_user_by_student_id(str(payload.get("sid", "")))
    except Exception:
        return
    if not account:
        return
    restore_student_state(account)
    st.session_state.app_stage = resume_stage()


# These values make a student's recommendations personal. They are saved in
# SQLite after each important action and restored when that student logs in.
PERSISTED_PROFILE_KEYS = (
    "app_stage",
    "intake_mode", "intake_index", "intake_answers", "personality_mode",
    "personality_index", "personality_answers", "personality_complete",
    "top_matches", "career_insights", "score_error", "mentor_history",
    "nav_page", "local_roadmap_completed", "career_journal",
)


def save_current_student_state() -> None:
    """Save quiz, results, chat and roadmap progress for the logged-in user."""
    email = str(st.session_state.get("student_email", "")).strip()
    if not email:
        return
    state: dict[str, object] = {}
    for key in PERSISTED_PROFILE_KEYS:
        value = st.session_state.get(key)
        # JSON cannot store Python sets; roadmap completion is the only one.
        state[key] = sorted(value) if isinstance(value, set) else value
    save_student_state(email, state)


def restore_student_state(account: dict[str, object]) -> None:
    """Restore one user's saved quiz state without restoring another user's UI."""
    st.session_state.student_name = str(account["name"])
    st.session_state.student_email = str(account["email"])
    student_id = str(account["student_id"])
    st.session_state.backend_profile = {
        "student_id": student_id,
        "name": st.session_state.student_name,
        "email": st.session_state.student_email,
    }
    saved = load_student_state(st.session_state.student_email)
    for key in PERSISTED_PROFILE_KEYS:
        if key in saved:
            st.session_state[key] = saved[key]
    st.session_state.local_roadmap_completed = set(
        st.session_state.get("local_roadmap_completed", [])
    )


def resume_stage() -> str:
    """Return a safe place for a returning student to continue."""
    allowed_stages = {
        "welcome", "intake", "intake_results", "personality",
        "personality_results", "dashboard",
    }
    saved_stage = str(st.session_state.get("app_stage", "dashboard"))
    return saved_stage if saved_stage in allowed_stages else "dashboard"


def admin_email() -> str:
    """Read the administrator email from Secrets or a local environment value."""
    try:
        return str(st.secrets.get("ADMIN_EMAIL", os.getenv("ADMIN_EMAIL", ""))).strip().lower()
    except FileNotFoundError:
        return os.getenv("ADMIN_EMAIL", "").strip().lower()


def is_admin() -> bool:
    return bool(admin_email()) and st.session_state.student_email.strip().lower() == admin_email()


def log_out() -> None:
    """Save the profile then clear this browser's active account."""
    save_current_student_state()
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.session_state.app_stage = "login"
    st.session_state.auth_mode = "login"
    st.session_state.light_mode = False
    st.session_state.nav_page = "Dashboard"
    try:
        st.query_params.pop("session", None)
    except Exception:
        pass


def theme_name() -> str:
    return "Light" if st.session_state.light_mode else "Dark"


def inject_styles() -> None:
    t = THEMES[theme_name()]
    st.markdown(f"""<style>
    @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Space+Grotesk:wght@500;600;700&display=swap');
    :root{{--bg:{t['bg']};--text:{t['text']};--muted:{t['muted']};--card:{t['card']};--soft:{t['soft']};--line:{t['line']};--sidebar:{t['sidebar']};--input:{t['input']};--input-text:{t['input_text']};--shadow:{t['shadow']};--score:{t['score']};--mentor:{t['mentor']};--violet:#7c3aed;--pink:#ef5e7d;--mint:#15bfa2}} *{{font-family:'DM Sans',sans-serif}} .stApp{{background:var(--bg);color:var(--text)}} #MainMenu,footer{{visibility:hidden}} header,[data-testid='stHeader']{{background:transparent!important;height:2.8rem!important}} [data-testid='stToolbar']{{visibility:visible!important;display:flex!important}} [data-testid='stToolbar'] button,[data-testid='stHeader'] button{{visibility:visible!important;display:flex!important;opacity:1!important;color:var(--text)!important;pointer-events:auto!important}} .block-container{{max-width:1500px;padding-top:2.2rem;padding-bottom:2.5rem}} [data-testid='stSidebar']{{background:var(--sidebar)!important;border-right:1px solid rgba(211,193,255,.24)!important}} [data-testid='stSidebar'] *{{color:#f8f5ff!important}} h1,h2,h3{{font-family:'Space Grotesk',sans-serif;color:var(--text)}}
    .brand{{display:flex;align-items:center;gap:10px;margin:3px 0 20px}}.brand-name{{color:var(--text);font:700 1.35rem 'Space Grotesk',sans-serif;white-space:nowrap}}.brand-name span{{color:#ff6b81}}.sidebar-tagline{{color:#cfc4eb;font-size:.73rem;white-space:nowrap}}.top-title{{font:700 2.25rem 'Space Grotesk',sans-serif;color:var(--text);letter-spacing:-1.4px;margin:0 0 3px}}.top-subtitle{{color:var(--muted);margin-bottom:18px}}.panel{{background:var(--card);border:1px solid var(--line);border-radius:18px;padding:20px;box-shadow:0 15px 38px var(--shadow);box-sizing:border-box}}.panel h3{{margin:0 0 8px}}.muted{{color:var(--muted)!important}}.accent{{color:#8b5cf6;font-weight:700}}.mint{{color:var(--mint);font-weight:700}}
    .choice-card{{background:var(--card);border:1px solid var(--line);border-radius:20px;padding:27px;min-height:250px;text-align:center;box-shadow:0 15px 38px var(--shadow)}}.choice-icon{{font-size:2.6rem;margin-bottom:9px}}.quiz-step{{color:#8b5cf6;font-size:.85rem;font-weight:700;margin-bottom:10px}}.question-card{{background:var(--card);border:1px solid var(--line);border-radius:20px;padding:29px;box-shadow:0 15px 38px var(--shadow)}}.question-number{{color:#8b5cf6;font-weight:700}}.question-text{{font:600 1.6rem 'Space Grotesk',sans-serif;color:var(--text);line-height:1.35;margin:13px 0 21px}}.progress-shell{{height:8px;background:rgba(124,58,237,.16);border-radius:999px;overflow:hidden;margin:11px 0 25px}}.progress-fill{{height:100%;background:linear-gradient(90deg,#7c3aed,#ef5e7d);border-radius:999px}}.result-code{{font:700 3.2rem 'Space Grotesk',sans-serif;color:#8b5cf6;letter-spacing:4px}}.result-number{{font:700 2.7rem 'Space Grotesk',sans-serif;color:var(--text)}}.match-grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:11px}}.match-card{{background:var(--soft);border:1px solid var(--line);border-radius:13px;padding:15px;min-height:160px;min-width:0}}.match-card h3{{font-size:clamp(1.15rem,2vw,1.55rem)!important;line-height:1.2!important;word-break:normal!important;overflow-wrap:normal!important;hyphens:none!important}}.match-card p{{word-break:normal!important;overflow-wrap:normal!important;hyphens:none!important}}.match-pill{{float:right;color:var(--mint);background:rgba(21,191,162,.13);padding:4px 8px;border-radius:8px;font-size:.74rem;font-weight:700}}.icon-bubble{{width:43px;height:43px;display:grid;place-items:center;border-radius:14px;background:linear-gradient(145deg,rgba(255,71,88,.34),rgba(19,12,31,.9));border:1px solid rgba(255,99,111,.62);box-shadow:inset 0 1px rgba(255,255,255,.2),0 0 14px rgba(255,48,73,.45);font-size:1.35rem}}.butterfly-mark{{color:#ff5066;text-shadow:0 0 8px #ff324c,0 0 18px rgba(255,50,76,.74);font-size:1.35rem}}.score-panel{{background:var(--score);border-radius:18px;padding:23px;color:#fff;min-height:228px}}.score-panel *{{color:#fff}}.big-score{{font:700 3.2rem 'Space Grotesk',sans-serif;margin:22px 0 8px}}.ai-card{{background:var(--mentor);border:1px solid rgba(236,91,122,.38);border-radius:18px;padding:20px;margin-bottom:17px}}.ai-card p{{color:var(--muted)}}
    .login-visual{{position:relative;min-height:610px;display:flex;align-items:center;justify-content:center;overflow:hidden}}.login-orbit{{position:absolute;width:470px;height:470px;border:1px dashed rgba(154,105,255,.34);border-radius:50%}}.login-message{{position:relative;z-index:2;max-width:500px;text-align:center;font:700 3.1rem/1.05 'Space Grotesk',sans-serif;color:var(--text);letter-spacing:-2px}}.login-message span{{color:#ef5e7d}}.float-career{{position:absolute;z-index:3;display:grid;place-items:center;width:93px;height:93px;border-radius:27px;border:1px solid var(--line);background:var(--soft);box-shadow:0 13px 32px var(--shadow);font-size:3rem;animation:career-drift 4s ease-in-out infinite}}.career-1{{top:48px;left:15%}}.career-2{{top:48px;right:15%;animation-delay:-1s}}.career-3{{top:235px;left:2%;animation-delay:-2s}}.career-4{{top:235px;right:2%;animation-delay:-.5s}}.career-5{{bottom:46px;left:17%;animation-delay:-2.5s}}.career-6{{bottom:46px;right:17%;animation-delay:-1.5s}}@keyframes career-drift{{50%{{transform:translateY(-12px) rotate(3deg)}}}}
    .st-key-ai_mentor_card{{background:var(--mentor);border:1px solid rgba(236,91,122,.44)!important;border-radius:17px;padding:12px 13px 16px;box-shadow:0 15px 38px var(--shadow);text-align:center}}[data-testid='stImage'] img{{filter:drop-shadow(0 0 7px rgba(163,99,255,.9)) drop-shadow(0 0 18px rgba(236,91,122,.42));animation:logo-glow 2.8s ease-in-out infinite;object-fit:contain!important}}@keyframes logo-glow{{50%{{filter:drop-shadow(0 0 12px rgba(181,114,255,1)) drop-shadow(0 0 30px rgba(255,91,141,.7))}}}}
    div[data-baseweb='input'],div[data-baseweb='input']>div,div[data-baseweb='textarea'],div[data-baseweb='textarea']>div{{background:var(--input)!important;border-color:var(--line)!important}}[data-testid='stTextInput'] input,[data-testid='stTextArea'] textarea,.stTextInput input,.stTextArea textarea,div[data-baseweb='input'] input,div[data-baseweb='textarea'] textarea{{background-color:var(--input)!important;color:var(--input-text)!important;-webkit-text-fill-color:var(--input-text)!important;caret-color:var(--input-text)!important;opacity:1!important;font-weight:600!important}}[data-testid='stTextInput'] input::placeholder,[data-testid='stTextArea'] textarea::placeholder,.stTextInput input::placeholder,.stTextArea textarea::placeholder{{color:var(--input-text)!important;-webkit-text-fill-color:var(--input-text)!important;opacity:.62!important}}.stButton>button,button[kind='primary'],[data-testid='stFormSubmitButton'] button{{background:linear-gradient(90deg,#7c3aed,#ef5e7d)!important;color:#fff!important;border:1px solid rgba(255,255,255,.16);border-radius:12px;font-weight:700;min-height:43px;box-shadow:0 8px 18px rgba(95,45,199,.24);transition:.24s}}.stButton>button *,[data-testid='stFormSubmitButton'] button *{{color:#fff!important;-webkit-text-fill-color:#fff!important;opacity:1!important}}.stButton>button:hover,button[kind='primary']:hover{{transform:translateY(-2px);color:#fff!important;background:linear-gradient(135deg,#8e50ef,#f1678c)!important;border-color:rgba(255,255,255,.68);box-shadow:inset 0 1px rgba(255,255,255,.82),0 12px 28px rgba(110,55,220,.32);backdrop-filter:blur(16px)}}[data-testid='stAlert']{{background:#fff3f4!important;border:2px solid #e23d55!important;border-radius:12px!important}}[data-testid='stAlert'] *,[data-testid='stAlert'] p,[data-testid='stAlert'] div{{color:#5d1020!important;-webkit-text-fill-color:#5d1020!important;opacity:1!important;font-weight:600!important}}[data-testid='stSidebar'] .stRadio label{{padding:7px 5px;border-radius:10px;background:linear-gradient(145deg,rgba(255,255,255,.1),rgba(145,98,255,.08));border:1px solid rgba(255,255,255,.1)}}
    /* Force every Streamlit control label and option to use a high-contrast
       theme colour. Some mobile browsers otherwise keep a faint default text
       colour after switching between light and dark mode. */
    [data-testid='stWidgetLabel'] *,[data-testid='stTextInput'] label *,[data-testid='stTextArea'] label *,[data-testid='stSelectbox'] label *,[data-testid='stCheckbox'] label *,[data-testid='stSlider'] label *,[data-testid='stRadio'] label,[data-testid='stRadio'] label *,[role='radiogroup'] label,[role='radiogroup'] label *{{color:var(--text)!important;-webkit-text-fill-color:var(--text)!important;opacity:1!important;font-weight:600!important;text-shadow:none!important}}[data-testid='stRadio'] [data-baseweb='radio'] span{{color:var(--text)!important;-webkit-text-fill-color:var(--text)!important;opacity:1!important}}[data-testid='stRadio'] label:hover,[role='radiogroup'] label:hover{{background:rgba(124,58,237,.12)!important;border-radius:8px}}[data-testid='stSelectbox'] [data-baseweb='select']>div,[data-testid='stSelectbox'] [data-baseweb='select'] input,[data-baseweb='select'] [role='combobox']{{background:var(--input)!important;color:var(--input-text)!important;-webkit-text-fill-color:var(--input-text)!important;opacity:1!important}}[data-baseweb='popover'],[data-baseweb='popover'] *{{color:#15121d!important;-webkit-text-fill-color:#15121d!important;opacity:1!important}}[data-testid='stCheckbox'] [data-baseweb='checkbox']{{background:var(--input)!important;border-color:var(--line)!important}}
    /* The sidebar uses radio controls too, so override the general form-label
       colour after all other radio rules. White text stays readable in both
       application themes against the permanent deep-purple sidebar. */
    [data-testid='stSidebar'] [data-testid='stRadio'] label,[data-testid='stSidebar'] [data-testid='stRadio'] label *,[data-testid='stSidebar'] [role='radiogroup'] label,[data-testid='stSidebar'] [role='radiogroup'] label *{{color:#fff!important;-webkit-text-fill-color:#fff!important;opacity:1!important;text-shadow:0 1px 2px rgba(0,0,0,.35)!important}}
    .stButton>button:disabled,[data-testid='stFormSubmitButton'] button:disabled{{background:#59536d!important;color:#d8d4e1!important;-webkit-text-fill-color:#d8d4e1!important;border-color:#706987!important;box-shadow:none!important;cursor:not-allowed!important;opacity:.72!important;transform:none!important}}
    /* Alerts are kept readable but neutral. Validation still appears, while
       an optional local-backend fallback never looks like an app failure. */
    [data-testid='stAlert']{{background:var(--card)!important;border:1px solid var(--line)!important;border-radius:12px!important;box-shadow:0 8px 22px var(--shadow)!important}}
    [data-testid='stAlert'] *,[data-testid='stAlert'] p,[data-testid='stAlert'] div{{color:var(--text)!important;-webkit-text-fill-color:var(--text)!important}}
    @media(max-width:900px){{.block-container{{padding:1rem}}.match-grid{{grid-template-columns:1fr}}.top-title{{font-size:1.9rem}}.question-text{{font-size:1.3rem}}}}
    </style>""", unsafe_allow_html=True)


def reset_quiz(mode: str) -> None:
    st.session_state.intake_mode = mode
    st.session_state.intake_index = 0
    st.session_state.intake_answers = {}
    # A new career quiz must not reuse old RIASEC ratings or old text-widget
    # values, otherwise the next results would mix two different attempts.
    st.session_state.personality_mode = None
    st.session_state.personality_index = 0
    st.session_state.personality_answers = {}
    st.session_state.personality_complete = False
    st.session_state.backend_profile = None
    st.session_state.backend_error = ""
    st.session_state.top_matches = []
    st.session_state.career_insights = {}
    st.session_state.score_error = ""
    for key in list(st.session_state):
        # Do not delete intake_mode/intake_index/intake_answers: they are the
        # new quiz state we have just set above. Only old widget values need
        # clearing before Streamlit redraws the form.
        if key.startswith(("widget_intake_", "radio_p_", "slider_p_")):
            del st.session_state[key]
    st.session_state.app_stage = "intake"
    save_current_student_state()


def begin_quiz_reattempt() -> None:
    """Clear an old attempt and let the student choose Quick or Complete again."""
    st.session_state.intake_mode = None
    st.session_state.intake_index = 0
    st.session_state.intake_answers = {}
    st.session_state.personality_mode = None
    st.session_state.personality_index = 0
    st.session_state.personality_answers = {}
    st.session_state.personality_complete = False
    st.session_state.backend_profile = None
    st.session_state.backend_error = ""
    st.session_state.top_matches = []
    st.session_state.career_insights = {}
    st.session_state.score_error = ""
    for key in list(st.session_state):
        if key.startswith(("widget_intake_", "radio_p_", "slider_p_")):
            del st.session_state[key]
    st.session_state.app_stage = "welcome"
    save_current_student_state()


def quit_current_quiz() -> None:
    """Leave a quiz without deleting answers already entered."""
    st.session_state.app_stage = "dashboard"
    save_current_student_state()


def begin_riasec_reattempt() -> None:
    """Keep the career quiz, but clear ratings so RIASEC can be taken again."""
    st.session_state.personality_mode = None
    st.session_state.personality_index = 0
    st.session_state.personality_answers = {}
    st.session_state.personality_complete = False
    st.session_state.backend_profile = None
    st.session_state.backend_error = ""
    st.session_state.top_matches = []
    st.session_state.career_insights = {}
    st.session_state.score_error = ""
    for key in list(st.session_state):
        if key.startswith(("radio_p_", "slider_p_")):
            del st.session_state[key]
    # Return to the existing chooser so the student can select Quick or Full.
    st.session_state.app_stage = "intake_results"
    save_current_student_state()


def open_ai_mentor() -> None:
    """Safe callback: sidebar widgets cannot be changed after they render."""
    st.session_state.nav_page = "AI Mentor"


def open_explore_careers() -> None:
    """Open the complete career catalogue from the dashboard card."""
    st.session_state.nav_page = "Explore Careers"


def open_career_quiz() -> None:
    """Open the quiz-length chooser for a student's first attempt."""
    st.session_state.app_stage = "welcome"
    save_current_student_state()


def open_dashboard_without_quiz() -> None:
    """Let a new account inspect the empty dashboard before taking a quiz."""
    st.session_state.app_stage = "dashboard"
    st.session_state.nav_page = "Dashboard"
    save_current_student_state()


def open_riasec_quiz() -> None:
    """Open the RIASEC choices after the written career quiz is complete."""
    st.session_state.app_stage = "intake_results"
    save_current_student_state()


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
    save_current_student_state()


def intake_questions() -> tuple[tuple[str, str], ...]:
    return SHORT_INTAKE if st.session_state.intake_mode == "short" else LONG_INTAKE


def personality_questions() -> tuple[tuple[str, str], ...]:
    return SHORT_RIASEC_QUESTIONS if st.session_state.personality_mode == "riasec_short" else RIASEC_QUESTIONS


CAREER_SIGNAL_SECTIONS = {
    # These are the answers that describe *what* the student wants to do.
    # Other sections (country, fees and learning format) still matter, but
    # guide university/scholarship matching rather than changing a career to
    # "Writer" just because a student chose a reading/writing learning style.
    "Academic performance",
    "Interests & passions",
    "Skills & strengths",
    "Hobbies & activities",
    "Drive, motivation & work values",
    "Career awareness & aspirations",
}


def career_interest_text() -> str:
    """Use the complete written quiz profile for matching.

    A student's preferred country, work style, school subjects and career
    goals can all add useful context.  Career keywords are still matched as
    complete words, so unrelated answers do not become a false career match.
    """
    answers = [
        str(st.session_state.intake_answers.get(f"intake_{index}", "")).strip().lower()
        for index, _question in enumerate(intake_questions())
    ]
    return " ".join(answer for answer in answers if answer)


def career_preference_text() -> str:
    """Return the career-relevant part of the written profile.

    The full quiz is retained for profile, university and scholarship
    recommendations.  This focused text prevents practical preferences such
    as country, budget, or learning format from masquerading as a career
    interest, while using every answer that communicates interests, skills,
    activities, academics, motivations or career aspirations.
    """
    answers = [
        str(st.session_state.intake_answers.get(f"intake_{index}", "")).strip().lower()
        for index, (section, _question) in enumerate(intake_questions())
        if section in CAREER_SIGNAL_SECTIONS
    ]
    return " ".join(answer for answer in answers if answer)


def labelled_quiz_answers() -> list[dict[str, str]]:
    """Give an AI model the question together with each saved answer."""
    profile: list[dict[str, str]] = []
    for index, (section, prompt) in enumerate(intake_questions()):
        answer = str(st.session_state.intake_answers.get(f"intake_{index}", "")).strip()
        if answer:
            profile.append({"section": section, "question": prompt, "answer": answer})
    return profile


def has_positive_career_keyword(text: str, keyword: str) -> bool:
    """Match a clear interest, but ignore 'I dislike/not interested in X'."""
    terms = (keyword, *DIRECT_CAREER_ALIASES.get(keyword, ()))
    for term in terms:
        pattern = re.compile(rf"(?<!\w){re.escape(term)}(?!\w)")
        for match in pattern.finditer(text.lower()):
            before = text[max(0, match.start() - 55):match.start()]
            negative_match = list(re.finditer(
                r"\b(?:no|not|never|don't|do not|didn't|did not|dislike|hate|avoid|isn't|is not|aren't|are not)\b",
                before,
            ))
            # Do not treat phrases such as “no time, but I like to dance” as
            # a rejection of dance. A contrast phrase after the last negative
            # word means the student is still expressing a positive interest.
            negative = bool(negative_match)
            if negative_match:
                after_negative = before[negative_match[-1].end():]
                if re.search(r"\b(?:but|however|although)\b", after_negative):
                    negative = False
            if not negative:
                return True
    return False


def local_riasec_scores() -> dict[str, int]:
    scores = {code: 0 for code in RIASEC}
    for index, (code, _) in enumerate(personality_questions()):
        scores[code] += int(st.session_state.personality_answers.get(f"p_{index}", 3))
    return scores


def intake_theme_scores() -> dict[str, int]:
    """Return lightweight interest signals from completed open-text answers."""
    # Do not let answers about budget, location, or preferred learning style
    # accidentally become a career interest. For example, selecting
    # "reading/writing" as a learning style should not force Writer results.
    combined = career_interest_text()
    scores: dict[str, int] = {code: 0 for code in RIASEC}
    for code, keywords in INTAKE_THEME_KEYWORDS.items():
        scores[code] = sum(
            has_positive_career_keyword(combined, keyword)
            for keyword in keywords
        )
    return scores


def active_theme_ranking() -> list[str]:
    """Use RIASEC after it is completed; otherwise use the discovery answers."""
    if st.session_state.personality_complete:
        scores = riasec_scores()
    else:
        scores = intake_theme_scores()
    return sorted(scores, key=scores.get, reverse=True)


def profile_confidence_score() -> int:
    """Estimate how specific the profile is; never return a fixed match value."""
    interest_text = career_interest_text()
    preference_text = career_preference_text()
    if not interest_text.strip():
        return 0

    meaningful_answers = [
        answer for answer in interest_text.split("\n")
        if len(answer.split()) >= 2
    ]
    # ``career_interest_text`` joins answers with spaces, so count completed
    # signal sections separately for a stable, explainable score.
    completed_sections = sum(
        bool(str(st.session_state.intake_answers.get(f"intake_{index}", "")).strip())
        for index, (section, _) in enumerate(intake_questions())
        if section in CAREER_SIGNAL_SECTIONS
    )
    word_count = len(re.findall(r"[a-zA-Z]+", interest_text))
    direct_interests = sum(
        has_positive_career_keyword(preference_text, keyword)
        for keyword in DIRECT_CAREER_KEYWORDS
    )
    active_themes = sum(value > 0 for value in intake_theme_scores().values())

    score = (
        45
        + min(16, completed_sections * 4)
        + min(14, word_count // 18)
        + min(12, direct_interests * 3)
        + min(8, active_themes * 2)
    )
    if st.session_state.personality_complete:
        # Completing RIASEC adds extra evidence, but does not claim certainty.
        score += 8
    return max(55, min(95, score))


def dashboard_suitability_score() -> int:
    """Show a changing profile-confidence score, not a hard-coded career score."""
    return profile_confidence_score()


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
    """Recognise optional local API failures without hiding real user errors."""
    message = str(error).lower()
    local_service = "127.0.0.1:8000" in message or "localhost:8000" in message
    network_failure = any(phrase in message for phrase in (
        "could not reach", "connection refused", "connection reset", "timed out",
    ))
    return local_service and network_failure


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


def direct_careers_from_text(text: str) -> tuple[str, ...]:
    """Return careers explicitly connected to words in a question or quiz."""
    groups: list[tuple[str, ...]] = []
    for keyword in sorted(DIRECT_CAREER_KEYWORDS, key=len, reverse=True):
        terms = (keyword, *DIRECT_CAREER_ALIASES.get(keyword, ()))
        if any(re.search(rf"(?<!\w){re.escape(term)}(?!\w)", text.lower()) for term in terms):
            groups.append(DIRECT_CAREER_KEYWORDS[keyword])
    found: list[str] = []
    # Interleave careers from every stated hobby/interest. This makes mixed
    # answers such as "dance and drawing" visibly represent both interests.
    for position in range(max((len(group) for group in groups), default=0)):
        for group in groups:
            if position < len(group):
                found.append(group[position])
    return tuple(dict.fromkeys(found))


def closest_career_keyword(text: str) -> str:
    """Recognise small spelling mistakes such as ``docotor`` → ``doctor``."""
    words = re.findall(r"[a-zA-Z]{3,}", text.lower())
    keywords = tuple(DIRECT_CAREER_KEYWORDS)
    for word in words:
        close = get_close_matches(word, keywords, n=1, cutoff=0.78)
        if close:
            return close[0]
    return ""


def job_titles_from_text(text: str) -> tuple[str, ...]:
    """Recognise any of the full local job catalogue in a mentor question."""
    lowered = text.lower()
    matches = [
        title for title in ALL_JOBS
        if len(title) >= 4 and re.search(rf"(?<!\w){re.escape(title.lower())}(?!\w)", lowered)
    ]
    return tuple(matches[:3])


def catalogue_careers_from_profile(text: str) -> tuple[str, ...]:
    """Find explicitly named roles in the complete 900+ career catalogue.

    This is deliberately conservative: a result is added only when the
    student's wording contains a whole career title or a distinctive part of
    it.  It gives uncommon roles in the supplied catalogue a route into the
    recommendations without guessing from unrelated profile answers.
    """
    lowered = text.lower()
    found: list[str] = list(job_titles_from_text(lowered))
    # A student may write "I want to be a geologist" while the catalogue entry
    # has extra wording. Match distinctive one-word titles as well, but avoid
    # generic words that appear in ordinary quiz sentences.
    ignored_words = {
        "career", "manager", "assistant", "specialist", "professional",
        "worker", "officer", "consultant", "technician", "engineer",
        "designer", "analyst", "teacher", "artist", "director", "scientist",
        "developer", "coordinator", "administrator", "executive", "operator",
    }
    answer_words = set(re.findall(r"[a-z][a-z-]{3,}", lowered))
    for title in ALL_JOBS:
        title_words = [word for word in re.findall(r"[a-z][a-z-]{3,}", title.lower()) if word not in ignored_words]
        if not title_words:
            continue
        # A rare role word, for example "geologist" or "cartographer", is a
        # strong enough signal on its own. Multi-word role names can also
        # match when all their distinctive words appear in the answer.
        if (len(title_words) == 1 and title_words[0] in answer_words) or (
            len(title_words) > 1 and all(word in answer_words for word in title_words)
        ):
            found.append(title)
    return tuple(dict.fromkeys(found))


def specific_skills_for_question(text: str) -> tuple[str, ...]:
    """Return precise learning priorities when a role is named in a question."""
    lowered = text.lower()
    for keyword in sorted(ROLE_SKILL_GUIDANCE, key=len, reverse=True):
        if re.search(rf"(?<!\w){re.escape(keyword)}(?!\w)", lowered):
            return ROLE_SKILL_GUIDANCE[keyword]
    return ()


def mentor_topic(question: str) -> tuple[str, tuple[str, ...], tuple[str, ...]]:
    """Identify the role the student asks about, before using profile defaults.

    The direct question must win over earlier quiz answers.  For example, a
    student interested in cooking can still ask a useful question about coding.
    """
    lowered = question.lower()
    matched_keywords = [
        keyword for keyword in sorted(DIRECT_CAREER_KEYWORDS, key=len, reverse=True)
        if re.search(rf"(?<!\w){re.escape(keyword)}(?!\w)", lowered)
    ]
    careers = direct_careers_from_text(lowered) or job_titles_from_text(lowered)
    skills = specific_skills_for_question(lowered)
    if matched_keywords:
        return matched_keywords[0].title(), careers[:3], skills
    fuzzy_keyword = closest_career_keyword(lowered)
    if fuzzy_keyword:
        fuzzy_careers = DIRECT_CAREER_KEYWORDS[fuzzy_keyword]
        fuzzy_skills = ROLE_SKILL_GUIDANCE.get(fuzzy_keyword, skills)
        return fuzzy_keyword.title(), fuzzy_careers[:3], fuzzy_skills
    if careers:
        return str(careers[0]), careers[:3], skills
    return "your selected career direction", career_suggestions()[:3], skills


def is_career_mentor_question(question: str) -> bool:
    """Keep the mentor career-focused while allowing natural student wording."""
    text = question.lower()
    guidance_words = (
        "career", "job", "course", "college", "university", "skill", "scholarship",
        "internship", "study", "degree", "subject", "resume", "interview", "education",
        "profession", "future", "stream", "admission", "salary", "salary", "placement",
        "roadmap", "qualification", "exam", "portfolio", "cv", "application",
    )
    # Match complete words/phrases only.  A plain ``word in text`` check made
    # short terms such as "ai" match unrelated words such as "pain".
    has_guidance_word = any(
        re.search(rf"(?<!\w){re.escape(word)}(?!\w)", text)
        for word in guidance_words
    )
    return bool(
        has_guidance_word
        or direct_careers_from_text(text)
        or job_titles_from_text(text)
        or closest_career_keyword(text)
    )


def is_friendly_mentor_message(question: str) -> bool:
    """Recognise greetings and ordinary conversational questions."""
    text = re.sub(r"[^a-z ]", " ", question.lower()).strip()
    greetings = {
        "hi", "hello", "hey", "good morning", "good afternoon", "good evening",
        "how are you", "how r you", "thank you", "thanks", "bye", "goodbye",
        "what are you doing", "what are u doing", "what do you do", "who are you",
        "what can you do", "are you real", "are you an ai",
    }
    return text in greetings


def friendly_mentor_reply(question: str) -> str:
    text = question.lower()
    if "what are you doing" in text or "what are u doing" in text:
        return "I’m here and ready to chat with you! I can answer questions, explain ideas, and help you explore careers, education, universities, scholarships, and skills whenever you need me."
    if "who are you" in text or "are you an ai" in text:
        return "I’m Career AI, an AI mentor built to help with questions, planning, learning, and career decisions. I can also have a normal conversation and explain general topics."
    if "what can you do" in text or "what do you do" in text:
        return "I can answer questions, explain concepts, compare options, suggest learning steps, and help with careers, courses, universities, scholarships, skills, and study plans."
    if "how" in text:
        return "I’m doing well, thank you! I’m ready to help you explore careers, courses, colleges, universities, scholarships, skills, internships, or study plans."
    if "thank" in text:
        return "You’re welcome! What would you like help with—career options, a course, universities, scholarships, skills, or a study plan?"
    if "bye" in text:
        return "Goodbye! You can return anytime for career, college, course, scholarship, or skill guidance."
    return "Hello! I’m Career AI. Tell me a career interest, course, college/university question, scholarship need, or skill goal, and I’ll help you plan your next step."


def is_wellbeing_question(question: str) -> bool:
    """Allow supportive health/wellbeing questions without giving diagnosis."""
    text = question.lower()
    wellbeing_words = (
        "health", "wellbeing", "well-being", "mental health", "stress",
        "burnout", "anxiety", "sleep", "tired", "overwhelmed", "mood",
        "focus", "concentration", "self care", "self-care",
    )
    return any(word in text for word in wellbeing_words)


def wellbeing_reply(question: str) -> str:
    """Give a short, safe wellbeing response rather than medical diagnosis."""
    return (
        "Your health is worth thinking about all the time—not only when it starts "
        "affecting studies or career plans. Pay attention early if sleep, energy, mood, "
        "stress, focus, or daily activities are becoming difficult. Talk to a trusted "
        "adult, doctor, counsellor, or qualified mental-health professional for personal "
        "advice. If you feel unsafe or think you may be in immediate danger, contact local "
        "emergency services or a crisis helpline now."
    )


def built_in_general_reply(question: str) -> str:
    """Useful fallback when a local/online model is unavailable."""
    if is_wellbeing_question(question):
        return wellbeing_reply(question)
    topic, careers, skills = mentor_topic(question)
    career_text = ", ".join(careers[:3]) or "the paths in your dashboard"
    skill_text = ", ".join(skills or SKILLS_BY_THEME[active_theme_ranking()[0]][:3])
    return (
        f"That is a thoughtful question. Relating it to your current profile, {topic} is a useful "
        f"starting point. You could explore {career_text} and strengthen {skill_text}. "
        "For a more detailed answer, try asking what you want to compare, learn, or decide next."
    )


def normalise_mentor_reply(reply: str) -> str:
    """Make replies comparable without being affected by punctuation or spacing."""
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]", " ", reply.lower())).strip()


def mentor_reply_is_repeated(reply: str) -> bool:
    """Reject an LLM answer that is effectively the same as a recent answer."""
    candidate = normalise_mentor_reply(reply)
    if len(candidate) < 35:
        return False
    for item in st.session_state.get("mentor_history", [])[-12:]:
        if chat_message_role(item) != "ai":
            continue
        previous = normalise_mentor_reply(chat_message_text(item))
        if previous and SequenceMatcher(None, candidate, previous).ratio() >= 0.84:
            return True
    return False


def non_repeating_career_reply(question: str) -> str:
    """Give a useful backup response when an AI model repeats an old answer."""
    topic, careers, skills = mentor_topic(question)
    skills_text = ", ".join(skills or SKILLS_BY_THEME[active_theme_ranking()[0]][:3])
    career_text = ", ".join(careers[:3]) or "the career paths in your dashboard"
    return (
        f"For your new question, “{question.strip()}”, focus on the exact decision in front of you about {topic}: "
        f"compare the day-to-day work, required qualifications, and entry route for {career_text}. "
        f"Useful skills to build first are {skills_text}. Tell me the country and education level you are aiming for, "
        "and I can make the next steps more specific."
    )


def built_in_mentor_reply(question: str) -> str:
    """Give question-aware career guidance in the free public app without an LLM/API."""
    text = question.lower()
    topic, question_careers, specific_skills = mentor_topic(question)
    careers = question_careers or career_suggestions()[:3]
    ranked = active_theme_ranking()
    primary = ranked[0]
    universities = university_recommendations(text)[:3]
    scholarships = recommended_scholarships(text)[:3]
    focus = ", ".join(careers)

    if any(word in text for word in ("scholarship", "financial aid", "funding", "fee", "afford")):
        options = "; ".join(item["name"] for item in scholarships)
        return f"For {focus}, start by checking: {options}. Compare eligibility, country or state rules, marks, financial-need requirements, deadlines, and documents. Prepare your marksheets, activity list, income documents, and recommendation letters early, then verify everything on the official scholarship website."
    if any(word in text for word in ("university", "universities", "college", "colleges", "campus", "admission", "apply")):
        options = "; ".join(f"{item['name']} ({item['field']})" for item in universities)
        return f"For {focus}, good places to research first are: {options}. Compare the course curriculum, location, entry requirements, total cost, scholarships, student support, and internship opportunities before applying. Tell me your preferred country, course, budget, and education level for more focused suggestions. You can also use the Universities Worldwide page to search by country or institution name."
    if any(word in text for word in ("skill", "skills", "learn", "learning", "certification", "certificate", "roadmap")):
        topic_skills = ", ".join(specific_skills or SKILLS_BY_THEME[primary][:3])
        return f"For {topic}, focus first on: {topic_skills}. Practise one of these through a small project or real activity, then keep it in a portfolio or evidence folder. After that, choose one beginner course to strengthen the skill you found most difficult."
    if any(word in text for word in ("resume", "cv", "interview", "portfolio", "linkedin")):
        return "Keep your resume to one clear page: education, relevant skills, projects/activities, achievements, and contact details. For interviews, prepare a 30-second introduction and two examples that show a skill, challenge, action, and result. Tailor both to the role you apply for."
    if any(word in text for word in ("course", "degree", "subject", "subjects", "stream", "major", "study")):
        return f"For {topic}, explore courses connected to {focus}. Open each syllabus and look for modules you genuinely enjoy. A good choice balances interest, your strengths, entry requirements, and the day-to-day work you want."
    if any(word in text for word in ("benefit", "benefits", "advantage", "advantages", "good", "pros", "why become", "why be")) and topic != "your selected career direction":
        return f"Potential benefits of becoming a {topic.lower()} include meaningful work in that field, the chance to build specialist expertise, varied career paths as you gain experience, and opportunities to make an impact. It also has real demands—training time, workload, competition, and responsibility—so try a small related activity or speak with someone in the field before deciding."
    if any(word in text for word in ("career", "job", "profession", "work", "role", "future", "coding", "design", "acting", "doctor", "engineer", "business", "psychology", "writer", "artist")):
        return (
            f"For {topic}, relevant paths include: {focus}. Here is a practical way to explore them:\n\n"
            "1. Learn the real day-to-day work: read official course pages and watch or speak to people in the field.\n"
            "2. Check the education route: identify the school subjects, entrance requirements, degree or certification needed in your country.\n"
            "3. Build one beginner skill: complete a short course, club activity, project, portfolio piece, or volunteering experience.\n"
            "4. Get real exposure: try shadowing, an internship, a competition, or a conversation with a professional.\n"
            "5. Compare your options: note which path fits your interests, strengths, preferred work style, training time, and budget.\n\n"
            "Do not decide from one activity alone. Try at least two small experiences and keep evidence of what you learned."
        )
    if topic != "your selected career direction":
        return f"For {topic}, start by exploring what the day-to-day work is really like, which qualifications are needed, the skills employers value, and the work environment you would prefer. The related paths in your catalogue are: {focus}. Try one small project, course, club, or conversation with someone in the field before making a long-term decision."
    return "I’m here for career and education guidance. Ask me about careers, courses, skills, universities, scholarships, resumes, interviews, or a learning roadmap, and I’ll help you plan the next step."


def expand_short_mentor_reply(question: str, reply: str) -> str:
    """Keep mentor answers useful even when an AI provider returns only one line.

    This runs locally, so it adds no extra API wait or API cost.  The original
    answer remains first, followed by a practical plan tailored to the topic.
    """
    if len(reply.split()) >= 120:
        return reply

    topic, suggested_careers, specific_skills = mentor_topic(question)
    careers = suggested_careers or career_suggestions()[:3]
    skills = specific_skills or SKILLS_BY_THEME[active_theme_ranking()[0]][:3]
    career_text = ", ".join(careers[:3]) or "the career direction you are exploring"
    skills_text = ", ".join(skills[:3]) or "communication, research, and practical problem-solving"
    lowered = question.lower()

    if any(word in lowered for word in ("scholarship", "financial aid", "funding", "fee", "afford")):
        actions = (
            "1. **Make an eligibility checklist:** note your country, course level, marks, income criteria, and any category-specific requirements.\n"
            "2. **Use official providers first:** shortlist scholarships from university, government, and trusted foundation websites.\n"
            "3. **Prepare documents early:** collect marksheets, ID, income evidence, references, essays, and test scores if required.\n"
            "4. **Track deadlines:** keep a calendar with opening date, closing date, required documents, and official application link.\n"
            "5. **Apply broadly:** include a mix of merit, need-based, subject-specific, and location-specific options."
        )
        example = "For example, make one folder per scholarship and tick off each document before submitting—never rely on a social-media post for eligibility rules."
    elif any(word in lowered for word in ("university", "universities", "college", "colleges", "campus", "admission", "apply")):
        actions = (
            "1. **Choose the course before the name:** compare the actual subjects, labs, placements, and specialisations offered.\n"
            "2. **Check entry requirements:** confirm subject prerequisites, grades, tests, portfolio rules, and application dates on the official site.\n"
            "3. **Compare total cost:** include tuition, housing, food, travel, visa, and available financial aid.\n"
            "4. **Look for real student evidence:** attend an open day, watch department sessions, or speak with current students.\n"
            "5. **Keep balanced choices:** apply to ambitious, realistic, and safer options that suit your country preference and budget."
        )
        example = "For example, two universities can offer the same degree title but have very different course modules and internship support."
    elif any(word in lowered for word in ("skill", "skills", "learn", "learning", "certification", "certificate", "roadmap")):
        actions = (
            f"1. **Start with one skill:** choose **{skills_text}** rather than trying to learn everything together.\n"
            "2. **Pick a beginner resource:** complete one short, reputable course or guided tutorial.\n"
            "3. **Create proof of learning:** make a small project, performance, write-up, or practical task.\n"
            "4. **Ask for feedback:** show it to a teacher, mentor, club leader, or someone working in the field.\n"
            "5. **Increase difficulty:** use the feedback to build a stronger second project for your portfolio."
        )
        example = "For example, a coding learner could build a tiny useful website; an aspiring musician could record and reflect on a short performance."
    elif any(word in lowered for word in ("resume", "cv", "interview", "portfolio", "linkedin")):
        actions = (
            "1. **Choose the target role:** tailor every resume, portfolio, or interview example to that role.\n"
            "2. **Show evidence:** add projects, activities, achievements, and the result of your work—not only a list of skills.\n"
            "3. **Use the STAR structure:** practise examples showing the situation, task, action, and result.\n"
            "4. **Keep it clear:** use simple headings, strong action verbs, and one page for an early-career resume.\n"
            "5. **Get a review:** ask a teacher, mentor, or professional to check it before you apply."
        )
        example = "For example, replace 'good communication' with a real example of organising an event, presenting research, or leading a group task."
    else:
        actions = (
            "1. **Understand the role:** read two reliable role descriptions and note the tasks you would enjoy and the tasks you would not.\n"
            "2. **Try it in a small way:** do one beginner activity such as a project, club, workshop, volunteering task, or conversation with a professional.\n"
            f"3. **Build core skills:** start with **{skills_text}** and save evidence of your work in a simple portfolio.\n"
            "4. **Check the study path:** compare subjects, entrance requirements, course length, cost, and certification needs for your preferred country.\n"
            "5. **Make a comparison table:** score each option for interest, strengths, training time, work environment, and future opportunities."
        )
        example = f"For example, spend two weeks trying one activity connected to {topic.lower()} and ask someone in that field about a normal workday."

    return (
        f"{reply.strip()}\n\n"
        f"### Why this matters\n"
        f"A good decision about **{topic}** comes from comparing real day-to-day work, the training route, "
        f"and whether the work fits your strengths. Related paths worth comparing are **{career_text}**.\n\n"
        f"### What to do next\n{actions}\n\n"
        f"### A realistic example\n"
        f"{example}"
    )


def openai_api_key() -> str:
    """Read the private key from Streamlit Secrets, never from source code."""
    try:
        return str(st.secrets.get("OPENAI_API_KEY", os.getenv("OPENAI_API_KEY", ""))).strip()
    except FileNotFoundError:
        return os.getenv("OPENAI_API_KEY", "").strip()


def openai_model() -> str:
    try:
        return str(st.secrets.get("OPENAI_MODEL", os.getenv("OPENAI_MODEL", DEFAULT_OPENAI_MODEL))).strip()
    except FileNotFoundError:
        return os.getenv("OPENAI_MODEL", DEFAULT_OPENAI_MODEL).strip()


def gemini_api_key() -> str:
    """Read the Gemini key from private Streamlit Secrets."""
    try:
        return str(st.secrets.get("GEMINI_API_KEY", os.getenv("GEMINI_API_KEY", ""))).strip()
    except FileNotFoundError:
        return os.getenv("GEMINI_API_KEY", "").strip()


def gemini_model() -> str:
    try:
        return str(st.secrets.get("GEMINI_MODEL", os.getenv("GEMINI_MODEL", DEFAULT_GEMINI_MODEL))).strip()
    except FileNotFoundError:
        return os.getenv("GEMINI_MODEL", DEFAULT_GEMINI_MODEL).strip()


def ollama_api_url() -> str:
    """Read a local Ollama server URL; no paid API key is required."""
    try:
        return str(st.secrets.get("OLLAMA_URL", os.getenv("OLLAMA_URL", DEFAULT_OLLAMA_URL))).rstrip("/")
    except FileNotFoundError:
        return os.getenv("OLLAMA_URL", DEFAULT_OLLAMA_URL).rstrip("/")


def ollama_model() -> str:
    try:
        return str(st.secrets.get("OLLAMA_MODEL", os.getenv("OLLAMA_MODEL", DEFAULT_OLLAMA_MODEL))).strip()
    except FileNotFoundError:
        return os.getenv("OLLAMA_MODEL", DEFAULT_OLLAMA_MODEL).strip()


def ollama_mentor_reply(question: str) -> tuple[str, str]:
    """Use a local Ollama model for a natural, profile-aware mentor reply."""
    profile_summary = {
        "student_name": profile_name(),
        "quiz_answers": labelled_quiz_answers(),
        "riasec_themes": [RIASEC[code][0] for code in active_theme_ranking()[:3]],
        "suggested_careers": list(career_suggestions()[:5]),
    }
    instructions = (
        "You are Career AI, a warm and accurate career mentor for students. "
        "Your specialty is careers, education, skills, courses, universities, scholarships, "
        "internships, portfolios, resumes, interviews, and study plans. You may also answer "
        "ordinary general questions politely and helpfully. "
        "Use the student profile where useful, but never invent marks, rankings, admission "
        "requirements, scholarship deadlines, fees, or guarantees. For meaningful questions, give a detailed but "
        "easy-to-read answer of at least 150 words with an explanation, examples, and 3 to 5 practical next steps. "
        "Say to check official sources for current requirements. "
        "Answer the newest question directly. Do not reuse an earlier answer, even if the "
        "student has a different career interest from their saved profile."
    )
    # Keep the previous conversation first. The question being asked must be
    # last, otherwise the model can answer an older message repeatedly.
    history = st.session_state.mentor_history[-6:]
    messages = [{"role": "system", "content": instructions}]
    for item in history:
        role = "user" if chat_message_role(item) == "student" else "assistant"
        messages.append({"role": role, "content": chat_message_text(item)})
    messages.append({
        "role": "user",
        "content": (
            f"Student profile:\n{json.dumps(profile_summary, ensure_ascii=False)}\n\n"
            f"Answer this NEW question directly. Do not repeat an earlier answer: {question}"
        ),
    })
    request = Request(
        f"{ollama_api_url()}/api/chat",
        data=json.dumps({"model": ollama_model(), "messages": messages, "stream": False}).encode("utf-8"),
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=90) as response:
            data = json.loads(response.read().decode("utf-8"))
        reply = str((data.get("message") or {}).get("content") or "").strip()
        if not reply:
            return "", "Ollama did not return a reply."
        return reply, ""
    except HTTPError as error:
        details = error.read().decode("utf-8", errors="replace")
        return "", f"Ollama could not use model '{ollama_model()}': {details}"
    except URLError:
        return "", "Ollama is not running. Start it, then try again."
    except (OSError, json.JSONDecodeError) as error:
        return "", f"Ollama could not answer right now: {error}"


def gemini_mentor_reply(question: str) -> tuple[str, str]:
    """Use Gemini through its OpenAI-compatible API when a Gemini key is set."""
    api_key = gemini_api_key()
    if not api_key:
        return "", "No Gemini key is configured."
    if OpenAI is None:
        return "", "The AI compatibility package is not installed yet."

    career_matches = ", ".join(career_suggestions()[:5]) or "Not available yet"
    profile_summary = {
        "student_name": profile_name(),
        "quiz_answers": labelled_quiz_answers(),
        "riasec_completed": bool(st.session_state.personality_complete),
        "riasec_themes": [RIASEC[code][0] for code in active_theme_ranking()[:3]],
        "suggested_careers": career_matches,
    }
    instructions = (
        "You are Career AI, a warm, accurate career mentor for students. "
        "Give a direct, personalised, detailed answer to the newest question. "
        "Use the student profile only when helpful; the newest question matters most. "
        "Do not repeat earlier answers or assume a different career from the profile. "
        "Answer naturally in the format that best fits the question: paragraphs, bullets, or a short list. "
        "Do not use a fixed template, repeated headings, or the same generic plan for every question. "
        "Give enough explanation and specific examples to be useful, usually around 150–350 words for a meaningful question, "
        "but be shorter when the question is simple. Be honest about uncertainty. For university, scholarships, fees, "
        "deadlines, and entry requirements, tell the student to verify facts on the official website. "
        "You may politely answer ordinary general questions too."
    )
    prompt = (
        f"Student profile (background only):\n{json.dumps(profile_summary, ensure_ascii=False)}\n\n"
        f"Answer only this new question, not an earlier one: {question}"
    )
    try:
        client = OpenAI(
            api_key=api_key,
            base_url=GEMINI_OPENAI_BASE_URL,
            timeout=35.0,
            max_retries=0,
        )
        response = client.chat.completions.create(
            model=gemini_model(),
            messages=[
                {"role": "system", "content": instructions},
                {"role": "user", "content": prompt},
            ],
        )
        reply = str(response.choices[0].message.content or "").strip()
        if not reply:
            return "", "Gemini did not return a reply."
        return reply, ""
    except Exception as error:
        return "", f"Gemini request failed ({error.__class__.__name__})."


def gpt_mentor_reply(question: str) -> tuple[str, str]:
    """Generate a safe, profile-aware response using GPT when Secrets are set."""
    api_key = openai_api_key()
    if not api_key:
        return "", "No OpenAI key is configured."
    if OpenAI is None:
        return "", "The OpenAI package is not installed yet."

    career_matches = ", ".join(career_suggestions()[:5]) or "Not available yet"
    profile_summary = {
        "student_name": profile_name(),
        "quiz_answers": labelled_quiz_answers(),
        "riasec_completed": bool(st.session_state.personality_complete),
        "riasec_themes": [RIASEC[code][0] for code in active_theme_ranking()[:3]],
        "suggested_careers": career_matches,
    }
    instructions = (
        "You are Career AI, a warm, accurate career mentor for students. "
        "Your specialty is careers, education, skills, courses, colleges/universities, "
        "scholarships, internships, portfolios, resumes, interviews, and study plans. "
        "You may also answer ordinary general questions politely and helpfully. "
        "Use the supplied student profile where useful, but do not invent marks, rankings, scholarship deadlines, "
        "admissions requirements, or facts. Do not guarantee outcomes. Give practical next steps. "
        "For scholarships and university applications, remind the student to verify current eligibility, fees, deadlines, "
        "and official information. The direct question is more important than the profile. Do not answer based on an "
        "older question or repeat a previous reply. Answer naturally rather than following a fixed response template."
    )
    prompt = (
        f"Student profile (background only):\n{json.dumps(profile_summary, ensure_ascii=False)}\n\n"
        f"Answer only this new question, not any earlier question: {question}"
    )
    try:
        # Avoid long automatic retries. If GPT is temporarily unavailable, the
        # app immediately gives the student a detailed local guide instead.
        client = OpenAI(api_key=api_key, timeout=25.0, max_retries=0)
        response = client.responses.create(
            model=openai_model(),
            instructions=instructions,
            input=prompt,
            max_output_tokens=800,
        )
        reply = (response.output_text or "").strip()
        if not reply:
            return "", "GPT did not return a reply."
        return reply, ""
    except AuthenticationError:
        return "", "GPT could not authenticate. Check that OPENAI_API_KEY in Streamlit Secrets is a complete active API key, then save and reboot the app."
    except RateLimitError:
        return "", "GPT has no available API credit or has reached its usage limit. Add a small billing credit or raise the API usage limit, then try again."
    except APIConnectionError:
        return "", "GPT could not be reached right now. Please try again in a moment."
    except Exception as error:
        # Keep the visible error safe, but retain the error type so the UI can
        # truthfully say when it used local guidance instead of GPT.
        return "", f"GPT request failed ({error.__class__.__name__})."


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
    # Use the answers that genuinely describe the student's direction for
    # direct matching.  The full quiz is still used for theme, university and
    # scholarship recommendations elsewhere in the app.
    written_answers = career_preference_text()
    direct_groups: list[tuple[str, ...]] = []
    # Check longest phrases first so "social work" is not lost inside another
    # match. Each matched interest becomes a group so recommendations can be
    # mixed instead of showing three careers from only the first hobby.
    for keyword in sorted(DIRECT_CAREER_KEYWORDS, key=len, reverse=True):
        if has_positive_career_keyword(written_answers, keyword):
            direct_groups.append(DIRECT_CAREER_KEYWORDS[keyword])
    direct: list[str] = []
    for position in range(max((len(group) for group in direct_groups), default=0)):
        for group in direct_groups:
            if position < len(group):
                direct.append(group[position])

    # Support any explicitly named profession in the complete job catalogue,
    # not only the curated everyday-interest keywords above. This keeps a
    # role a student types (for example, geologist or cartographer) ahead of
    # broad RIASEC fallback careers.
    catalogue_matches = list(catalogue_careers_from_profile(written_answers))
    direct = list(dict.fromkeys(direct + catalogue_matches))

    # An explicit interest, hobby, skill or career goal is stronger evidence
    # than a broad personality theme. Keep at least the student's first four
    # direct options together so "playing instruments" shows music careers,
    # not a Robotics Engineer inserted between them.
    if direct:
        return tuple(dict.fromkeys(direct + list(theme_careers)))

    if st.session_state.personality_complete:
        return tuple(theme_careers)

    # Before RIASEC is completed, the student's explicit written interests
    # remain the clearest signal, followed by related career-theme options.
    return tuple(theme_careers)


def career_match_reason(career: str, primary: str, secondary: str, written_answers: str) -> tuple[bool, str]:
    """Explain each card using its own direct interest or RIASEC connection."""
    matched_interests = [
        keyword
        for keyword, options in DIRECT_CAREER_KEYWORDS.items()
        if career in options and has_positive_career_keyword(written_answers, keyword)
    ]
    if matched_interests:
        interest = max(matched_interests, key=len)
        return True, f"{career} turns your interest in {interest} into a possible career path."

    themes = CAREER_THEME_CODES.get(career, ())
    theme_explanations = {
        "Realistic": "practical, hands-on problem solving",
        "Investigative": "analysis, research, and understanding how things work",
        "Artistic": "creative expression and original ideas",
        "Social": "helping, teaching, and working closely with people",
        "Enterprising": "leading, persuading, and turning ideas into action",
        "Conventional": "organising information, accuracy, and structured work",
    }
    if primary in themes and secondary in themes:
        return False, (
            f"{career} suits you because your quiz shows interest in "
            f"{theme_explanations[RIASEC[primary][0]]} and "
            f"{theme_explanations[RIASEC[secondary][0]]}. This career uses both every day."
        )
    if primary in themes:
        return False, (
            f"{career} suits you because your strongest quiz theme is "
            f"{RIASEC[primary][0]}: {theme_explanations[RIASEC[primary][0]]}."
        )
    return False, f"{career} is related to the themes and interests shown in your quiz answers."


def relevant_career_results() -> tuple[dict[str, object], ...]:
    """Create broad, theme-based results from the full UI career map.

    The backend seed currently has only six careers, whereas the UI has many
    more career paths. These results preserve the student's RIASEC direction
    instead of letting the small seed list dominate the dashboard.
    """
    ranked = active_theme_ranking()
    primary, secondary = ranked[:2]
    careers = career_suggestions()[:6]
    written_answers = career_preference_text()
    profile_score = profile_confidence_score()
    results: list[dict[str, object]] = []
    for position, career in enumerate(careers):
        themes = CAREER_THEME_CODES.get(career, (primary,))
        direct_match, reason = career_match_reason(career, primary, secondary, written_answers)
        alignment = (
            profile_score
            if direct_match
            else profile_score - 3 if primary in themes and secondary in themes
            else profile_score - 7 if primary in themes
            else profile_score - 12
        )
        results.append({
            "career": career,
            "score": max(55, alignment - position * 3),
            "reason": reason,
        })
    return tuple(results)


def displayed_career_matches() -> tuple[dict[str, object], ...]:
    """Prefer a broad local result set if backend results are too limited."""
    # A brand-new account must not receive default careers before answering
    # either quiz. This guard also protects other pages that reuse this helper.
    has_written_attempt = any(
        bool(str(value).strip()) for value in st.session_state.get("intake_answers", {}).values()
    )
    has_riasec_attempt = any(
        value in {1, 2, 3, 4, 5}
        for value in st.session_state.get("personality_answers", {}).values()
    )
    if not has_written_attempt and not has_riasec_attempt:
        return tuple()
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


def automatic_roadmap_steps() -> tuple[dict[str, object], ...]:
    """Build an honest roadmap from work the student has actually completed.

    Quiz milestones are never marked by a manual checkbox.  They update from
    the saved answers, so the same progress is shown after logging in again.
    """
    career_total = len(intake_questions()) if st.session_state.intake_mode in {"short", "long"} else 0
    career_answered = sum(
        bool(str(st.session_state.intake_answers.get(f"intake_{index}", "")).strip())
        for index in range(career_total)
    )
    career_complete = bool(career_total and career_answered >= career_total)

    riasec_total = len(personality_questions()) if st.session_state.personality_mode else 0
    riasec_answered = sum(
        value is not None
        for value in st.session_state.personality_answers.values()
    )
    riasec_complete = bool(
        st.session_state.personality_complete
        and riasec_total
        and riasec_answered >= riasec_total
    )
    primary, secondary = active_theme_ranking()[:2]
    careers = career_suggestions()[:3]

    return (
        {
            "id": 1,
            "title": "Complete your Career Discovery Quiz",
            "description": f"{career_answered} of {career_total} career-quiz answers saved." if career_total else "Choose a Quick or Complete Career Discovery Quiz to begin.",
            "completed": career_complete,
        },
        {
            "id": 2,
            "title": "Build your written career profile",
            "description": "Your interests, strengths, study preferences, goals, location choices and activities are now used in your recommendations." if career_complete else "This unlocks automatically after the Career Discovery Quiz is complete.",
            "completed": career_complete,
        },
        {
            "id": 3,
            "title": "Complete your RIASEC Personality Quiz",
            "description": f"{riasec_answered} of {riasec_total} RIASEC ratings saved." if riasec_total else "Take a Quick or Full RIASEC Quiz to refine your work-style match.",
            "completed": riasec_complete,
        },
        {
            "id": 4,
            "title": "Identify your Holland Code work style",
            "description": f"Your strongest current work-style themes are {RIASEC[primary][0]} and {RIASEC[secondary][0]}." if riasec_complete else "This is calculated automatically after the RIASEC quiz.",
            "completed": riasec_complete,
        },
        {
            "id": 5,
            "title": "Generate personalised career matches",
            "description": f"Your written answers and RIASEC profile are now combined. Compare: {', '.join(careers)}." if career_complete and riasec_complete else "This unlocks automatically once both quizzes are complete.",
            "completed": career_complete and riasec_complete,
        },
        {
            "id": 6,
            "title": "Prepare your skills and course direction",
            "description": f"Your learning focus is ready: {', '.join(SKILLS_BY_THEME[primary][:3])}." if riasec_complete else "Complete RIASEC to personalise your skill priorities.",
            "completed": career_complete and riasec_complete,
        },
        {
            "id": 7,
            "title": "Unlock relevant university and scholarship routes",
            "description": "Your University and Scholarship pages can now use your career direction, location preferences and interests." if career_complete and riasec_complete else "Complete both quizzes to unlock the most focused recommendations.",
            "completed": career_complete and riasec_complete,
        },
        {
            "id": 8,
            "title": "Compare your top career paths",
            "description": "Read the day-to-day work, entry requirements, courses and opportunities for at least two of your suggested careers.",
            "completed": False,
        },
        {
            "id": 9,
            "title": "Start a skill-building project or course",
            "description": "Choose one small project, club, course, competition or practice activity linked to your preferred path.",
            "completed": False,
        },
        {
            "id": 10,
            "title": "Build a portfolio and plan your next application",
            "description": "Save projects, achievements and certificates, then check official college, scholarship or internship requirements.",
            "completed": False,
        },
    )


def university_recommendations(extra_context: str = "") -> tuple[dict[str, str], ...]:
    """Match universities to quiz interests, with optional mentor-question context."""
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
    written_answers = " ".join(str(answer).lower() for answer in st.session_state.intake_answers.values()) + " " + extra_context.lower()
    sport_terms = ("sport", "sports", "cricket", "football", "athlete", "athletics", "coach", "physical education", "fitness", "yoga")
    health_sport_terms = ("physiotherapy", "physiotherapist", "sports medicine", "sports doctor")
    wants_sports = any(re.search(rf"(?<!\w){re.escape(term)}(?!\w)", written_answers) for term in sport_terms)
    wants_sports_health = any(re.search(rf"(?<!\w){re.escape(term)}(?!\w)", written_answers) for term in health_sport_terms)
    # Detect any country written by the student, not only a short hard-coded
    # list. Aliases cover the names most commonly used in applications.
    catalogue_countries = {university["country"] for university in UNIVERSITY_CATALOG}
    # Add every country available in the worldwide directory, then normalise
    # common short forms to the country labels used by our curated catalogue.
    country_aliases = {country.lower(): country for country in GLOBAL_UNIVERSITY_COUNTRIES}
    country_aliases.update({country.lower(): country for country in catalogue_countries})
    country_aliases.update({
        "us": "USA", "usa": "USA", "united states": "USA",
        "uk": "UK", "united kingdom": "UK", "uae": "United Arab Emirates",
        "korea": "South Korea", "south korea": "South Korea",
    })
    country_choices = tuple(dict.fromkeys(
        country for phrase, country in country_aliases.items()
        if re.search(rf"(?<!\w){re.escape(phrase)}(?!\w)", written_answers)
    ))
    karnataka_terms = ("karnataka", "bengaluru", "bangalore", "mysuru", "mysore", "manipal", "hubballi", "surathkal")
    wants_karnataka = any(re.search(rf"(?<!\w){re.escape(term)}(?!\w)", written_answers) for term in karnataka_terms)
    direct_fields = [
        field for keyword, fields in CAREER_FIELD_SIGNALS.items()
        if re.search(rf"(?<!\w){re.escape(keyword)}(?!\w)", written_answers)
        for field in fields
    ]
    theme_fields = [field for theme in themes for field in field_keywords[theme]]
    preferred_fields = tuple(dict.fromkeys(direct_fields + theme_fields))

    def field_score(university: dict[str, str]) -> int:
        field = university["field"].lower()
        # The subject/career must come first. Country is only a tie-breaker:
        # an acting student who writes "US" should get US film/arts options,
        # not an unrelated US business university.
        subject_score = sum(20 if signal in direct_fields else 2 for signal in preferred_fields if signal.lower() in field)
        # A requested country is a strong requirement, but course relevance
        # still affects the order within that country.
        country_score = 100 if university["country"] in country_choices else 0
        local_score = 12 if wants_karnataka and any(term in university["name"].lower() for term in karnataka_terms) else 0
        # An explicit sport interest is stronger evidence than a broad RIASEC
        # Social/Realistic theme. Keep healthcare universities out unless the
        # student asked for physiotherapy or sports medicine specifically.
        sport_score = 500 if wants_sports and "sports" in field else 0
        healthcare_penalty = -250 if wants_sports and not wants_sports_health and "healthcare" in field and "sports" not in field else 0
        return country_score + local_score + subject_score + sport_score + healthcare_penalty

    country_matches = [university for university in UNIVERSITY_CATALOG if university["country"] in country_choices]

    # The bundled list is deliberately curated and cannot contain every
    # university on earth. When a student explicitly gives a country (Japan,
    # Brazil, Kenya, etc.), supplement it with that country's institutions
    # from the public worldwide directory instead of silently showing an
    # unrelated default country.
    if country_choices:
        requested_country = country_choices[0]
        directory_country = {
            "USA": "United States",
            "UK": "United Kingdom",
        }.get(requested_country, requested_country)
        directory_rows = search_worldwide_universities("", directory_country)
        existing_names = {university["name"].lower() for university in country_matches}
        for row in directory_rows:
            name = row["name"].strip()
            if not name or name.lower() in existing_names:
                continue
            city = f" · {row['city']}" if row.get("city") else ""
            country_matches.append({
                "name": name,
                "country": requested_country,
                "field": "Worldwide university directory",
                "reputation": f"Institution listed for {requested_country}{city}",
                "scholarships": "Check this university's official scholarships and financial-aid page.",
            })
            existing_names.add(name.lower())
            if len(country_matches) >= 12:
                break
    catalogue = country_matches if country_matches else list(UNIVERSITY_CATALOG)
    ranked_matches = sorted(catalogue, key=field_score, reverse=True)
    return tuple((ranked_matches or list(UNIVERSITY_CATALOG))[:3])


def recommendation_career_text() -> str:
    """Relevant career names are additional evidence for courses and funding."""
    return " ".join(match_title(match).lower() for match in displayed_career_matches())


def recommended_scholarships(extra_context: str = "") -> tuple[dict[str, str], ...]:
    """Recommend funding from explicit study interests before generic awards.

    A scholarship cannot honestly be guaranteed from an interest alone.  The
    cards therefore prioritise subject-specific university aid and relevant
    funding *routes*, then show named public programmes only when their stated
    eligibility matches the student's country or subject.
    """
    # Do not use old dashboard career cards as evidence here: they can belong
    # to an earlier attempt. The current written-interest answers are the
    # source of truth for a fresh recommendation.
    interest_context = career_interest_text() + " " + extra_context.lower()
    location_context = " ".join(
        str(answer).lower() for answer in st.session_state.intake_answers.values()
    ) + " " + extra_context.lower()
    wants_karnataka = any(re.search(rf"(?<!\w){re.escape(term)}(?!\w)", location_context) for term in ("karnataka", "bengaluru", "bangalore", "mysuru", "mysore", "manipal", "hubballi", "surathkal"))
    country_aliases = {country.lower(): country for country in GLOBAL_UNIVERSITY_COUNTRIES}
    country_aliases.update({
        "us": "USA", "usa": "USA", "united states": "USA", "uk": "UK",
        "united kingdom": "UK", "uae": "United Arab Emirates", "korea": "South Korea",
    })
    wanted_countries = tuple(dict.fromkeys(
        country for phrase, country in country_aliases.items()
        if re.search(rf"(?<!\w){re.escape(phrase)}(?!\w)", location_context)
    ))
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
        if any(has_positive_career_keyword(interest_context, trigger) for trigger in triggers)
    )
    field_routes = {
        "stem": ("STEM merit and research funding route", "Technology, engineering and science universities", "Look for department merit awards, research assistantships and government STEM schemes.", "Students pursuing coding, data, engineering, AI, science or environment programmes"),
        "arts": ("Creative-arts portfolio scholarship route", "Art, design, film, fashion and media universities", "Look for portfolio-based merit scholarships, creative bursaries and programme-specific fee waivers.", "Students pursuing acting, film, design, music, writing, fashion or other creative fields"),
        "health": ("Healthcare and medical education support route", "Medical, nursing and health-sciences institutions", "Check institutional merit/need aid, government health schemes and programme-specific grants.", "Students pursuing medicine, nursing, psychology, therapy or allied health"),
        "business": ("Business and entrepreneurship scholarship route", "Business schools and management programmes", "Look for merit awards, leadership scholarships, women-in-business awards and need-based tuition support.", "Students pursuing business, marketing, finance, accounting or entrepreneurship"),
        "law": ("Law and public-policy scholarship route", "Law schools and public-policy programmes", "Check merit-cum-means support, debate/leadership awards and university financial-aid pages.", "Students pursuing law, policy or politics"),
        "sports": ("Sports-performance and athletic scholarship route", "Sports universities, clubs and physical-education programmes", "Check sports quotas, athletic scholarships, coaching-academy support and university sports bursaries.", "Students pursuing cricket, football, coaching, athletics, fitness or physical education"),
        "education": ("Education and social-impact funding route", "Education, teaching and social-science programmes", "Look for teaching fellowships, community-service awards and university need-based aid.", "Students pursuing teaching, education or social work"),
    }
    focused_routes = [
        {"name": field_routes[label][0], "funded_by": field_routes[label][1], "coverage": field_routes[label][2], "best_for": field_routes[label][3]}
        for label in keywords
    ]
    university_aid = [
        {
            "name": f"{university['name']} financial aid",
            "funded_by": university["name"],
            "coverage": university["scholarships"],
            "best_for": f"{university['field']} · {university['country']}",
        }
        for university in university_recommendations(extra_context)
    ]
    def unique(items: list[dict[str, str]]) -> tuple[dict[str, str], ...]:
        result: list[dict[str, str]] = []
        seen: set[str] = set()
        for item in items:
            key = item["name"].lower()
            if key not in seen:
                result.append(item)
                seen.add(key)
        return tuple(result[:5])
    ranked_scholarships = sorted(
        SCHOLARSHIP_CATALOG,
        key=lambda scholarship: (
            (20 if wants_karnataka and "karnataka" in " ".join(scholarship.values()).lower() else 0)
            + 30 * sum(country.lower() in " ".join(scholarship.values()).lower() for country in wanted_countries)
            + sum(keyword in " ".join(scholarship.values()).lower() for keyword in keywords)
        ),
        reverse=True,
    )
    # If the student named a country, real country-specific programmes (for
    # example Japan's MEXT) are shown before broader options. If our curated
    # data has no named programme for that country, direct them to the matched
    # country's university financial-aid offices rather than pretending a
    # scholarship from another country applies.
    country_specific = [
        scholarship for scholarship in ranked_scholarships
        if any(country.lower() in " ".join(scholarship.values()).lower() for country in wanted_countries)
    ]
    if wanted_countries:
        country = wanted_countries[0]
        country_route = {
            "name": f"{country} university financial-aid route",
            "funded_by": "Selected universities in your chosen country",
            "coverage": "Check tuition grants, merit awards, need-based aid, and the official government study portal.",
            "best_for": f"Students planning to study in {country}",
        }
        # Subject match comes before country-wide generic programmes.
        return unique(focused_routes + university_aid + country_specific + [country_route] + ranked_scholarships)
    if focused_routes or wants_karnataka:
        # A student who chose acting should see creative funding routes, not a
        # repeated list of generic overseas fellowships.
        return unique(focused_routes + university_aid + ranked_scholarships)
    # No subject or location was provided: give only transparent broad routes.
    return unique(university_aid + list(SCHOLARSHIP_CATALOG[:2]))


def university_recommendation_reason() -> str:
    """Explain the exact profile signal used for the university cards."""
    written_answers = " ".join(str(answer).lower() for answer in st.session_state.intake_answers.values())
    selected_country = next(
        (country for country in GLOBAL_UNIVERSITY_COUNTRIES if re.search(rf"(?<!\w){re.escape(country.lower())}(?!\w)", written_answers)),
        "",
    )
    if selected_country:
        return f"Prioritising universities and funding routes in {selected_country}, then matching them to your interests."
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
    """Reject blank, placeholder and obvious keyboard-mash quiz answers."""
    cleaned = answer.strip().lower()
    compact = re.sub(r"\s+", "", cleaned)
    letters = re.sub(r"[^a-z]", "", cleaned)
    not_applicable_answers = {
        "na", "n/a", "n.a.", "not applicable", "not available",
        "not sure", "not yet", "prefer not to say", "none",
    }
    blocked = {
        "asdf", "asdfgh", "qwerty", "qwertyuiop", "test", "testing",
        "idk", "xxx", "abc", "abcd", "random",
        "iuhdjcknn", "jhjhjh", "fghjkl", "hjkl", "zxcv", "zxcvbn",
    }
    keyboard_mash_fragments = ("asdf", "qwer", "zxcv", "hjkl", "lkjh", "iuhd", "jckn", "mnbv", "poiuy")
    valid_short_answers = {
        "yes", "no", "y", "n", "true", "false", "maybe", "us", "usa",
        "uk", "uae", "eu", "india", "canada", "australia", "germany",
        "france", "japan", "china", "singapore", "male", "female", "other",
    }
    if not cleaned or cleaned in blocked:
        return False
    # Students can use N/A for questions that genuinely do not apply to them.
    if cleaned in not_applicable_answers:
        return True
    # Many profile questions genuinely need concise factual responses.
    if cleaned in valid_short_answers:
        return True
    if re.fullmatch(r"[+-]?\d+(?:\.\d+)?\s*%?", cleaned):
        return True
    # Reject common keyboard runs and obvious nonsense such as "iuhdjcknn".
    if any(fragment in compact for fragment in keyboard_mash_fragments):
        return False
    # A run such as "isjjjd" or "helloooo" is almost always placeholder
    # text in this questionnaire, not an answer a recommendation can use.
    if re.search(r"([a-z])\1{2,}", letters):
        return False
    if len(cleaned) < 3 or (letters and len(set(letters)) == 1):
        return False
    if len(letters) < 2:
        return False
    # Reject invented strings such as "dhwijekwh". We deliberately only use
    # this check for an unknown one-word response, so normal sentences, names,
    # locations and career terms are not unnecessarily blocked.
    words = re.findall(r"[a-z]+", cleaned)
    known_single_words = {
        "acting", "actor", "artist", "athlete", "books", "business", "coding",
        "cooking", "cricket", "crochet", "dance", "dancer", "design", "drawing",
        "engineering", "football", "gaming", "medicine", "music", "painting",
        "photography", "reading", "science", "singing", "sports", "writing",
        "yes", "no", "maybe", "india", "japan", "usa", "canada", "australia",
        "germany", "france", "uk", "uae", "bengaluru", "bangalore", "mumbai",
        "delhi", "chennai", "hyderabad", "pune", "karnataka",
    }
    if len(words) == 1 and words[0] not in known_single_words:
        # A sequence of three or more consonants in an otherwise unknown lone
        # word is a strong keyboard-mash signal. Known valid terms above stay
        # accepted even where English spelling naturally has such a cluster.
        if re.search(r"[bcdfghjklmnpqrstvwxyz]{3,}", words[0]):
            return False
    return True


def intake_answer_error(index: int, answer: str, prompt: str = "") -> str:
    """Return a student-friendly validation message, or an empty string."""
    cleaned = answer.strip().lower()
    not_applicable_answers = {
        "na", "n/a", "n.a.", "not applicable", "not available",
        "not sure", "not yet", "prefer not to say", "none",
    }
    is_not_applicable = cleaned in not_applicable_answers
    prompt_lower = prompt.lower()
    # Name, age and current grade/year are needed to build a student profile,
    # so N/A is not sufficient for this one required opening question.
    if index == 0:
        words = re.findall(r"[A-Za-z]{2,}", answer)
        if is_not_applicable or not re.search(r"\d{1,2}", answer) or len(words) < 2:
            return "Please include your name, age, and grade/year, for example: “Aanya, 16, Grade 11”."
    if not is_meaningful_answer(answer):
        return "Please replace the random text with a meaningful answer. Examples accepted: yes/no, N/A, US or UK, 85, crochet, or a full sentence."
    # Marks, percentages, GPA, scores, hours and budgets need a number (or a
    # legitimate N/A). Letter grades such as A or B+ are also valid for the
    # individual-subject marks question.
    # The hobbies prompt contains the phrase “hours per week”, but it is
    # primarily a free-text question. Students may reasonably answer “I do
    # not track my time” or list hobbies without exact hour counts, so do not
    # reject those answers merely because the prompt mentions hours.
    hobby_prompt = "current hobbies" in prompt_lower or "hobbies and activities" in prompt_lower
    numeric_prompt = any(term in prompt_lower for term in (
        "percentage", "gpa", "cgpa", "scores or targets", "hours per week",
        "annual budget", "maximum amount",
    )) and not hobby_prompt
    marks_prompt = "marks or grades" in prompt_lower
    has_number = bool(re.search(r"\d+(?:\.\d+)?\s*%?", answer))
    has_letter_grade = bool(re.search(r"\b[A-F](?:[+-])?\b", answer))
    if numeric_prompt and not is_not_applicable and not has_number:
        return "Please enter a number, percentage, GPA/CGPA, or N/A if this does not apply."
    if marks_prompt and not is_not_applicable and not (has_number or has_letter_grade):
        return "Please include numeric marks, percentages, letter grades, or N/A if this does not apply."
    # For rating questions, a real score is needed before a recommendation can
    # use the answer. The student may add an explanation after the number.
    if ("scale of 1–5" in prompt_lower or "rate your confidence (1–5)" in prompt_lower) and not is_not_applicable and not re.search(r"(?<!\d)[1-5](?!\d)", answer):
        return "Please include a rating from 1 to 5, then add a short explanation if you wish."
    return ""


def render_theme_toggle(show_logout: bool = False) -> None:
    """Place page controls together at the top-right of full-screen pages."""
    if show_logout:
        _, theme_col, logout_col = st.columns([4, 1, 1])
    else:
        _, theme_col = st.columns([5, 1])
    with theme_col:
        label = "🌙 Dark mode" if st.session_state.light_mode else "☀️ Light mode"
        if st.button(label, key="theme_mode_button", use_container_width=True):
            # ``nav_page`` is a Streamlit widget value. Keep a separate copy
            # before rerunning so a theme refresh returns to the page the
            # student was viewing rather than the default Dashboard.
            st.session_state.theme_return_page = st.session_state.get("nav_page", "Dashboard")
            st.session_state.light_mode = not st.session_state.light_mode
            st.rerun()
    if show_logout:
        with logout_col:
            if st.button("Log out", key="top_right_log_out", use_container_width=True):
                save_current_student_state()
                log_out()
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
        # Forms make the Return/Enter key submit the login or sign-up action.
        with st.form("login_form", clear_on_submit=False, enter_to_submit=True):
            email = st.text_input("Email address", placeholder="you@example.com", key="email_input")
            display_name = ""
            if creating_account:
                display_name = st.text_input("What should we call you?", placeholder="Enter your name", key="name_input")
            password = st.text_input("Password", placeholder="Enter your password", type="password", key="password_input")
            if creating_account:
                st.caption("Create your own password.")
            remember_me = st.checkbox("Remember me", key="remember_me_input")
            submit_label = "Create account  →" if creating_account else "Log in  →"
            submitted = st.form_submit_button(submit_label, use_container_width=True)
        if submitted:
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
                with st.spinner("Setting up your account…"):
                    if creating_account:
                        account, error = create_user(
                            display_name.strip(),
                            clean_email,
                            password,
                        )
                    else:
                        account, error = authenticate_user(
                            clean_email,
                            password,
                        )

                if error:
                    st.error(error)

                if account:
                    restore_student_state(account)
                    # New students choose a quiz. Returning students continue
                    # from the exact page saved before they logged out/closed.
                    st.session_state.app_stage = "welcome" if creating_account else resume_stage()
                    if remember_me:
                        try:
                            st.query_params["session"] = make_session_token(account["student_id"])
                        except Exception:
                            pass
                    else:
                        try:
                            st.query_params.pop("session", None)
                        except Exception:
                            pass
                    save_current_student_state()
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
    render_theme_toggle(show_logout=True)
    st.markdown(f"<div class='top-title'>Hello, {escape(profile_name())}! 👋</div><div class='top-subtitle'>Let’s start by learning what matters to you.</div>", unsafe_allow_html=True)
    st.markdown(f"<div class='panel' style='text-align:center;max-width:900px;margin:0 auto 23px'><div class='butterfly-mark' style='font-size:2.3rem'>🦋</div><h2>“{random.choice(QUOTES)}”</h2><p class='muted'>Choose a quiz length. You can pause and return during this browser session.</p></div>", unsafe_allow_html=True)
    short, long = st.columns(2, gap="large")
    with short:
        st.markdown("<div class='choice-card'><div class='choice-icon'>⚡</div><h2>Quick Career Quiz</h2><p class='muted'>11 thoughtful questions — one from each important area. Great for a fast first recommendation.</p><p class='accent'>About 8–10 minutes</p></div>", unsafe_allow_html=True)
        st.button("Start quick quiz  →", use_container_width=True, on_click=reset_quiz, args=("short",))
    with long:
        st.markdown("<div class='choice-card'><div class='choice-icon'>🧭</div><h2>Complete Career Quiz</h2><p class='muted'>The full question bank covering academics, interests, skills, preferences, finances, and support needs.</p><p class='accent'>About 30–40 minutes</p></div>", unsafe_allow_html=True)
        st.button("Start complete quiz  →", use_container_width=True, on_click=reset_quiz, args=("long",))
    st.markdown("<p class='muted' style='text-align:center;margin-top:22px'>Not ready to answer yet? You can view your empty dashboard first.</p>", unsafe_allow_html=True)
    st.button(
        "Open dashboard without quiz  →",
        use_container_width=True,
        on_click=open_dashboard_without_quiz,
        key="welcome_open_empty_dashboard",
    )


def render_intake() -> None:
    render_theme_toggle(show_logout=True)
    # A browser can refresh while a reset callback is in progress, or an older
    # saved profile may have an incomplete quiz state. Never index the question
    # list with an empty value; take the student back to the quiz-length page.
    mode = st.session_state.get("intake_mode")
    index = st.session_state.get("intake_index")
    if mode not in {"short", "long"} or not isinstance(index, int):
        st.session_state.intake_mode = None
        st.session_state.intake_index = 0
        st.session_state.app_stage = "welcome"
        save_current_student_state()
        st.rerun()
    questions = intake_questions()
    if not 0 <= index < len(questions):
        st.session_state.intake_index = 0
        st.session_state.app_stage = "welcome"
        save_current_student_state()
        st.rerun()
    section, prompt = questions[index]
    percent = round((index + 1) * 100 / len(questions))
    st.markdown(f"<div class='top-title'>Career Discovery Quiz</div><div class='top-subtitle'>{'Quick' if st.session_state.intake_mode == 'short' else 'Complete'} version · Answer honestly — there are no right answers.</div><div class='quiz-step'>{section}</div><div class='progress-shell'><div class='progress-fill' style='width:{percent}%'></div></div>", unsafe_allow_html=True)
    key = f"intake_{index}"
    st.markdown(f"<div class='question-card'><div class='question-number'>QUESTION {index + 1} OF {len(questions)}</div><div class='question-text'>{escape(prompt)}</div>", unsafe_allow_html=True)
    # A form batches typing and clicking into one submission. This removes the
    # old "Press ⌘+Enter to apply" delay before the Next button responds.
    with st.form(f"intake_form_{index}", clear_on_submit=False, enter_to_submit=True):
        quiz_name = st.session_state.student_name
        quiz_email = st.session_state.student_email
        if index == 0:
            quiz_name = st.text_input("What should we call you?", value=st.session_state.student_name, placeholder="Enter your name", key="quiz_display_name")
            quiz_email = st.text_input("Email address", value=st.session_state.student_email, placeholder="you@example.com", key="quiz_email")
        # Single-line input is intentional: pressing Enter submits the form
        # and advances to the next question. Students can still type a full
        # sentence or paragraph in this field.
        answer = st.text_input("Your answer", value=st.session_state.intake_answers.get(key, ""), placeholder="Write your answer here, then press Enter…", key=f"widget_{key}")
        # Keep exactly one submit button inside the form. Streamlit sends the
        # Enter key to the first form submit control; placing Previous inside
        # the form could therefore move backwards unexpectedly.
        next_label = "Finish quiz  →" if index == len(questions) - 1 else "Next question  →"
        go_next = st.form_submit_button(next_label, type="primary", use_container_width=True)
    st.markdown("</div>", unsafe_allow_html=True)

    previous, quit_col = st.columns([1, 1])
    with previous:
        go_previous = index > 0 and st.button("← Previous", use_container_width=True, key=f"intake_previous_{index}")
    with quit_col:
        quit_clicked = st.button("Quit quiz", use_container_width=True, key=f"intake_quit_{index}")

    if go_previous:
        st.session_state.intake_answers[key] = str(st.session_state.get(f"widget_{key}", answer)).strip()
        st.session_state.intake_index -= 1
        save_current_student_state()
        st.rerun()
    if quit_clicked:
        st.session_state.intake_answers[key] = str(st.session_state.get(f"widget_{key}", answer)).strip()
        quit_current_quiz()
        st.rerun()
    if go_next:
        validation_error = intake_answer_error(index, answer, prompt)
        if validation_error:
            st.error(f"Invalid answer — {validation_error}")
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
        save_current_student_state()
        st.rerun()


def render_intake_results() -> None:
    render_theme_toggle()
    answered = sum(bool(value.strip()) for value in st.session_state.intake_answers.values())
    total = len(intake_questions())
    first_matches = relevant_career_results()[:3]
    first_careers = ", ".join(match_title(match) for match in first_matches)
    st.markdown("<div class='top-title'>Your Career Profile is Ready</div><div class='top-subtitle'>Your recommendations below are already based on the answers you wrote. The RIASEC quiz is optional and only refines them further.</div>", unsafe_allow_html=True)
    stat1, stat2, stat3 = st.columns(3)
    for col, icon, number, label in ((stat1, "🦋", f"{answered}/{total}", "Questions answered"), (stat2, "🧭", "Career profile", "Saved in this session"), (stat3, "🧠", "Next: personality", "Refine your matches")):
        with col: st.markdown(f"<div class='panel' style='text-align:center'><div class='icon-bubble' style='margin:auto'>{icon}</div><div class='result-number'>{number}</div><p class='muted'>{label}</p></div>", unsafe_allow_html=True)
    st.markdown(f"<div class='panel' style='margin-top:18px'><h3>Your first personalised career matches</h3><p class='mint'>{escape(first_careers)}</p><p class='muted'>Chosen from the interests you entered in the career quiz.</p></div>", unsafe_allow_html=True)
    st.markdown("<h2 style='margin-top:28px'>Refine your results with a RIASEC personality quiz</h2><p class='muted'>Choose one version. Both provide a Holland Code and career-family suggestions.</p>", unsafe_allow_html=True)
    short, long = st.columns(2, gap="large")
    with short:
        st.markdown("<div class='choice-card'><div class='choice-icon'>⚡</div><h2>Quick RIASEC Quiz</h2><p class='muted'>12 short statements — two for each career-interest theme. Get a fast career-direction summary.</p><p class='accent'>About 3–5 minutes</p></div>", unsafe_allow_html=True)
        st.button("Start quick RIASEC quiz  →", use_container_width=True, on_click=start_personality, args=("riasec_short",))
    with long:
        st.markdown("<div class='choice-card'><div class='choice-icon'>🧠</div><h2>Full RIASEC Quiz</h2><p class='muted'>60 statements measuring Realistic, Investigative, Artistic, Social, Enterprising, and Conventional themes.</p><p class='accent'>About 15–20 minutes</p></div>", unsafe_allow_html=True)
        st.button("Start full personality quiz  →", use_container_width=True, on_click=start_personality, args=("riasec_long",))
    if st.button("Open my personalised dashboard  →", use_container_width=True):
        st.session_state.app_stage = "dashboard"
        save_current_student_state()
        st.rerun()


def render_personality() -> None:
    render_theme_toggle(show_logout=True)
    questions = personality_questions()
    index = st.session_state.personality_index
    code, statement = questions[index]
    name, icon, _ = RIASEC[code]
    value_key = f"p_{index}"
    quiz_title = "Quick RIASEC Personality Quiz" if st.session_state.personality_mode == "riasec_short" else "Full RIASEC Personality Quiz"
    st.markdown(f"<div class='top-title'>{quiz_title}</div><div class='top-subtitle'>Rate each statement based on how you actually feel. 1 = strongly disagree · 5 = strongly agree.</div><div class='progress-shell'><div class='progress-fill' style='width:{round((index+1)*100/len(questions))}%'></div></div>", unsafe_allow_html=True)
    st.markdown(f"<div class='question-card'><div class='question-number'>{icon} {name.upper()} · QUESTION {index+1} OF {len(questions)}</div><div class='question-text'>{escape(statement)}</div>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)
    # A form gives the RIASEC controls the same Enter-to-continue behaviour as
    # the written quiz and the login screen.
    with st.form(f"personality_form_{index}", clear_on_submit=False, enter_to_submit=True):
        saved_value = st.session_state.personality_answers.get(value_key)
        value = st.radio("Your rating", (1, 2, 3, 4, 5), index=int(saved_value) - 1 if saved_value else None, horizontal=True, format_func=lambda number: {1:"1 · Strongly disagree",2:"2 · Disagree",3:"3 · Neutral",4:"4 · Agree",5:"5 · Strongly agree"}[number], key=f"radio_{value_key}")
        final = index == len(questions) - 1
        # Only Next/See results is a form submit control, so Enter cannot
        # accidentally activate Previous.
        go_next = st.form_submit_button("See results  →" if final else "Next question  →", type="primary", use_container_width=True)

    previous, quit_col = st.columns([1, 1])
    with previous:
        go_previous = index > 0 and st.button("← Previous", use_container_width=True, key=f"personality_previous_{index}")
    with quit_col:
        quit_clicked = st.button("Quit quiz", use_container_width=True, key=f"personality_quit_{index}")

    if go_previous:
        if value is not None:
            st.session_state.personality_answers[value_key] = value
        st.session_state.personality_index -= 1
        save_current_student_state()
        st.rerun()
    if quit_clicked:
        if value is not None:
            st.session_state.personality_answers[value_key] = value
        quit_current_quiz()
        st.rerun()
    if go_next:
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
        save_current_student_state()
        st.rerun()


def render_personality_results() -> None:
    render_theme_toggle()
    scores = riasec_scores()
    ranked = sorted(scores, key=scores.get, reverse=True)
    code = "".join(ranked[:2])
    scored_matches = displayed_career_matches()
    suggestions = tuple(match_title(match) for match in scored_matches[:4]) or career_suggestions()[:4]
    max_score = 10 if st.session_state.personality_mode == "riasec_short" else 50
    summary_title = "Your Quick RIASEC Career Profile" if st.session_state.personality_mode == "riasec_short" else "Your RIASEC Career Profile"
    st.markdown(f"<div class='top-title'>{summary_title}</div><div class='top-subtitle'>Your strongest themes point to work environments and career families that may feel naturally engaging.</div>", unsafe_allow_html=True)
    saved_profile = st.session_state.backend_profile or {}
    if not saved_profile.get("student_id") and st.session_state.backend_error and not backend_unavailable(st.session_state.backend_error):
        st.warning(f"Your on-screen summary is ready, but it was not saved to the backend. {st.session_state.backend_error}")
    if st.session_state.score_error and not backend_unavailable(st.session_state.score_error):
        st.warning(f"Your local results are shown below. {st.session_state.score_error}")
    st.markdown(f"<div class='panel' style='text-align:center;max-width:780px;margin:0 auto 22px'><div class='result-code'>{code}</div><h2>{RIASEC[ranked[0]][1]} {RIASEC[ranked[0]][0]} + {RIASEC[ranked[1]][1]} {RIASEC[ranked[1]][0]}</h2><p class='muted'>Your Holland Code is a starting point for exploration, not a final decision.</p></div>", unsafe_allow_html=True)
    st.markdown("<h2 style='margin-top:28px'>Your full RIASEC score breakdown</h2>", unsafe_allow_html=True)
    # RIASEC has six dimensions. Show every one, not only the strongest three.
    for start in range(0, len(ranked), 3):
        score_cols = st.columns(3)
        for col, type_code in zip(score_cols, ranked[start:start + 3]):
            with col:
                name, icon, _ = RIASEC[type_code]
                st.markdown(f"<div class='panel' style='text-align:center'><div class='icon-bubble' style='margin:auto'>{icon}</div><h3>{name}</h3><div class='result-number'>{scores[type_code]}/{max_score}</div></div>", unsafe_allow_html=True)
    st.markdown("<h2 style='margin-top:28px'>Career families to explore</h2>", unsafe_allow_html=True)
    if scored_matches:
        cards = "".join(
            f"<div class='match-card'><span class='match-pill'>{escape(match_score(match))}</span><div class='icon-bubble butterfly-mark'>🦋</div><h3>{escape(match_title(match))}</h3><p class='muted'>{escape(str(match.get('reason') or match.get('description') or 'A strong match based on your profile.'))}</p></div>"
            for match in scored_matches[:4]
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
        save_current_student_state()
        st.rerun()


def start_career_game() -> None:
    """Create a fresh ten-question round with balanced answer positions."""
    question_count = min(10, len(CAREER_GAME_QUESTIONS))
    previous_order = st.session_state.get("career_game_order", [])
    previous_questions = {
        item for item in previous_order
        if isinstance(item, int) and 0 <= item < len(CAREER_GAME_QUESTIONS)
    } if isinstance(previous_order, list) else set()
    unused_questions = [
        question_index for question_index in range(len(CAREER_GAME_QUESTIONS))
        if question_index not in previous_questions
    ]
    # With 20 questions and 10 per round, replay can use the exact unused
    # half of the bank, guaranteeing no repeat from the immediately prior round.
    candidate_pool = unused_questions if len(unused_questions) >= question_count else list(range(len(CAREER_GAME_QUESTIONS)))
    order = random.sample(candidate_pool, question_count)
    # Spread correct answers across A/B/C/D, then shuffle that position plan.
    # This prevents a round from accidentally placing every answer first.
    answer_slots = [position % 4 for position in range(question_count)]
    random.shuffle(answer_slots)
    option_orders = {}
    for round_position, question_index in enumerate(order):
        question = CAREER_GAME_QUESTIONS[question_index]
        distractors = [option for option in question["options"] if option != question["answer"]]
        random.shuffle(distractors)
        shuffled_options = distractors
        shuffled_options.insert(answer_slots[round_position], question["answer"])
        option_orders[str(question_index)] = tuple(shuffled_options)
    st.session_state.career_game_order = order
    st.session_state.career_game_option_orders = option_orders
    st.session_state.career_game_index = 0
    st.session_state.career_game_score = 0
    st.session_state.career_game_answered = False
    st.session_state.career_game_feedback = {}
    st.session_state.career_game_complete = False
    st.session_state.career_game_celebrated = False
    st.session_state.career_game_round = int(st.session_state.get("career_game_round", 0)) + 1


def render_career_game() -> None:
    """Render a small, replayable career-clue guessing game."""
    order = st.session_state.get("career_game_order")
    option_orders = st.session_state.get("career_game_option_orders")
    if (
        not isinstance(order, list)
        or not order
        or any(not isinstance(item, int) or item >= len(CAREER_GAME_QUESTIONS) for item in order)
        or not isinstance(option_orders, dict)
        or any(str(item) not in option_orders for item in order)
    ):
        start_career_game()
        order = st.session_state.career_game_order
        option_orders = st.session_state.career_game_option_orders

    st.markdown(
        "<div class='top-title'>🎮 Career Quest</div>"
        "<div class='top-subtitle'>Guess the career from each clue and discover what different professionals actually do.</div>",
        unsafe_allow_html=True,
    )

    if st.session_state.get("career_game_complete", False):
        score = int(st.session_state.get("career_game_score", 0))
        total = len(order)
        if not st.session_state.get("career_game_celebrated", False):
            st.balloons()
            st.session_state.career_game_celebrated = True
        if score == total:
            result_title, result_note = "Career Expert!", "Perfect score—you matched every clue to its career."
        elif score >= max(1, total - 2):
            result_title, result_note = "Career Explorer!", "Great work—you already understand many different career roles."
        else:
            result_title, result_note = "Curious Starter!", "Every clue you explored added a new career to your mental map."
        st.markdown(
            f"<div class='panel' style='text-align:center;max-width:760px;margin:20px auto'>"
            f"<div class='result-code'>{score}/{total}</div><h2>{result_title}</h2>"
            f"<p class='muted'>{result_note}</p></div>",
            unsafe_allow_html=True,
        )
        replay_col, dashboard_col = st.columns(2)
        with replay_col:
            if st.button("↻ Play another round", use_container_width=True, key="career_game_replay"):
                start_career_game()
                st.rerun()
        with dashboard_col:
            st.button(
                "Open dashboard →",
                use_container_width=True,
                key="career_game_dashboard",
                on_click=lambda: st.session_state.update(nav_page="Dashboard"),
            )
        return

    index = min(int(st.session_state.get("career_game_index", 0)), len(order) - 1)
    question = CAREER_GAME_QUESTIONS[order[index]]
    answered = bool(st.session_state.get("career_game_answered", False))
    progress = (index + 1) / len(order)
    st.markdown(
        f"<div class='panel'><span class='match-pill'>Clue {index + 1} of {len(order)}</span>"
        f"<h2 style='margin-top:28px'>{escape(question['clue'])}</h2></div>",
        unsafe_allow_html=True,
    )
    st.progress(progress)
    choice = st.radio(
        "Choose your answer",
        option_orders[str(order[index])],
        index=None,
        key=f"career_game_choice_{st.session_state.career_game_round}_{index}",
        disabled=answered,
    )

    if not answered:
        if st.button("Lock my answer →", use_container_width=True, key=f"career_game_lock_{index}"):
            if choice is None:
                st.error("Choose one career before locking your answer.")
                return
            correct = choice == question["answer"]
            if correct:
                st.session_state.career_game_score += 1
            st.session_state.career_game_feedback = {"correct": correct, "choice": choice}
            st.session_state.career_game_answered = True
            st.rerun()
        return

    feedback = st.session_state.get("career_game_feedback", {})
    if feedback.get("correct"):
        st.success(f"Correct! {question['answer']} is the answer.")
    else:
        st.warning(f"Good try! You chose {feedback.get('choice', 'another option')}. The answer is {question['answer']}.")
    st.info(question["explanation"])

    final_question = index == len(order) - 1
    if st.button(
        "See my score →" if final_question else "Next clue →",
        use_container_width=True,
        key=f"career_game_next_{index}",
    ):
        if final_question:
            st.session_state.career_game_complete = True
        else:
            st.session_state.career_game_index = index + 1
            st.session_state.career_game_answered = False
            st.session_state.career_game_feedback = {}
        st.rerun()


def normalise_career_journal(raw: object) -> dict[str, object]:
    """Keep journal data compact, JSON-safe, and suitable for account storage."""
    if not isinstance(raw, dict):
        return {"version": 1, "currentPage": 0, "pages": []}

    allowed_fonts = {"DM Sans", "Caveat", "Lora", "Playfair Display", "Quicksand"}
    allowed_papers = {"cream", "blush", "lavender", "sage", "sky", "peach"}
    text_limits = {
        "date": 24,
        "title": 100,
        "goal": 500,
        "steps": 3000,
        "win": 800,
        "reflection": 2000,
        "nextStep": 1000,
        "mood": 40,
    }

    def bounded_number(value: object, minimum: float, maximum: float, fallback: float) -> float:
        try:
            number = float(value)
        except (TypeError, ValueError):
            return fallback
        return max(minimum, min(maximum, number))

    clean_pages: list[dict[str, object]] = []
    pages = raw.get("pages", [])
    if not isinstance(pages, list):
        pages = []
    for page_number, page in enumerate(pages[:366]):
        if not isinstance(page, dict):
            continue
        clean_page: dict[str, object] = {
            "id": str(page.get("id") or f"page-{page_number + 1}")[:80],
            "font": str(page.get("font", "DM Sans")) if str(page.get("font", "DM Sans")) in allowed_fonts else "DM Sans",
            "color": str(page.get("color", "#49365f"))[:20],
            "paper": str(page.get("paper", "cream")) if str(page.get("paper", "cream")) in allowed_papers else "cream",
        }
        for field, limit in text_limits.items():
            clean_page[field] = str(page.get(field, ""))[:limit]

        clean_decorations: list[dict[str, object]] = []
        decorations = page.get("decorations", [])
        if isinstance(decorations, list):
            for decoration_number, decoration in enumerate(decorations[:80]):
                if not isinstance(decoration, dict):
                    continue
                decoration_type = str(decoration.get("type", "sticker"))
                if decoration_type not in {"sticker", "washi"}:
                    continue
                clean_decorations.append({
                    "id": str(decoration.get("id") or f"decor-{decoration_number + 1}")[:80],
                    "type": decoration_type,
                    "sticker": int(bounded_number(decoration.get("sticker", 0), 0, 19, 0)),
                    "tapeStyle": int(bounded_number(decoration.get("tapeStyle", 0), 0, 7, 0)),
                    "x": bounded_number(decoration.get("x", 50), 0, 100, 50),
                    "y": bounded_number(decoration.get("y", 50), 0, 100, 50),
                    "size": bounded_number(decoration.get("size", 90), 30, 240, 90),
                    "rotation": bounded_number(decoration.get("rotation", 0), -180, 180, 0),
                })
        clean_page["decorations"] = clean_decorations
        clean_pages.append(clean_page)

    current_page = int(bounded_number(raw.get("currentPage", 0), 0, max(0, len(clean_pages) - 1), 0))
    return {"version": 1, "currentPage": current_page, "pages": clean_pages}


def render_career_journal() -> None:
    """Render the draggable, account-saved career progress journal."""
    st.markdown(
        "<div class='top-title'>Career Journal</div>"
        "<div class='top-subtitle'>Turn small daily steps into a career story that feels like yours.</div>",
        unsafe_allow_html=True,
    )
    st.caption("📔 Drag stickers and washi tape, personalise your writing, then choose Save journal to keep it with your account.")
    journal = normalise_career_journal(st.session_state.get("career_journal", {}))
    st.session_state.career_journal = journal
    result = career_journal_component(
        journal=journal,
        light_mode=bool(st.session_state.light_mode),
        student_name=str(st.session_state.get("student_name", "Student")),
        key=f"career_journal_{st.session_state.get('student_email', 'guest')}",
        default=None,
    )
    if not isinstance(result, dict) or result.get("action") != "save":
        return
    save_token = str(result.get("token", ""))
    if not save_token or save_token == st.session_state.get("journal_last_save_token", ""):
        return
    st.session_state.journal_last_save_token = save_token
    st.session_state.career_journal = normalise_career_journal(result.get("journal", {}))
    save_current_student_state()
    st.toast("Journal saved to your Career AI account 📔")


def render_sidebar() -> str:
    with st.sidebar:
        logo_col, name_col = st.columns([.3, .7], gap="small")
        with logo_col: st.image(LOGO_PATH, width=62)
        with name_col: st.markdown("<div style='padding-top:3px'><div class='brand-name'>Career <span>AI</span></div><div class='sidebar-tagline'>Your AI Career Mentor</div></div>", unsafe_allow_html=True)
        st.markdown("---")
        pages = (*PAGES, "Admin") if is_admin() else PAGES
        page = st.radio("Navigation", pages, format_func=lambda p: f"{PAGE_ICONS[p]}  {p}", key="nav_page", label_visibility="collapsed")
        st.markdown("---")
        if st.button("Log out", use_container_width=True):
            log_out()
            st.rerun()
    return page


def render_admin() -> None:
    """Private local-demo account management. Deletion cannot be undone."""
    st.markdown("<div class='top-title'>Admin · User accounts</div><div class='top-subtitle'>Manage registered accounts and their saved profile data.</div>", unsafe_allow_html=True)
    st.warning("Deleting an account permanently removes its login and all saved quiz, RIASEC, roadmap, and chat data.")
    users = list_users()
    if not users:
        st.info("No user accounts have been created yet.")
        return
    st.caption(f"{len(users)} registered account(s)")
    current_email = st.session_state.student_email.strip().lower()
    pending_delete = str(st.session_state.get("admin_delete_target", "")).strip().lower()
    for user in users:
        email = user["email"]
        left, action = st.columns([5, 1])
        with left:
            st.markdown(
                f"<div class='panel'><h3>{escape(user['name'])}</h3>"
                f"<p class='muted'>{escape(email)}<br>Created: {escape(user['created_at'])}</p></div>",
                unsafe_allow_html=True,
            )
        with action:
            st.markdown("<div style='height:18px'></div>", unsafe_allow_html=True)
            if email == current_email:
                st.button("Current admin", disabled=True, use_container_width=True, key=f"admin_current_{user['student_id']}")
            elif pending_delete == email:
                st.markdown("<p class='muted'><b>Delete this account?</b><br>This cannot be undone.</p>", unsafe_allow_html=True)
                yes_col, no_col = st.columns(2)
                with yes_col:
                    if st.button("Yes", use_container_width=True, key=f"admin_confirm_delete_{user['student_id']}"):
                        delete_user(email)
                        st.session_state.pop("admin_delete_target", None)
                        st.success(f"Deleted {email} and its saved data.")
                        st.rerun()
                with no_col:
                    if st.button("No", use_container_width=True, key=f"admin_cancel_delete_{user['student_id']}"):
                        st.session_state.pop("admin_delete_target", None)
                        st.rerun()
            elif st.button("Delete", use_container_width=True, key=f"admin_delete_{user['student_id']}"):
                st.session_state.admin_delete_target = email
                st.rerun()


def render_change_password() -> None:
    """Allow the signed-in student to change only their own password."""
    st.markdown("<div class='top-title'>Change Password</div><div class='top-subtitle'>Choose a new password for your Career AI account.</div>", unsafe_allow_html=True)
    with st.form("change_password_form"):
        current_password = st.text_input("Current password", type="password")
        new_password = st.text_input("New password", type="password", help="Use at least 8 characters.")
        confirm_password = st.text_input("Confirm new password", type="password")
        submitted = st.form_submit_button("Update password  →", use_container_width=True)

    if not submitted:
        return
    if not current_password or not new_password or not confirm_password:
        st.error("Please complete all three password fields.")
    elif len(new_password) < 8:
        st.error("Your new password must contain at least 8 characters.")
    elif new_password != confirm_password:
        st.error("The new password and confirmation do not match.")
    else:
        updated, error = update_user_password(st.session_state.student_email, current_password, new_password)
        if error:
            st.error(error)
        elif updated:
            st.success("Password updated successfully. You can use it the next time you log in.")


def render_dashboard() -> None:
    st.markdown(f"<div class='top-title'>Hello, {escape(profile_name())} 👋</div><div class='top-subtitle'>Here is your growing career profile.</div>", unsafe_allow_html=True)
    career_questions = intake_questions() if st.session_state.intake_mode in {"short", "long"} else tuple()
    career_quiz_finished = bool(career_questions) and all(
        bool(str(st.session_state.intake_answers.get(f"intake_{index}", "")).strip())
        for index in range(len(career_questions))
    )
    personality_questions_saved = personality_questions() if st.session_state.personality_mode in {"riasec_short", "riasec_long"} else tuple()
    riasec_finished = bool(personality_questions_saved) and all(
        st.session_state.personality_answers.get(f"p_{index}") in {1, 2, 3, 4, 5}
        for index in range(len(personality_questions_saved))
    )
    quiz_col, riasec_col, _ = st.columns([1.35, 1.35, 3])
    with quiz_col:
        if career_quiz_finished:
            st.button(
                "↻ Re-attempt career quiz",
                key="dashboard_reattempt_quiz",
                use_container_width=True,
                on_click=begin_quiz_reattempt,
            )
        else:
            st.button(
                "Take career quiz →",
                key="dashboard_take_quiz",
                use_container_width=True,
                on_click=open_career_quiz,
            )
    with riasec_col:
        if riasec_finished:
            st.button(
                "↻ Re-attempt RIASEC",
                key="dashboard_reattempt_riasec",
                use_container_width=True,
                on_click=begin_riasec_reattempt,
            )
        elif career_quiz_finished:
            st.button(
                "Take RIASEC quiz →",
                key="dashboard_take_riasec",
                use_container_width=True,
                on_click=open_riasec_quiz,
            )
        else:
            st.button(
                "Take RIASEC quiz →",
                key="dashboard_take_riasec_locked",
                use_container_width=True,
                disabled=True,
            )
    if not career_quiz_finished:
        st.caption("Take the Career Quiz to receive personalised recommendations. RIASEC becomes available after it.")
    elif not riasec_finished:
        st.caption("Take a Quick or Full RIASEC Quiz to refine your matches. Re-attempt becomes available after completion.")
    else:
        st.caption("Career quiz replaces your written interests. RIASEC re-attempt keeps those interests and lets you choose Quick or Full again.")
    live_careers, _ = load_careers_from_backend(careers_api_url())
    scored_matches = displayed_career_matches() if career_quiz_finished else tuple()
    # Before RIASEC scoring, prioritise the student's discovery answers over
    # the backend's generic catalogue order. Once scored, backend matches win.
    local_suggestions = career_suggestions()
    generic_backend_suggestions = tuple(career_title(career) for career in live_careers[:4])
    suggested = (
        tuple(match_title(match) for match in scored_matches[:4])
        or (local_suggestions if not st.session_state.personality_complete else generic_backend_suggestions)
        or generic_backend_suggestions
        or local_suggestions
    )
    score, matches, mentor = st.columns([1, 1.45, .7], gap="medium")
    suitability_score = dashboard_suitability_score()
    if not career_quiz_finished:
        score_message = "Complete the Career Quiz first"
        score_detail = "No suitability score is shown yet. Attempt the Career Quiz so every recommendation is based on your answers."
    elif not st.session_state.personality_complete:
        score_message = "Your strongest current career match"
        score_detail = "Calculated from your written quiz interests. Take the Quick or Full RIASEC quiz to refine the match further."
    else:
        score_message = "Your profile has a strong direction!"
        score_detail = "Based on your RIASEC profile and all of your career-quiz answers."
    score_value = f"{suitability_score}%" if career_quiz_finished else "—"
    with score: st.markdown(f"<div class='score-panel'><h3>Career Suitability Score</h3><div class='big-score'>{score_value}</div><b>{score_message}</b><p>{score_detail}</p></div>", unsafe_allow_html=True)
    with matches:
        header_left, header_right = st.columns([3, 1])
        with header_left:
            st.markdown("<h3 style='margin:0'>Top Career Matches</h3>", unsafe_allow_html=True)
        with header_right:
            st.button(
                "View all →",
                key="dashboard_view_all_careers",
                use_container_width=True,
                on_click=open_explore_careers,
            )
        if not career_quiz_finished:
            st.caption("Attempt the Career Quiz to replace these general suggestions with matches based on your answers.")
        match_cards = "".join(
            f"<div class='match-card'><span class='match-pill'>{escape(match_score(match))}</span><div class='icon-bubble butterfly-mark'>🦋</div><h3>{escape(match_title(match))}</h3><p class='muted'>{escape(str(match.get('reason') or 'A promising direction based on your profile.'))}</p></div>"
            for match in scored_matches[:4]
        ) if scored_matches else "<div class='panel'><h3>Complete your Career Quiz</h3><p class='muted'>Your personalised career matches will appear here after you answer the quiz questions.</p></div>"
        st.markdown("<div class='panel'><div class='match-grid'>" + match_cards + "</div></div>", unsafe_allow_html=True)
    with mentor:
        with st.container(border=True, key="ai_mentor_card"):
            st.markdown("### AI Mentor")
            _, logo, _ = st.columns([1, 1.4, 1])
            with logo: st.image(LOGO_PATH, use_container_width=True)
            st.markdown("**Ask your AI Mentor**")
            st.caption("Career and education guidance whenever you need it.")
            st.button("Start a conversation", use_container_width=True, on_click=open_ai_mentor)

    # RIASEC is optional: written quiz answers already produce recommendations.
    # Keep both versions available here so students can refine them later.
    if not st.session_state.personality_complete:
        with st.container(border=True):
            st.markdown("### Refine your career matches with RIASEC")
            st.caption("Your current recommendations use your written quiz answers. Take this optional interest test whenever you are ready for an extra layer of detail.")
            quick_col, full_col, note_col = st.columns([1, 1, 1.35], gap="medium")
            with quick_col:
                st.button(
                    "Quick RIASEC quiz →",
                    key="dashboard_riasec_short",
                    use_container_width=True,
                    on_click=start_personality,
                    args=("riasec_short",),
                )
            with full_col:
                st.button(
                    "Full RIASEC quiz →",
                    key="dashboard_riasec_long",
                    use_container_width=True,
                    on_click=start_personality,
                    args=("riasec_long",),
                )
            with note_col:
                st.markdown("<p class='muted'><b>Quick:</b> a fast check-in.<br><b>Full:</b> a more detailed interest profile.</p>", unsafe_allow_html=True)
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
    using_gemini = bool(gemini_api_key() and OpenAI is not None)
    using_gpt = bool(openai_api_key() and OpenAI is not None)
    if using_gemini:
        st.caption(f"Gemini is ready to personalise career guidance using {gemini_model()}.")
    elif using_gpt:
        st.caption("GPT is ready to personalise career guidance from your quiz profile.")
    else:
        st.caption(f"Ollama model active: {ollama_model()}. If Ollama cannot answer, Career AI uses built-in guidance.")

    def ask_selected_model(new_question: str) -> tuple[str, str]:
        # Use exactly one configured model. This avoids a slow chain of failed
        # requests and prevents a depleted OpenAI account overriding Gemini.
        if using_gemini:
            return gemini_mentor_reply(new_question)
        if using_gpt:
            return gpt_mentor_reply(new_question)
        return ollama_mentor_reply(new_question)

    if st.button("Clear conversation", key="mentor_clear_history"):
        st.session_state.mentor_history = []
        save_current_student_state()
        st.rerun()
    with st.form("mentor_form", clear_on_submit=True):
        question = st.text_input("Ask your question", placeholder="Which skills should I build for UX design?")
        asked = st.form_submit_button("Ask AI Mentor  →", use_container_width=True)
    if asked:
        source_note = ""
        model_error = ""
        if not question.strip():
            st.error("Please type a career or education question before submitting.")
        elif is_friendly_mentor_message(question):
            reply = friendly_mentor_reply(question)
        elif not is_career_mentor_question(question):
            # General questions can use the configured AI model too.
            reply, model_error = ask_selected_model(question.strip())
            if not reply:
                reply = built_in_general_reply(question.strip())
                reason = f" ({model_error})" if model_error else ""
                source_note = f"This reply is using Career AI’s local guidance because the selected AI model did not respond{reason}."
        else:
            reply, model_error = ask_selected_model(question.strip())
            if not reply:
                reply = built_in_mentor_reply(question.strip())
                reason = f" ({model_error})" if model_error else ""
                source_note = f"This reply is using Career AI’s local guidance because the selected AI model did not respond{reason}."
        if question.strip():
            is_greeting = is_friendly_mentor_message(question)
            if not is_greeting and mentor_reply_is_repeated(reply):
                reply = non_repeating_career_reply(question.strip())
                if mentor_reply_is_repeated(reply):
                    reply += " This is a fresh follow-up plan rather than a repeat of your earlier answer."
            # Compare the original AI reply before adding the detailed local
            # plan. Otherwise the shared plan itself makes different answers
            # look identical and causes an unnecessary replacement.
            st.session_state.mentor_history.append({"role": "student", "message": question.strip()})
            st.session_state.mentor_history.append({"role": "ai", "message": reply})
            st.session_state.mentor_last_source_note = source_note
            save_current_student_state()
            st.rerun()
    # Keep each question/reply together, but show the most recent exchange
    # first so students do not need to scroll down for the latest guidance.
    history = st.session_state.mentor_history
    if st.session_state.get("mentor_last_source_note"):
        st.caption(st.session_state.mentor_last_source_note)
    exchanges = [history[position:position + 2] for position in range(0, len(history), 2)]
    for exchange in reversed(exchanges):
        for message in exchange:
            role = "You" if chat_message_role(message) == "student" else "Career AI"
            # The mentor may return Markdown emphasis and headings. The chat
            # cards are plain-text cards, so remove Markdown markers instead
            # of showing symbols such as ** and ### to the student.
            readable_text = chat_message_text(message)
            readable_text = re.sub(r"(?m)^\s*#{1,6}\s*", "", readable_text)
            readable_text = readable_text.replace("**", "").replace("__", "")
            readable_text = re.sub(r"(?m)^\s*[*-]\s+", "", readable_text)
            message_text = escape(readable_text).replace("\n", "<br>")
            st.markdown(
                f"<div class='panel'><b>{role}:</b> {message_text}</div>",
                unsafe_allow_html=True,
            )


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

    # Students naturally search by an interest ("crochet", "cricket",
    # "plants") while the catalogue stores professional job titles ("Textile
    # Designer", "Sports Coach", "Horticulturist"). Expand those interest
    # words into the relevant careers before filtering.
    related_terms: list[str] = [query] if query else []
    for keyword, careers_for_interest in DIRECT_CAREER_KEYWORDS.items():
        terms = (keyword, *DIRECT_CAREER_ALIASES.get(keyword, ()))
        if query and any(re.search(rf"(?<!\w){re.escape(term)}(?!\w)", query) for term in terms):
            related_terms.extend(career.lower() for career in careers_for_interest)
    related_terms.extend({
        "crochet": ("textile", "weaver", "fashion", "craft", "garment", "pattern"),
        "cricket": ("sports", "athlete", "coach", "fitness", "physio", "journalist"),
        "plants": ("botan", "horticultur", "agricultur", "garden", "farm", "environment"),
        "cooking": ("chef", "cook", "food", "restaurant", "baker", "hospitality"),
        "acting": ("actor", "theatre", "film", "perform", "voice", "media"),
    }.get(query, ()))
    related_terms = list(dict.fromkeys(term for term in related_terms if term))
    def related_job_match(job: str) -> bool:
        title = job.lower()
        for term in related_terms:
            # Only scientific stems need a partial-word match (botanist,
            # horticulturist, physiotherapist). All other terms use word
            # boundaries, preventing accidental matches such as craft →
            # aircraft or sport → transport.
            if term in {"botan", "horticultur", "agricultur", "physio"}:
                if term in title:
                    return True
            elif re.search(rf"(?<!\w){re.escape(term)}(?!\w)", title):
                return True
        return False

    filtered = [(job, group) for job, group in all_jobs_with_category if not query or related_job_match(job)]
    if query and len(related_terms) > 1:
        st.caption("Related career search: " + " · ".join(title.title() for title in related_terms[1:7]))
    st.caption(f"{len(filtered)} career paths found")
    if not filtered:
        st.info("No careers match that search. Try a broader word or choose All categories.")
        return
    # Rendering all ~1,000 cards at once makes phones and slower laptops lag.
    # Give students access to every result, 30 at a time, with search narrowing
    # it further when they know the career they want to explore.
    page_size = 30
    total_pages = max(1, (len(filtered) + page_size - 1) // page_size)
    page_number = st.selectbox(
        "Career results page",
        tuple(range(1, total_pages + 1)),
        key=f"career_page_{category}_{query}",
        format_func=lambda number: f"Page {number} of {total_pages}",
    )
    page_start = (page_number - 1) * page_size
    visible_jobs = filtered[page_start:page_start + page_size]
    st.caption(f"Showing careers {page_start + 1}–{page_start + len(visible_jobs)} of {len(filtered)}")
    cards = []
    for job, group in visible_jobs:
        backend_job = backend_by_name.get(job, {})
        description = career_description(backend_job) if backend_job else f"{group} · Explore required skills, courses, and opportunities."
        cards.append(
            f"<div class='match-card'><span class='match-pill'>{escape(group)}</span><div class='icon-bubble butterfly-mark'>🦋</div>"
            f"<h3>{escape(job)}</h3><p class='muted'>{escape(description)}</p></div>"
        )
    st.markdown("<div class='match-grid'>" + "".join(cards) + "</div>", unsafe_allow_html=True)


def render_skill_roadmap() -> None:
    st.markdown("<div class='top-title'>Your Learning Roadmap</div><div class='top-subtitle'>Your quiz progress updates this roadmap automatically.</div>", unsafe_allow_html=True)
    steps = list(automatic_roadmap_steps())
    # Quiz/profile milestones are automatic. These final actions need real
    # student work, so they keep a saved manual completion control.
    manual_step_ids = {8, 9, 10}
    for step in steps:
        step_id = roadmap_step_id(step)
        if step_id in manual_step_ids:
            step["completed"] = step_id in st.session_state.local_roadmap_completed
    completed_count = sum(bool(step.get("completed", False)) for step in steps)
    progress = round(completed_count * 100 / len(steps))
    st.markdown(f"<div class='panel'><h3>{progress}% complete</h3><div class='progress-shell'><div class='progress-fill' style='width:{progress}%'></div></div><p class='muted'>{completed_count} of {len(steps)} steps completed. Quiz milestones update automatically; real-world actions can be marked when you finish them.</p></div>", unsafe_allow_html=True)
    for position, step in enumerate(steps, 1):
        step_id = roadmap_step_id(step)
        title = roadmap_step_title(step, position)
        description = str(step.get("description") or step.get("details") or "")
        completed = bool(step.get("completed", False))
        row, check = st.columns([5, 1])
        with row:
            state = "Completed automatically" if completed and step_id not in manual_step_ids else ("Completed" if completed else "Next step")
            st.markdown(f"<div class='panel'><h3>{position}. {escape(title)}</h3><p class='muted'>{escape(description) if description else state}</p></div>", unsafe_allow_html=True)
        with check:
            st.markdown("<div style='height:18px'></div>", unsafe_allow_html=True)
            if step_id in manual_step_ids:
                if st.button("↩ Undo" if completed else "✓ Done", key=f"roadmap_manual_{step_id}", use_container_width=True):
                    if completed:
                        st.session_state.local_roadmap_completed.discard(step_id)
                    else:
                        st.session_state.local_roadmap_completed.add(step_id)
                    save_current_student_state()
                    st.rerun()
            else:
                st.markdown(
                    "<div class='match-pill' style='text-align:center'>✓ Auto</div>" if completed
                    else "<div class='match-pill' style='text-align:center'>Quiz needed</div>",
                    unsafe_allow_html=True,
                )


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
            st.info("No matching institution was found in the available directory. Try a university name, a broader study field, or another country.")
            return
        source_name = str(global_results[0].get("source") or "worldwide directory")
        st.caption(f"{len(global_results)} institutions found · Source: {source_name}. Use each university’s official website to verify courses, fees, accreditation, admissions, and scholarships.")
        for row_start in range(0, len(global_results), 3):
            row = global_results[row_start:row_start + 3]
            columns = st.columns(3)
            for column, item in zip(columns, row):
                with column:
                    detail = str(item.get("description") or item.get("city") or "See the official university website for courses, admissions and scholarships.")
                    st.markdown(
                        f"<div class='match-card'><span class='match-pill'>{escape(item['country'])}</span><div class='icon-bubble'>🎓</div>"
                        f"<h3>{escape(item['name'])}</h3><p class='muted'>{escape(detail)}</p></div>",
                        unsafe_allow_html=True,
                    )
                    st.link_button(
                        "Open university website ↗",
                        item["website"] or university_website(item["name"]),
                        use_container_width=True,
                        key=f"world_university_link_{row_start}_{item['name']}",
                    )
        return
    recommended = university_recommendations()
    with st.container(border=True):
        st.markdown("### 🦋 Recommended for you")
        st.caption(university_recommendation_reason())
        recommendation_columns = st.columns(3)
        for column, university in zip(recommendation_columns, recommended):
            with column:
                st.markdown(f"<div class='match-card'><span class='match-pill'>For you</span><div class='icon-bubble'>🎓</div><h3>{escape(university['name'])}</h3><p class='muted'><b>{escape(university['field'])}</b><br>{escape(university['country'])}<br><span class='mint'>{escape(university['scholarships'])}</span></p></div>", unsafe_allow_html=True)
                st.link_button("Open university website ↗", university_website(university["name"]), use_container_width=True)
    st.markdown("<h2 style='margin-top:28px'>Browse all curated universities</h2>", unsafe_allow_html=True)
    fields = tuple(sorted({university["field"] for university in UNIVERSITY_CATALOG}))
    countries = tuple(sorted({university["country"] for university in UNIVERSITY_CATALOG}))
    search_col, field_col, country_col = st.columns([2, 1, 1])
    with search_col:
        query = st.text_input("Search universities", placeholder="Try MIT, IIT, design, medicine…").strip().lower()
    with field_col:
        field = st.selectbox("Study field", ("All fields", *fields))
    with country_col:
        selected_country = st.selectbox("Country", ("All countries", *countries), key="curated_university_country")
    filtered = [
        university for university in UNIVERSITY_CATALOG
        if (field == "All fields" or university["field"] == field)
        and (selected_country == "All countries" or university["country"] == selected_country)
        and (not query or query in " ".join(university.values()).lower())
    ]
    st.caption(f"{len(filtered)} university recommendations found · Rankings are snapshots—check current rankings before applying.")
    if not filtered:
        st.info("No universities match that search.")
        return
    for row_start in range(0, len(filtered), 3):
        row = filtered[row_start:row_start + 3]
        columns = st.columns(3)
        for column, university in zip(columns, row):
            with column:
                st.markdown(f"<div class='match-card'><span class='match-pill'>{escape(university['country'])}</span><div class='icon-bubble'>🎓</div><h3>{escape(university['name'])}</h3><p class='muted'><b>{escape(university['field'])}</b><br>{escape(university['reputation'])}<br><span class='mint'>{escape(university['scholarships'])}</span></p></div>", unsafe_allow_html=True)
                st.link_button("Open university website ↗", university_website(university["name"]), use_container_width=True, key=f"university_link_{row_start}_{university['name']}")


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
    saved_page = st.session_state.pop("theme_return_page", "")
    if saved_page in PAGES or (saved_page == "Admin" and is_admin()):
        # This runs before the sidebar radio widget is created, so Streamlit
        # can safely restore its selected item on the theme-change rerun.
        st.session_state.nav_page = saved_page
    page = render_sidebar()
    if page == "Dashboard": render_dashboard()
    elif page == "Explore Careers": render_explore_careers()
    elif page == "Career Quest": render_career_game()
    elif page == "Career Journal": render_career_journal()
    elif page == "Skill Roadmap": render_skill_roadmap()
    elif page == "Universities": render_universities()
    elif page == "Scholarships": render_scholarships()
    elif page == "AI Mentor": render_ai_mentor()
    elif page == "Change Password": render_change_password()
    elif page == "Admin": render_admin()
    else: render_simple_page(page)


def main() -> None:
    init_state()
    restore_session_from_url()
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
