from datetime import datetime
import streamlit as st


LOGO_PATH = "assets/career-ai-logo-cropped.png"
st.set_page_config(page_title="Career AI", page_icon=LOGO_PATH, layout="wide")

PAGES = (
    "Dashboard",
    "Assessments",
    "Explore Careers",
    "Skill Roadmap",
    "Scholarships",
    "Universities",
    "Profile",
    "AI Mentor",
)
PAGE_ICONS = {
    "Dashboard": "⌂",
    "Assessments": "✓",
    "Explore Careers": "⌕",
    "Skill Roadmap": "↗",
    "Scholarships": "✦",
    "Universities": "♜",
    "Profile": "♙",
    "AI Mentor": "✧",
}

RIASEC_TYPES = {
    "R": ("Realistic", "The Doer", "hands-on work, tools, and practical problem-solving", "🔧"),
    "I": ("Investigative", "The Thinker", "research, analysis, and discovering how things work", "🔬"),
    "A": ("Artistic", "The Creator", "ideas, design, expression, and original work", "🎨"),
    "S": ("Social", "The Helper", "teaching, supporting, and working with people", "🤝"),
    "E": ("Enterprising", "The Persuader", "leading, persuading, and building initiatives", "🚀"),
    "C": ("Conventional", "The Organizer", "structure, accuracy, systems, and planning", "📋"),
}

# Three statements per RIASEC theme keep the assessment approachable while
# retaining the scoring model used by the Flask prototype (1–5 per statement).
RIASEC_QUESTIONS = (
    ("R", "I enjoy building, repairing, or working with physical objects."),
    ("R", "I like solving practical problems by trying things out."),
    ("R", "I would enjoy a role involving equipment, technology, or the outdoors."),
    ("I", "I enjoy investigating questions until I understand the answer."),
    ("I", "I like working with facts, data, or complex ideas."),
    ("I", "I am curious about why things happen and how systems work."),
    ("A", "I enjoy expressing myself through writing, art, design, or performance."),
    ("A", "I prefer work that lets me create original ideas or experiences."),
    ("A", "I notice visual details and enjoy making things more appealing."),
    ("S", "I enjoy helping people learn, feel supported, or solve their problems."),
    ("S", "I would rather collaborate with people than work entirely alone."),
    ("S", "I am patient when listening to someone else's perspective."),
    ("E", "I enjoy taking the lead and motivating others toward a goal."),
    ("E", "I am comfortable presenting ideas and influencing decisions."),
    ("E", "I like turning opportunities into plans or projects."),
    ("C", "I enjoy organizing information and keeping track of details."),
    ("C", "I feel satisfied when a process is accurate and well structured."),
    ("C", "I like setting plans, deadlines, and clear next steps."),
)

CAREER_MAPPING = {
    "AI": ("UX Designer", "Product Designer", "Content Strategist"),
    "IA": ("UX Designer", "Data Visualisation Specialist", "Researcher"),
    "IR": ("Data Analyst", "Engineer", "Lab Technologist"),
    "IS": ("Psychologist", "Healthcare Researcher", "Teacher"),
    "SA": ("Clinical Psychologist", "Teacher", "Communications Specialist"),
    "SE": ("HR Specialist", "Business Development Manager", "Social Entrepreneur"),
    "EC": ("Project Manager", "Marketing Manager", "Business Analyst"),
    "CE": ("Operations Manager", "Financial Analyst", "Project Coordinator"),
    "CR": ("Accountant", "Quality Analyst", "Systems Administrator"),
    "RA": ("Architect", "Industrial Designer", "Photographer"),
}

INTAKE_SECTIONS = {
    "short": (
        ("About you", ("What subjects or activities do you enjoy most?", "What strengths do people often notice in you?")),
        ("Your future", ("What kind of impact would you like your work to have?", "What careers are you curious about right now?")),
    ),
    "long": (
        ("About you", ("What subjects or activities do you enjoy most?", "What strengths do people often notice in you?", "Which tasks give you the most energy?")),
        ("Your learning style", ("How do you prefer to learn something new?", "Describe a project or achievement you are proud of.", "What skills would you like to develop next?")),
        ("Your future", ("What kind of impact would you like your work to have?", "What work environment suits you best?", "What careers are you curious about right now?")),
    ),
}

WORKSTYLE_DIMENSIONS = (
    ("Collaboration", "Independent work", "Team collaboration"),
    ("Decision-making", "Evidence and analysis", "Intuition and possibility"),
    ("Structure", "Flexible and spontaneous", "Planned and structured"),
    ("Focus", "Big-picture strategy", "Detail and precision"),
    ("Energy", "Quiet, focused settings", "People-facing, active settings"),
)

THEMES = {
    "Dark": {
        "app_bg": "radial-gradient(circle at 70% 2%, #34206c 0, #170b31 38%, #0d0820 100%)",
        "text": "#fbfaff",
        "muted": "#bdb4d4",
        "card": "linear-gradient(145deg, rgba(37,24,76,.96), rgba(16,10,42,.96))",
        "card_soft": "rgba(35, 23, 71, .84)",
        "line": "rgba(190, 156, 255, .22)",
        "sidebar": "#0d0824",
        "input": "rgba(13, 8, 32, .78)",
        "shadow": "rgba(0, 0, 0, .27)",
        "score": "linear-gradient(135deg, #4d26c5, #1e4eaa)",
        "mentor": "linear-gradient(145deg, rgba(69, 29, 93, .86), rgba(18, 11, 45, .96))",
    },
    "Light": {
        "app_bg": "radial-gradient(circle at 72% 5%, #ffffff 0, #f0edff 43%, #e5e0ff 100%)",
        "text": "#28184d",
        "muted": "#71628d",
        "card": "linear-gradient(145deg, rgba(255,255,255,.98), rgba(248,246,255,.98))",
        "card_soft": "rgba(255,255,255,.9)",
        "line": "rgba(124, 58, 237, .20)",
        "sidebar": "#201153",
        "input": "#ffffff",
        "shadow": "rgba(67, 37, 128, .12)",
        "score": "linear-gradient(135deg, #7542df, #5e94ef)",
        "mentor": "linear-gradient(145deg, #ffffff, #f8f5ff)",
    },
}


def init_state() -> None:
    st.session_state.setdefault("show_dashboard", False)
    st.session_state.setdefault("nav_page", "Dashboard")
    st.session_state.setdefault("light_mode", False)
    st.session_state.setdefault("intake_answers", {})
    st.session_state.setdefault("intake_completed_at", None)
    st.session_state.setdefault("riasec_scores", None)
    st.session_state.setdefault("workstyle_results", None)


def profile_name() -> str:
    """Use the first intake answer as a friendly fallback-free greeting."""
    return st.session_state.get("student_name", "Aanya")


def career_matches() -> tuple[str, ...]:
    scores = st.session_state.get("riasec_scores")
    if not scores:
        return ("UX Designer", "Data Analyst", "Clinical Psychologist")
    ranked = sorted(scores, key=scores.get, reverse=True)
    code = "".join(ranked[:2])
    return CAREER_MAPPING.get(code) or CAREER_MAPPING.get(code[::-1]) or CAREER_MAPPING.get(ranked[0], ("Career Explorer",))


def assessment_progress() -> int:
    completed = sum((
        bool(st.session_state.get("intake_answers")),
        bool(st.session_state.get("riasec_scores")),
        bool(st.session_state.get("workstyle_results")),
    ))
    return round(completed * 100 / 3)


def current_theme() -> str:
    return "Light" if st.session_state.light_mode else "Dark"


def inject_styles(theme_name: str) -> None:
    theme = THEMES[theme_name]
    st.markdown(
        f"""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Space+Grotesk:wght@500;600;700&display=swap');
        :root {{
          --app-bg:{theme['app_bg']}; --text:{theme['text']}; --muted:{theme['muted']};
          --card:{theme['card']}; --card-soft:{theme['card_soft']}; --line:{theme['line']};
          --sidebar:{theme['sidebar']}; --input:{theme['input']}; --shadow:{theme['shadow']};
          --score:{theme['score']}; --mentor:{theme['mentor']}; --violet:#7c3aed; --pink:#ec5b7a; --mint:#15bfa2;
        }}
        * {{ font-family:'DM Sans',sans-serif; }}
        .stApp {{ background:var(--app-bg); color:var(--text); }}
        #MainMenu, footer, header {{ visibility:hidden; }}
        .block-container {{ max-width:1530px; padding-top:1.6rem; padding-bottom:2.6rem; }}
        [data-testid='stSidebar'] {{ background:var(--sidebar); border-right:1px solid rgba(211,193,255,.24); }}
        [data-testid='stSidebar'] * {{ color:#f8f5ff !important; }}
        [data-testid='stSidebar'] .stRadio label {{ padding:7px 5px; border-radius:10px; }}
        h1,h2,h3 {{ font-family:'Space Grotesk',sans-serif; color:var(--text); letter-spacing:-.55px; }}
        label,p {{ color:var(--text); }}
        .brand {{ display:flex; align-items:center; gap:10px; margin:5px 0 22px; }}
        .brand-mark {{ width:45px; height:45px; border-radius:15px; display:grid; place-items:center; font-size:27px; background:linear-gradient(135deg,#e83d60,#7247e9); box-shadow:0 9px 25px rgba(221,54,132,.35); }}
        .brand-name {{ color:#fff; font-size:1.35rem; font-family:'Space Grotesk',sans-serif; font-weight:700; }} .brand-name span {{ color:#ff6b81; }}
        .sidebar-brand {{ padding-top:3px; }} .sidebar-brand .brand-name {{ margin:0; white-space:nowrap; }} .sidebar-tagline {{ color:#cfc4eb; font-size:.73rem; margin-top:4px; white-space:nowrap; }}
        .top-title {{ font-family:'Space Grotesk',sans-serif; font-weight:700; color:var(--text); font-size:2.25rem; letter-spacing:-1.5px; margin:0 0 2px; }}
        .top-subtitle {{ color:var(--muted); font-size:1.03rem; margin-bottom:17px; }}
        .panel {{ background:var(--card); border:1px solid var(--line); border-radius:17px; padding:19px; box-shadow:0 15px 38px var(--shadow); box-sizing:border-box; height:100%; }}
        .panel-title {{ font-family:'Space Grotesk',sans-serif; font-weight:700; color:var(--text); font-size:1.07rem; margin:0 0 15px; }}
        .panel-link {{ color:#8b5cf6; font-weight:700; font-size:.84rem; float:right; }}
        .score-panel {{ background:var(--score); color:#fff; border-radius:17px; padding:24px; min-height:250px; box-shadow:0 16px 38px var(--shadow); }}
        .score-panel h3,.score-panel p {{ color:#fff; }} .score-panel p {{ color:rgba(255,255,255,.78); }}
        .big-score {{ font-family:'Space Grotesk',sans-serif; font-weight:700; font-size:3.15rem; color:#fff; margin:24px 0 12px; }}
        .score-ring {{ float:right; margin-top:-76px; width:100px; height:100px; border-radius:50%; border:12px solid rgba(255,255,255,.19); border-top-color:#fff; border-right-color:#fff; box-sizing:border-box; }}
        .match-card {{ background:var(--card-soft); border:1px solid var(--line); border-radius:12px; padding:13px; min-height:185px; box-sizing:border-box; }}
        .match-grid,.mini-grid {{ display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:10px; }} .roadmap-grid {{ display:grid; grid-template-columns:1.35fr .65fr; gap:16px; }}
        .icon-bubble {{ width:42px; height:42px; border-radius:14px; display:grid; place-items:center; background:rgba(124,58,237,.13); font-size:1.35rem; }}
        .match-name {{ color:var(--text); font-weight:700; margin:10px 0 4px; }} .match-copy {{ color:var(--muted); font-size:.8rem; line-height:1.45; min-height:58px; }}
        .match-pill {{ float:right; color:var(--mint); background:rgba(21,191,162,.13); padding:4px 7px; border-radius:7px; font-size:.72rem; font-weight:700; }}
        .tiny-link {{ color:#8b5cf6; font-size:.78rem; font-weight:700; }}
        .mentor-panel {{ background:var(--mentor); border:1px solid rgba(236,91,122,.44); border-radius:17px; padding:21px; min-height:100%; text-align:center; box-shadow:0 15px 38px var(--shadow); box-sizing:border-box; }}
        .mentor-panel h3 {{ text-align:left; margin:0; }} .mentor-orb {{ width:102px; height:102px; border-radius:50%; margin:33px auto 22px; display:grid; place-items:center; font-size:47px; background:radial-gradient(circle,#3d1959,#100a29); border:2px solid #9d5cff; box-shadow:0 0 0 13px rgba(140,78,245,.08); }}
        .st-key-ai_mentor_card {{ background:var(--mentor); border:1px solid rgba(236,91,122,.44)!important; border-radius:17px; padding:12px 13px 16px; box-shadow:0 15px 38px var(--shadow); text-align:center; }}
        .st-key-ai_mentor_card img {{ filter:drop-shadow(0 0 9px rgba(167,99,255,.9)) drop-shadow(0 0 22px rgba(236,91,122,.42)); }}
        .roadmap {{ border-left:2px solid rgba(124,58,237,.35); margin:5px 0 0 8px; }} .roadmap-item {{ padding:0 0 13px 16px; position:relative; color:var(--text); font-size:.83rem; }} .roadmap-item:before {{ content:''; position:absolute; left:-8px; top:4px; width:13px; height:13px; border-radius:50%; background:#7352e7; box-shadow:0 0 0 3px rgba(124,58,237,.14); }} .roadmap-item.done:before {{ background:var(--mint); }} .roadmap-sub {{ color:var(--muted); font-size:.72rem; }}
        .progress-circle {{ width:105px; height:105px; border:11px solid rgba(124,58,237,.18); border-top-color:#7c3aed; border-right-color:#7c3aed; border-radius:50%; display:grid; place-items:center; font-weight:700; font-size:1.45rem; margin:12px auto; }}
        .insight {{ display:flex; gap:10px; padding:12px 0; border-top:1px solid var(--line); color:var(--muted); font-size:.8rem; line-height:1.42; }} .insight:first-of-type {{ border-top:0; }} .insight-icon {{ color:#8b5cf6; font-size:1.25rem; }}
        .course-card,.scholar-card {{ background:var(--card-soft); border:1px solid var(--line); border-radius:12px; padding:12px; min-height:102px; box-sizing:border-box; }}
        .course-card b,.scholar-card b {{ color:var(--text); font-size:.78rem; }} .course-meta {{ color:var(--muted); font-size:.72rem; margin-top:16px; }} .price {{ color:var(--mint); font-weight:700; font-size:.8rem; margin-top:13px; }}
        .university-row {{ display:flex; justify-content:space-between; align-items:center; border-top:1px solid var(--line); padding:12px 0; color:var(--text); font-weight:600; font-size:.86rem; }} .university-row:first-of-type {{ border-top:0; }}
        .tag {{ color:var(--mint); background:rgba(21,191,162,.13); border-radius:7px; padding:5px 8px; font-size:.71rem; font-weight:700; }}
        .login-panel {{ background:var(--card); border:1px solid var(--line); border-radius:28px; padding:43px; box-shadow:0 22px 64px var(--shadow); }} .login-title {{ font-family:'Space Grotesk',sans-serif; color:var(--text); font-size:2.65rem; line-height:1.05; letter-spacing:-1.5px; margin:0 0 10px; }} .login-subtitle {{ color:var(--muted); margin-bottom:22px; }}
        .career-visual {{ position:relative; min-height:610px; display:flex; align-items:center; justify-content:center; overflow:hidden; }} .orb {{ position:absolute; width:480px; height:480px; border:1px dashed rgba(124,58,237,.35); border-radius:50%; }} .career-quote {{ position:relative; z-index:2; max-width:370px; text-align:center; font-family:'Space Grotesk',sans-serif; color:var(--text); font-size:2.9rem; line-height:1.04; font-weight:700; letter-spacing:-1.9px; }} .career-quote span {{ color:var(--pink); }} .float {{ position:absolute; z-index:3; display:grid; place-items:center; width:93px; height:93px; border:1px solid var(--line); background:var(--card-soft); border-radius:26px; font-size:3.15rem; box-shadow:0 13px 32px var(--shadow); animation:drift 4s ease-in-out infinite; }} .one{{top:45px;left:15%}}.two{{top:48px;right:15%;animation-delay:-1s}}.three{{top:233px;left:2%;animation-delay:-2s}}.four{{top:233px;right:2%;animation-delay:-.5s}}.five{{bottom:44px;left:17%;animation-delay:-2.5s}}.six{{bottom:44px;right:17%;animation-delay:-1.5s}} @keyframes drift{{50%{{transform:translateY(-12px) rotate(3deg)}}}}
        div[data-baseweb='input']>div {{ background:var(--input)!important; border-color:var(--line)!important; color:var(--text)!important; }} input {{ color:var(--text)!important; }} .stButton>button,button[kind='primary'] {{ background:linear-gradient(90deg,#7c3aed,#ef5e7d); color:#fff; border:0; border-radius:10px; font-weight:700; min-height:42px; }} .stButton>button:hover{{border:0;filter:brightness(1.08)}}
        @media(max-width:900px){{.block-container{{padding:1rem}}.login-panel{{padding:30px 22px}}.career-visual{{min-height:400px}}.career-quote{{font-size:2.1rem}}.float{{width:67px;height:67px;font-size:2.2rem}}.top-title{{font-size:1.9rem}}.match-grid,.mini-grid{{grid-template-columns:1fr}}.roadmap-grid{{grid-template-columns:1fr}}}}
        </style>
        """,
        unsafe_allow_html=True,
    )


def go_to(page: str) -> None:
    st.session_state.nav_page = page


def render_login() -> None:
    top_left, top_right = st.columns([5, 1])
    with top_right:
        st.toggle("☀️ Light mode", key="light_mode")

    left, right = st.columns([0.9, 1.1], gap="large")
    with left:
        st.image(LOGO_PATH, width=86)
        st.markdown("""
        <div class='login-panel'>
          <div class='brand'><div class='brand-name'>Career <span>AI</span></div></div>
          <h1 class='login-title'>Welcome back</h1>
          <div class='login-subtitle'>Your future is waiting.</div>
        """, unsafe_allow_html=True)
        st.text_input("Username or email", placeholder="Enter your username or email")
        st.text_input("Password", placeholder="Enter your password", type="password")
        st.checkbox("Remember me")
        if st.button("Sign in  →", use_container_width=True):
            st.session_state.show_dashboard = True
            st.rerun()
        st.markdown("<p style='text-align:center;color:var(--muted);margin:28px 0 0'>New to Career AI? <span style='color:#8b5cf6;font-weight:700'>Create an account</span></p></div>", unsafe_allow_html=True)
    with right:
        st.markdown("""
        <div class='career-visual'>
          <div class='orb'></div><div class='float one'>🩺</div><div class='float two'>💻</div>
          <div class='float three'>🏏</div><div class='float four'>🎓</div>
          <div class='float five'>🎨</div><div class='float six'>🔬</div>
          <div class='career-quote'>Every interest<br>can become a <span>future.</span></div>
        </div>
        """, unsafe_allow_html=True)


def render_sidebar() -> str:
    with st.sidebar:
        logo_col, name_col = st.columns([.3, .7], gap="small")
        with logo_col:
            st.image(LOGO_PATH, width=62)
        with name_col:
            st.markdown("<div class='sidebar-brand'><div class='brand-name'>Career <span>AI</span></div><div class='sidebar-tagline'>Your AI Career Mentor</div></div>", unsafe_allow_html=True)
        st.markdown("---")
        labels = [f"{PAGE_ICONS[page]}  {page}" for page in PAGES]
        choice = st.radio("Navigation", labels, index=PAGES.index(st.session_state.nav_page), label_visibility="collapsed")
        page = choice[3:]
        st.session_state.nav_page = page
        st.markdown("---")
        if st.button("Log out", use_container_width=True):
            st.session_state.show_dashboard = False
            st.session_state.nav_page = "Dashboard"
            st.rerun()
    return page


def render_heading() -> None:
    st.markdown(f"<div class='top-title'>Good morning, {profile_name()} 👋</div><div class='top-subtitle'>Let’s build your future, one step at a time.</div>", unsafe_allow_html=True)


def render_dashboard() -> None:
    render_heading()
    progress = assessment_progress()
    matches = career_matches()
    score_col, matches_col, mentor_col = st.columns([1.05, 1.43, .67], gap="medium")
    with score_col:
        score_copy = "Your assessment results are shaping your matches." if progress else "Complete an assessment to personalise this score."
        st.markdown(f"""
        <div class='score-panel'><h3>Career Discovery Progress</h3><div class='big-score'>{progress}%</div><div class='score-ring'></div>
        <b>{'You’re building a clear picture!' if progress else 'Start your discovery journey.'}</b><p>{score_copy}</p></div>
        """, unsafe_allow_html=True)
    with matches_col:
        descriptions = (
            "Explore a path that fits the interests you shared.",
            "Use your strongest themes to guide your next steps.",
            "Compare courses, skills, and real-world opportunities.",
        )
        cards = tuple(("✦", name, f"{max(70, 94 - index * 4)}%", descriptions[index]) for index, name in enumerate(matches[:3]))
        cards_html = "".join(
            f"<div class='match-card'><span class='match-pill'>{score}</span><div class='icon-bubble'>{icon}</div><div class='match-name'>{name}</div><div class='match-copy'>{copy}</div><span class='tiny-link'>Explore career →</span></div>"
            for icon, name, score, copy in cards
        )
        st.markdown(f"<div class='panel'><span class='panel-link'>View all →</span><div class='panel-title'>Top Career Matches</div><div class='match-grid'>{cards_html}</div></div>", unsafe_allow_html=True)
    with mentor_col:
        with st.container(border=True, key="ai_mentor_card"):
            st.markdown("### AI Mentor")
            _, logo_col, _ = st.columns([1, 1.4, 1])
            with logo_col:
                st.image(LOGO_PATH, use_container_width=True)
            st.markdown("**Ask your AI Mentor**")
            st.caption("Get personalised guidance, clarity, and career advice whenever you need it.")
            st.button("Start a conversation", use_container_width=True)

    roadmap_col, insight_col = st.columns([1.02, .98], gap="medium")
    with roadmap_col:
        st.markdown("""<div class='panel'><span class='panel-link'>View full roadmap</span><div class='panel-title'>Your Learning Roadmap</div><div class='roadmap-grid'><div class='roadmap'>
              <div class='roadmap-item done'><b>1. Self Discovery</b><br><span class='roadmap-sub'>Complete your assessments</span></div>
              <div class='roadmap-item'><b>2. Career Exploration</b><br><span class='roadmap-sub'>Review your recommended paths</span></div>
              <div class='roadmap-item'><b>3. Skill Building</b><br><span class='roadmap-sub'>In progress</span></div>
              <div class='roadmap-item'><b>4. Real World Preparation</b><br><span class='roadmap-sub'>Upcoming</span></div>
              <div class='roadmap-item'><b>5. Career Launch</b><br><span class='roadmap-sub'>Upcoming</span></div>
            </div><div><div class='progress-circle'>{progress}%</div><p style='text-align:center;margin:0'><b>Overall Progress</b><br><span style='color:var(--muted);font-size:.78rem'>Complete the three assessments.</span></p></div></div></div>""", unsafe_allow_html=True)
    with insight_col:
        st.markdown("""<div class='panel'><span class='panel-link'>View all insights</span><div class='panel-title'>✧ AI Insights</div>
        <div class='insight'><span class='insight-icon'>◎</span><span>You have strong analytical and problem-solving skills, ideal for roles in data and research.</span></div>
        <div class='insight'><span class='insight-icon'>↗</span><span>Gaining expertise in tools like Figma and SQL can boost your career prospects.</span></div>
        <div class='insight'><span class='insight-icon'>♙</span><span>Consider internships in the next 6 months to gain hands-on experience.</span></div></div>""", unsafe_allow_html=True)

    courses_col, universities_col, scholarship_col = st.columns([1.02, .78, 1.2], gap="medium")
    with courses_col:
        courses_html = "".join(f"<div class='course-card'><b>{name}</b><div class='course-meta'>Course provider<br><span class='mint'>4.8 ★</span></div></div>" for name in ("UI/UX Design Fundamentals", "SQL for Data Analysis", "Data Visualization"))
        st.markdown(f"<div class='panel'><span class='panel-link'>View all</span><div class='panel-title'>Recommended Courses</div><div class='mini-grid'>{courses_html}</div></div>", unsafe_allow_html=True)
    with universities_col:
        st.markdown("""<div class='panel'><span class='panel-link'>Browse</span><div class='panel-title'>Top Universities for You</div>
          <div class='university-row'><span>IIT Bombay</span><span class='tag'>Match 94%</span></div>
          <div class='university-row'><span>NID Ahmedabad</span><span class='tag'>Match 91%</span></div>
          <div class='university-row'><span>Ashoka University</span><span class='tag'>Match 88%</span></div></div>""", unsafe_allow_html=True)
    with scholarship_col:
        scholarships_html = "".join(f"<div class='scholar-card'><b>{name}</b><div class='price'>{price}</div><div class='course-meta'>Deadline: Aug 2026</div></div>" for name, price in zip(("Future Leaders Scholarship", "Women in Tech Scholarship", "Merit Excellence Award"), ("Up to $5,000", "Up to $3,000", "Up to $2,500")))
        st.markdown(f"<div class='panel'><span class='panel-link'>View all</span><div class='panel-title'>Scholarship Recommendations</div><div class='mini-grid'>{scholarships_html}</div></div>", unsafe_allow_html=True)


def render_intake_assessment() -> None:
    mode_label = st.radio("Choose the intake length", ("Quick check-in (4 questions)", "Full reflection (9 questions)"), horizontal=True)
    mode = "short" if mode_label.startswith("Quick") else "long"
    st.caption("Your answers help you reflect on your interests before you see career recommendations.")
    with st.form(f"intake_form_{mode}"):
        answers: dict[str, str] = {}
        for section_number, (section, questions) in enumerate(INTAKE_SECTIONS[mode], start=1):
            st.markdown(f"#### {section_number}. {section}")
            for question_number, question in enumerate(questions, start=1):
                key = f"intake_{mode}_{section_number}_{question_number}"
                answers[key] = st.text_area(question, key=key, height=78)
        submitted = st.form_submit_button("Save intake profile →", use_container_width=True)
    if submitted:
        st.session_state.intake_answers = {key: answer.strip() for key, answer in answers.items()}
        st.session_state.intake_completed_at = datetime.now().strftime("%B %d, %Y at %I:%M %p")
        st.success("Your intake profile has been saved.")

    if st.session_state.intake_answers:
        answered = sum(bool(answer) for answer in st.session_state.intake_answers.values())
        total = len(st.session_state.intake_answers)
        st.info(f"Intake profile: {answered}/{total} questions answered • {st.session_state.intake_completed_at}")


def render_riasec_assessment() -> None:
    st.caption("Rate each statement from 1 (not like me) to 5 (very much like me).")
    labels = {1: "Not like me", 2: "A little like me", 3: "Somewhat like me", 4: "Mostly like me", 5: "Very much like me"}
    with st.form("riasec_form"):
        values: dict[str, int] = {}
        for position, (type_code, question) in enumerate(RIASEC_QUESTIONS, start=1):
            name, _, _, icon = RIASEC_TYPES[type_code]
            values[f"riasec_{position}"] = st.radio(
                f"{icon} {position}. {question}",
                options=tuple(labels),
                format_func=labels.get,
                horizontal=True,
                key=f"riasec_{position}",
            )
        submitted = st.form_submit_button("See my RIASEC results →", use_container_width=True)
    if submitted:
        scores = {code: 0 for code in RIASEC_TYPES}
        for position, (type_code, _) in enumerate(RIASEC_QUESTIONS, start=1):
            scores[type_code] += values[f"riasec_{position}"]
        st.session_state.riasec_scores = scores
        st.success("Your RIASEC profile is ready.")

    scores = st.session_state.riasec_scores
    if scores:
        ranked = sorted(scores, key=scores.get, reverse=True)
        first, second = ranked[:2]
        st.markdown("#### Your results")
        result_columns = st.columns(3)
        for column, code in zip(result_columns, ranked[:3]):
            name, nickname, description, icon = RIASEC_TYPES[code]
            with column:
                st.markdown(f"<div class='panel'><div class='icon-bubble'>{icon}</div><h3>{name}</h3><p><b>{scores[code]}/15</b> · {nickname}</p><p style='color:var(--muted)'>{description}</p></div>", unsafe_allow_html=True)
        st.info(f"Your Holland code is **{first}{second}**. Suggested paths: **{', '.join(career_matches())}**.")


def render_workstyle_assessment() -> None:
    st.caption("Choose where you naturally sit on each work-style spectrum.")
    with st.form("workstyle_form"):
        values: dict[str, int] = {}
        for number, (title, left, right) in enumerate(WORKSTYLE_DIMENSIONS, start=1):
            st.markdown(f"**{title}** — {left} ↔ {right}")
            values[title] = st.slider(title, 1, 7, 4, key=f"workstyle_{number}", label_visibility="collapsed")
        submitted = st.form_submit_button("Save work-style profile →", use_container_width=True)
    if submitted:
        st.session_state.workstyle_results = values
        st.success("Your work-style profile has been saved.")

    results = st.session_state.workstyle_results
    if results:
        st.markdown("#### Your work-style profile")
        for title, left, right in WORKSTYLE_DIMENSIONS:
            score = results[title]
            tendency = right if score >= 5 else left if score <= 3 else "Balanced"
            st.progress((score - 1) / 6, text=f"{title}: {tendency} ({score}/7)")


def render_assessments() -> None:
    st.markdown("<div class='top-title'>Discover what fits you</div><div class='top-subtitle'>Complete the assessments below to turn your interests into useful career direction.</div>", unsafe_allow_html=True)
    intake_tab, riasec_tab, workstyle_tab = st.tabs(("1. Intake profile", "2. RIASEC interests", "3. Work style"))
    with intake_tab:
        render_intake_assessment()
    with riasec_tab:
        render_riasec_assessment()
    with workstyle_tab:
        render_workstyle_assessment()