import streamlit as st
import google.generativeai as genai
from datetime import datetime
import requests
from bs4 import BeautifulSoup
import re

st.set_page_config(
    page_title="The Analyst",
    page_icon="📰",
    layout="wide",
    initial_sidebar_state="expanded"
)

# CSS load from file
def load_css():
    with open("style.css", "r", encoding="utf-8") as f:
        css = f.read()
    st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)

load_css()

# ══════════════════════════════════════════
#  SESSION STATE
# ══════════════════════════════════════════
SECTIONS = [
    "sentences", "vocabulary", "context", "grammar",
    "collocations", "formulas", "exam", "mistakes", "revision",
]

SECTION_LABELS = {
    "sentences":    "📖 Sentences",
    "vocabulary":   "💎 Vocabulary",
    "context":      "🌍 Context & History",
    "grammar":      "🏛️ Grammar",
    "collocations": "🔗 Collocations",
    "formulas":     "✍️ Formulas",
    "exam":         "🏆 Exam Prep",
    "mistakes":     "❌ Mistake Radar",
    "revision":     "📸 Revision Card",
}

for k, v in {
    "saved_vocab": [],
    "notes": [],
    "total": 0,
    "cache": {},
    "results": {},
    "current_text": "",
    "fetched_title": "",
    "fetched_source": "",
    "analysis_done": False,
}.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ══════════════════════════════════════════
#  SIDEBAR
# ══════════════════════════════════════════
with st.sidebar:
    st.markdown("## ⚙️ Control Panel")
    st.divider()

    api_key = st.text_input("🔑 API Key", type="password",
                            placeholder="Gemini API key...")

    model_choice = st.selectbox("🤖 Model", [
        "gemini-3.5-flash-lite",
        "gemini-3.8-flash",
        "gemini-3.6-flash",
        "gemini-3.1-flash-lite",
        "gemini-1.5-pro",
    ], index=0)

    difficulty = st.select_slider(
        "📊 Level",
        ["Beginner", "Intermediate", "Advanced", "Expert"],
        value="Advanced"
    )

    pub_style = st.selectbox("🎯 Style", [
        "The Economist", "New York Times", "The Guardian",
        "BBC News", "Academic / IELTS", "Legal / Constitutional",
    ])

    analysis_type = st.selectbox("📋 Mode", [
        "General (News / Editorial)", "Law / Constitutional",
        "Economics / Business", "Political Science",
        "Science / Environment",
    ])

    st.divider()
    c1, c2 = st.columns(2)
    c1.metric("Runs", st.session_state.total)
    c2.metric("Words", len(st.session_state.saved_vocab))

    if st.button("🗑️ Clear All", use_container_width=True):
        st.session_state.cache = {}
        st.session_state.results = {}
        st.session_state.analysis_done = False
        st.session_state.current_text = ""
        st.session_state.fetched_title = ""
        st.session_state.fetched_source = ""
        st.success("Cleared!")
        st.rerun()


# ══════════════════════════════════════════
#  WEB SCRAPER — 3 LAYER SYSTEM
# ══════════════════════════════════════════
def extract_article_from_url(url: str):
    from urllib.parse import urlparse

    def try_direct(url):
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        }
        try:
            resp = requests.get(url, headers=headers, timeout=15)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")

            title = ""
            if soup.find("h1"):
                title = soup.find("h1").get_text(strip=True)
            elif soup.title:
                title = soup.title.get_text(strip=True)

            source = urlparse(url).netloc.replace("www.", "")

            for tag in soup([
                "script", "style", "nav", "header", "footer",
                "aside", "iframe", "noscript", "form", "button",
                "figure", "figcaption", "picture"
            ]):
                tag.decompose()

            article_text = ""
            selectors = [
                "article", "[class*='article-body']",
                "[class*='story-body']", "[class*='post-content']",
                "[class*='entry-content']", "[class*='article-content']",
                "[class*='content-body']", "[class*='news-body']",
                "[class*='main-content']", "main", "[role='main']",
            ]

            for selector in selectors:
                container = soup.select_one(selector)
                if container:
                    paragraphs = container.find_all("p")
                    text = " ".join(
                        p.get_text(strip=True) for p in paragraphs
                        if len(p.get_text(strip=True)) > 40
                    )
                    if len(text) > 300:
                        article_text = text
                        break

            if len(article_text) < 300:
                all_p = soup.find_all("p")
                article_text = " ".join(
                    p.get_text(strip=True) for p in all_p
                    if len(p.get_text(strip=True)) > 50
                )

            article_text = re.sub(r'\s+', ' ', article_text).strip()

            if len(article_text) > 300:
                words = article_text.split()
                if len(words) > 4000:
                    article_text = " ".join(words[:4000]) + "..."
                return title, source, article_text, None

        except Exception:
            pass
        return None, None, None, "layer1_failed"

    def try_jina(url):
        try:
            jina_url = f"https://r.jina.ai/{url}"
            headers = {
                "Accept": "text/plain",
                "User-Agent": "Mozilla/5.0",
                "X-Return-Format": "text",
            }
            resp = requests.get(jina_url, headers=headers, timeout=20)

            if resp.status_code == 200 and len(resp.text) > 200:
                raw = resp.text

                title = ""
                title_match = re.search(r'^Title:\s*(.+)$', raw, re.MULTILINE)
                if title_match:
                    title = title_match.group(1).strip()

                lines = raw.split('\n')
                content_lines = []
                skip_patterns = [
                    'Title:', 'URL Source:', 'Published Time:',
                    'Warning:', 'Image ', '================',
                    'Links/Buttons:', '* [', '![',
                ]
                for line in lines:
                    if any(line.strip().startswith(p) for p in skip_patterns):
                        continue
                    if line.strip():
                        content_lines.append(line.strip())

                article_text = " ".join(content_lines)
                article_text = re.sub(r'\s+', ' ', article_text).strip()
                article_text = re.sub(r'\[.*?\]\(.*?\)', '', article_text)

                source = urlparse(url).netloc.replace("www.", "")

                if len(article_text) > 300:
                    words = article_text.split()
                    if len(words) > 4000:
                        article_text = " ".join(words[:4000]) + "..."
                    return title, source, article_text, None

        except Exception:
            pass
        return None, None, None, "layer2_failed"

    def try_gemini_url(url):
        if not api_key:
            return None, None, None, "no_api_key"
        try:
            source = urlparse(url).netloc.replace("www.", "")
            genai.configure(api_key=api_key.strip())
            model = genai.GenerativeModel("gemini-1.5-flash")
            prompt = f"""
Visit this URL and extract the main article text:
URL: {url}

Return ONLY in this format:
TITLE: [article title]
SOURCE: [website name]
TEXT: [full article text, clean, no ads, no navigation]

If you cannot access the URL, say: CANNOT_ACCESS
"""
            resp = model.generate_content(prompt)
            raw = resp.text.strip()

            if "CANNOT_ACCESS" in raw:
                return None, None, None, "gemini_cannot_access"

            title = ""
            title_match = re.search(r'TITLE:\s*(.+)', raw)
            if title_match:
                title = title_match.group(1).strip()

            article_text = ""
            text_match = re.search(r'TEXT:\s*(.+)', raw, re.DOTALL)
            if text_match:
                article_text = text_match.group(1).strip()

            if len(article_text) > 200:
                words = article_text.split()
                if len(words) > 4000:
                    article_text = " ".join(words[:4000]) + "..."
                return title, source, article_text, None

        except Exception:
            pass
        return None, None, None, "layer3_failed"

    source = urlparse(url).netloc.replace("www.", "")

    title, src, text, err = try_direct(url)
    if text:
        return title, src, text, None

    title, src, text, err = try_jina(url)
    if text:
        return title or "", src or source, text, None

    title, src, text, err = try_gemini_url(url)
    if text:
        return title or "", src or source, text, None

    return "", source, "", (
        "⚠️ এই সাইটটি automatically fetch করা গেলো না।\n\n"
        "**কারণ:**\n"
        "- Paywall (subscription required)\n"
        "- JavaScript-heavy site\n"
        "- Bot protection (Cloudflare)\n\n"
        "**সমাধান:** Article manually copy করুন → "
        "Paste Text mode ব্যবহার করুন।"
    )


# ══════════════════════════════════════════
#  AI HELPERS
# ══════════════════════════════════════════
def build_system_header():
    law_note = ""
    if "Law" in analysis_type or "Constitutional" in analysis_type:
        law_note = """
⚖️ LAW/CONSTITUTION MODE:
- Identify constitutional articles, legal doctrines, landmark cases
- Bangladesh Constitution (1972) + relevant amendments
- International law / human rights angles
- Legal terms with full Bengali + English definitions
"""
    return f"""
You are an elite analyst: Oxford Professor · BCS Cadre · GRE 340 · NYT Senior Editor · Supreme Court Lawyer.
Level: {difficulty} | Style: {pub_style} | Mode: {analysis_type}
{law_note}
RULES:
1. Bengali (বাংলা হরফ) AND English — always both, side by side
2. ZERO Banglish
3. Specific — real years, real cases, real exam questions
4. Clean readable formatting — not walls of text
"""


def call_ai(prompt_text, cache_key=None):
    if not api_key:
        return None
    if cache_key and cache_key in st.session_state.cache:
        return st.session_state.cache[cache_key]
    try:
        genai.configure(api_key=api_key.strip())
        model = genai.GenerativeModel(
            model_name=model_choice,
            generation_config=genai.GenerationConfig(
                temperature=0.65,
                max_output_tokens=8192,
            )
        )
        resp = model.generate_content(prompt_text)
        result = resp.text
        if cache_key:
            st.session_state.cache[cache_key] = result
        st.session_state.total += 1
        return result
    except Exception as e:
        return f"❌ Error: {e}"


def show_result(result, filename_prefix="result"):
    if result:
        if result.startswith("❌"):
            st.error(result)
        else:
            st.markdown(result)
            st.download_button(
                "📥 Download",
                result,
                f"{filename_prefix}_{datetime.now().strftime('%Y%m%d_%H%M')}.md",
            )


# ══════════════════════════════════════════
#  SECTION PROMPTS
# ══════════════════════════════════════════
def prompt_sentences(text):
    return f"""
{build_system_header()}
TEXT: \"\"\"{text}\"\"\"

# 📖 SENTENCE-BY-SENTENCE ANALYSIS

For EVERY sentence in the text:

---
**S[N]:** *"[exact sentence]"*

| | |
|---|---|
| বাংলা অনুবাদ | [natural Bengali] |
| Clause Type | [Simple/Compound/Complex/Compound-Complex] |
| Clause Breakdown | [label each clause] |
| Grammar Device | [Parallelism/Inversion/Fronting/Passive/Cleft/Ellipsis] |
| কেন এই গঠন? | [Bengali explanation] |
| Why It Works | [English explanation] |
| BCS / Exam Link | [if applicable] |

---

## Transformation Exercises (BCS/Bank)
1. [Voice change] → ✅
2. [Degree change] → ✅
3. [Conditional] → ✅
4. [Reported speech] → ✅
5. [Simple ↔ Complex] → ✅
"""


def prompt_vocabulary(text):
    return f"""
{build_system_header()}
TEXT: \"\"\"{text}\"\"\"

# 💎 VOCABULARY INTELLIGENCE

## Quick Reference
| # | Word | বাংলা অর্থ | Definition | POS | Root | Frequency |
|---|---|---|---|---|---|---|

---

## Deep-Dive (every important word — minimum 12)

#### 🔤 [WORD]
**[Bengali meaning] · [English definition]**

| | |
|---|---|
| 🌱 Root | [root] → [language] → "[meaning]" |
| 📖 Etymology | [interesting origin — 2 sentences] |
| ⚡ Frequency | 🔴 HIGH / 🟡 MEDIUM / 🟢 LOW |

**Word Family:**
| Form | Word | Example |
|---|---|---|
| Noun | | |
| Verb | | |
| Adjective | | |
| Adverb | | |

**GRE Synonyms:**
- **[S1]** — [Bengali] — *[subtle difference]*
- **[S2]** — [Bengali] — *[subtle difference]*

**Antonyms:** [A1] ([Bengali]) · [A2] ([Bengali])

**🧠 Memory Hook:** [Bengali mnemonic]

**📰 {pub_style} Sentence:** > [Professional example]

**🏆 Exam Record:**
| Exam | Year | Question | Answer |
|---|---|---|---|
"""


def prompt_context(text):
    return f"""
{build_system_header()}
TEXT: \"\"\"{text}\"\"\"

# 🌍 CONTEXT & HISTORICAL INTELLIGENCE

## What This Is Really About
**EN:** [2-3 sentences]
**বাংলা:** [Bengali]

## The Immediate Context
[Narrative explanation — not bullet points]
বাংলা: [Bengali paragraph]

## Historical Timeline
| Year | Event | Where | Why It Matters |
|---|---|---|---|

## Famous & Notorious Related Events

### [Event Name] ([Year], [Place])
[4-5 sentences — what happened, why controversial, what changed]
**বাংলা:** [Bengali]

### [Event 2]
[Same]

### [Event 3]
[Same]

## 🇧🇩 Bangladesh Dimension
[Specific facts, laws, dates, figures]
**বাংলা:** [Bengali]

{"## ⚖️ Constitutional & Legal Map" if "Law" in analysis_type else ""}
{"[Relevant BD Constitution articles + landmark cases]" if "Law" in analysis_type else ""}

## 📆 On This Day ({datetime.now().strftime('%B %d')})
[Related historical event today]
"""


def prompt_grammar(text):
    return f"""
{build_system_header()}
TEXT: \"\"\"{text}\"\"\"

# 🏛️ GRAMMAR LABORATORY

## Advanced Syntax Devices
| Device | Example from Text | কেন কার্যকর (Bengali) | Why Effective (English) | BCS Use |
|---|---|---|---|---|

## Clause Architecture
For each complex sentence:

**"[sentence]"**
Main Clause: [...]
└─ Subordinate ([type]): [...]

text

বাংলা: [why this layering works]

## BCS/Bank Grammar Rules Found
| Rule | Exam Frequency | Sample Question | Answer |
|---|---|---|---|

## Transformation Exercises
**Ex 1 — Voice:** Original: [...] → ✅ | বাংলা নিয়ম: [...]
**Ex 2 — Degree:** → ✅
**Ex 3 — Conditional:** → ✅
**Ex 4 — Narration:** → ✅
**Ex 5 — Simple ↔ Complex:** → ✅
"""


def prompt_collocations(text):
    return f"""
{build_system_header()}
TEXT: \"\"\"{text}\"\"\"

# 🔗 COLLOCATION & PHRASE INTELLIGENCE

## Collocations Found
| Expression | Type | বাংলা | English | Register | Better Alternatives |
|---|---|---|---|---|---|

## Top 5 — Deep Analysis
**[collocation]**
- বাংলা: [meaning]
- Why it collocates: [English]
- ❌ Students write: [...] → ✅ Correct: [...]
- Example: > [{pub_style} sentence]

## Idioms & Fixed Expressions
| Expression | বাংলা | English | Origin | Exam |
|---|---|---|---|---|

## Phrasal Verbs
| Verb | বাংলা | Formal Equivalent | Example | Exam |
|---|---|---|---|---|

## Transition Map
| Transition | Category | বাংলা | Level | Better Options |
|---|---|---|---|---|

## Reference Chains
- "it" → refers to: [...]
- "they" → refers to: [...]
- "this" → refers to: [...]
"""


def prompt_formulas(text):
    return f"""
{build_system_header()}
TEXT: \"\"\"{text}\"\"\"

# ✍️ WRITING FORMULA LABORATORY

### Formula 1: [Pattern Name]
**Template:** `[SUBJECT] + [VERB], [CONCESSIVE], [ASSERTION].`
**From text:** *"[exact sentence]"*
**New example:** [fresh topic]
**কখন ব্যবহার:** [Bengali] | **When:** [English]
**IELTS/BCS Bonus:** [score impact]

### Formula 2: [Name]
[Same structure]

### Formula 3: [Name]
[Same]

### Formula 4: [Name]
[Same]

### Formula 5: [Name]
[Same]

### Formula 6: [Name]
[Same]

---

## Writing Drills

**Drill 1:** Use Formula 2. Topic: [related current issue]
Words to use: [word1], [word2], [word3]

**Drill 2 — Paraphrase:**
Most complex sentence → 3 versions:
- Simpler:
- More formal:
- Different structure:

**Drill 3 — Paragraph ({pub_style}):**
5-6 sentences: 4 vocab + 1 transition + 1 formula
"""


def prompt_exam(text):
    return f"""
{build_system_header()}
TEXT: \"\"\"{text}\"\"\"

# 🏆 COMPETITIVE EXAM INTELLIGENCE

## BCS Previous Questions (Real)
| Word/Concept | BCS | Year | Question | Options | Answer | Explanation |
|---|---|---|---|---|---|---|

## High Frequency Word Alert
| Word | 🔴🟡🟢 | বাংলা | Why High Frequency | Predicted Exam |
|---|---|---|---|---|

## Predicted BCS MCQs (5)

**Q1.** [question]
A) &nbsp; B) &nbsp; C) &nbsp; D)
✅ **[X]** — [Bengali + English explanation]

**Q2.** [question]
A) &nbsp; B) &nbsp; C) &nbsp; D)
✅ **[X]** — [explanation]

**Q3.** [question]
A) &nbsp; B) &nbsp; C) &nbsp; D)
✅ **[X]** — [explanation]

**Q4.** [question]
A) &nbsp; B) &nbsp; C) &nbsp; D)
✅ **[X]** — [explanation]

**Q5.** [question]
A) &nbsp; B) &nbsp; C) &nbsp; D)
✅ **[X]** — [explanation]

## Bank Recruitment (3)
[Q + options + answer + explanation]

## IELTS / GRE (3)
[Q + answer]

## BCS Written / Viva (3)
[Open Q + model answers — Bengali + English]

## GK Facts for Exams
| Fact | Appeared In | Year | Format |
|---|---|---|---|
"""


def prompt_mistakes(text):
    return f"""
{build_system_header()}
TEXT: \"\"\"{text}\"\"\"

# ❌ BENGALI SPEAKER MISTAKE RADAR

## Error Table
| ❌ What Bangladeshis Write | ✅ Correct | Error Type | Rule | বাংলা ব্যাখ্যা | Fix |
|---|---|---|---|---|---|

## Top 3 Mother Tongue Interference Errors

### MTI Error 1: [Name]
**Why it happens:** [How Bengali causes this]
**বাংলা:** [explanation]
❌ [wrong] → ✅ [correct]
**Rule:** [clear English rule]
**Trick:** [memory trick]

### MTI Error 2: [Name]
[Same]

### MTI Error 3: [Name]
[Same]

## Punctuation Traps
| ❌ | ✅ | Rule |
|---|---|---|

## Register Errors
[Informal where formal needed — specific to this text]
"""


def prompt_revision(text):
    return f"""
{build_system_header()}
TEXT: \"\"\"{text}\"\"\"

# 📸 RAPID REVISION CARD + POWER LINES

## ⭐ Power Lines (4-5 most important)

| Line (exact) | কেন গুরুত্বপূর্ণ | Why It Matters | Reuse In |
|---|---|---|---|

## Core Message
**EN:** [The real argument — 2 sentences]
**বাংলা:** [Same]

## Revision Card
╔══════════════════════════════════════════════════════╗
║ 📌 TOPIC: [one line] ║
╠══════════════════════════════════════════════════════╣
║ 🔑 TOP 5 WORDS: ║
║ 1. [word] = [Bengali] | Root: [root] ║
║ 2. [word] = [Bengali] | Root: [root] ║
║ 3. [word] = [Bengali] | Root: [root] ║
║ 4. [word] = [Bengali] | Root: [root] ║
║ 5. [word] = [Bengali] | Root: [root] ║
╠══════════════════════════════════════════════════════╣
║ 🏛️ GRAMMAR RULE: [one key rule] ║
║ 📅 HISTORY FACT: [event + year] ║
║ 🇧🇩 BD LINK: [specific Bangladesh fact] ║
║ 🏆 BCS LINK: [exam + year + question] ║
║ ✍️ FORMULA: [one reusable template] ║
╚══════════════════════════════════════════════════════╝

text


## 5-Minute Study Plan
1. [Most important vocabulary fact]
2. [Most important grammar point]
3. [Most important historical fact]
4. [Most likely exam question]
5. [The one writing formula to remember]
"""


SECTION_PROMPTS = {
    "sentences":    prompt_sentences,
    "vocabulary":   prompt_vocabulary,
    "context":      prompt_context,
    "grammar":      prompt_grammar,
    "collocations": prompt_collocations,
    "formulas":     prompt_formulas,
    "exam":         prompt_exam,
    "mistakes":     prompt_mistakes,
    "revision":     prompt_revision,
}


# ══════════════════════════════════════════
#  INPUT SECTION
# ══════════════════════════════════════════
st.markdown("## 📥 Input")

input_mode = st.radio(
    "", ["📋 Paste Text", "🔗 URL / Link"],
    horizontal=True, key="input_mode_radio"
)

article_text = ""

# ── URL MODE ──
if input_mode == "🔗 URL / Link":
    st.markdown(
        '<div class="strip-blue">🔗 যেকোনো news website-এর link দিন — article automatically extract হবে</div>',
        unsafe_allow_html=True
    )

    url_input = st.text_input(
        "", placeholder="https://www.thedailystar.net/... or https://www.bbc.com/...",
        key="url_input"
    )

    if st.button("🌐 Fetch Article", type="primary", key="fetch_btn"):
        if url_input.strip():
            with st.spinner("🌐 Article fetch করা হচ্ছে..."):
                title, source, text, error = extract_article_from_url(url_input.strip())

            if error:
                st.error(error)
                st.markdown(
                    '<div class="strip-amber">💡 Fetch না হলে: manually copy → Paste Text mode</div>',
                    unsafe_allow_html=True
                )
            else:
                st.session_state.current_text = text
                st.session_state.fetched_title = title
                st.session_state.fetched_source = source
                st.session_state.analysis_done = False
                st.session_state.results = {}
                st.success("✅ Article fetched!")
                st.rerun()

    if st.session_state.current_text and st.session_state.fetched_source:
        st.markdown(
            f'<span class="source-badge">🌐 {st.session_state.fetched_source}</span>',
            unsafe_allow_html=True
        )
        with st.expander("📄 Fetched Article Preview", expanded=True):
            if st.session_state.fetched_title:
                st.markdown(f"### {st.session_state.fetched_title}")
            st.markdown(
                f'<div class="article-preview">{st.session_state.current_text}</div>',
                unsafe_allow_html=True
            )
            st.caption(f"📊 {len(st.session_state.current_text.split())} words")

        with st.expander("✏️ Edit Extracted Text", expanded=False):
            edited = st.text_area(
                "Edit if needed:",
                value=st.session_state.current_text,
                height=300, key="url_edit"
            )
            if st.button("💾 Use Edited Version", key="use_edited"):
                st.session_state.current_text = edited
                st.session_state.results = {}
                st.session_state.analysis_done = False
                st.success("✅ Updated!")

    article_text = st.session_state.current_text

# ── PASTE MODE ──
else:
    article_text = st.text_area(
        "", height=220, key="paste_text",
        placeholder="Paste any English newspaper article, editorial, legal text, or academic passage here..."
    )
    if article_text.strip():
        st.session_state.current_text = article_text.strip()
        st.session_state.fetched_title = ""
        st.session_state.fetched_source = ""

# ══════════════════════════════════════════
#  ANALYZE BUTTON
# ══════════════════════════════════════════
st.divider()

col1, col2 = st.columns([2, 8])
with col1:
    analyze_btn = st.button(
        "🚀 Analyze All Sections",
        type="primary",
        use_container_width=True
    )
with col2:
    if st.session_state.analysis_done:
        if st.button("🔄 Re-analyze", use_container_width=True):
            st.session_state.cache = {}
            st.session_state.results = {}
            st.session_state.analysis_done = False
            st.rerun()

if analyze_btn:
    text_to_analyze = st.session_state.current_text.strip()

    if not text_to_analyze:
        st.warning("⚠️ Article paste করুন অথবা URL fetch করুন।")
    elif not api_key:
        st.warning("⚠️ API Key দিন — sidebar-এ।")
    elif (st.session_state.current_text == text_to_analyze
          and st.session_state.analysis_done):
        st.info("✅ Already analyzed! নিচে results দেখুন।")
    else:
        st.markdown('<div class="progress-card">', unsafe_allow_html=True)
        st.markdown(f"#### ⏳ Generating {len(SECTIONS)} sections...")
        progress_bar = st.progress(0)
        status_text = st.empty()

        st.session_state.results = {}
        st.session_state.analysis_done = False

        for i, section in enumerate(SECTIONS):
            label = SECTION_LABELS[section]
            status_text.markdown(
                f"🔄 **{label}** চলছে... ({i+1}/{len(SECTIONS)})"
            )
            progress_bar.progress(i / len(SECTIONS))

            ck = f"{section}_{hash(text_to_analyze)}"
            result = call_ai(
                SECTION_PROMPTS[section](text_to_analyze),
                cache_key=ck
            )
            st.session_state.results[section] = result or "❌ Generation failed."
            progress_bar.progress((i + 1) / len(SECTIONS))

        status_text.markdown("✅ **সব sections ready!**")
        st.session_state.analysis_done = True
        st.markdown('</div>', unsafe_allow_html=True)
        st.rerun()

# ══════════════════════════════════════════
#  RESULTS
# ══════════════════════════════════════════
if st.session_state.analysis_done and st.session_state.results:
    st.divider()

    if st.session_state.fetched_title:
        st.markdown(
            f'<span class="source-badge">🌐 {st.session_state.fetched_source}</span>',
            unsafe_allow_html=True
        )
        st.markdown(f"### 📰 {st.session_state.fetched_title}")

    st.markdown(
        '<div class="strip-green">✅ সব sections ready — tab-এ click করুন</div>',
        unsafe_allow_html=True
    )

    tab_labels = [SECTION_LABELS[s] for s in SECTIONS]
    tabs = st.tabs(tab_labels)

    for tab, section in zip(tabs, SECTIONS):
        with tab:
            result = st.session_state.results.get(section, "")
            show_result(result, filename_prefix=section)

elif not st.session_state.analysis_done:
    st.markdown("""
    <div style='text-align:center; padding:3rem; color:#999;'>
        <div style='font-size:3rem;'>📰</div>
        <p style='font-size:1.1rem; margin-top:1rem;'>
            Article paste করুন বা URL দিন → Analyze করুন
        </p>
        <p style='font-size:0.88rem;'>
            Sentences · Vocabulary · Context · Grammar ·
            Collocations · Formulas · Exam · Mistakes · Revision
        </p>
    </div>
    """, unsafe_allow_html=True)

# ══════════════════════════════════════════
#  EXTRA TOOLS
# ══════════════════════════════════════════
st.divider()
with st.expander("🛠️ Extra Tools", expanded=False):
    tool_tabs = st.tabs([
        "🔀 Translate", "📝 Error Fix", "✍️ Writing Lab",
        "🔄 Paraphrase", "📰 Headlines", "🧠 Vocab Quiz",
        "⚖️ Compare", "📓 Notes", "📚 Word Bank",
    ])

    with tool_tabs[0]:
        direction = st.radio("", ["Bengali → English", "English → Bengali"],
                             horizontal=True, key="tr_dir")
        t_text = st.text_area("", height=140, key="tr_text",
                              placeholder="Text to translate...")
        if st.button("🔀 Translate", type="primary", key="tr_btn"):
            if t_text.strip():
                if direction == "Bengali → English":
                    p = f"""{build_system_header()}
Bengali: \"\"\"{t_text}\"\"\"
## Translation Lab
### 1. Literal Version
[Direct] | বাংলা নোট: [how done]
### 2. {pub_style} Version
[Polished] | Why better: [...] | কেন ভালো: [...]
### 3. Step-by-Step
| Step | Action | Result |
|---|---|---|
| 1 | Core meaning | |
| 2 | Structure | |
| 3 | Vocabulary upgrade | |
| 4 | Polish | |
### 4. Three Alternatives
1. Simple: 2. Standard: 3. {pub_style} Premium:
### 5. Bengali Speaker Traps
| ❌ | ✅ | Why | Rule |
|---|---|---|---|
### 6. Key Vocabulary
| Word | বাংলা | Definition | Root | Exam |
|---|---|---|---|---|"""
                else:
                    p = f"""{build_system_header()}
English: \"\"\"{t_text}\"\"\"
## Translation (EN→BN)
### 1. Standard Bengali [Natural, fluent]
### 2. Journalistic Bengali [Newspaper quality]
### 3. Word Breakdown
| English | বাংলা | Note |
|---|---|---|
### 4. Structure Comparison [diagram]
### 5. Exam Vocabulary
| Word | বাংলা | Synonym | Antonym | BCS |
|---|---|---|---|---|"""
                with st.spinner("Translating..."):
                    res = call_ai(p)
                if res:
                    show_result(res, "translation")

    with tool_tabs[1]:
        e_text = st.text_area("", height=180, key="err_text",
                              placeholder="Your English writing here...")
        if st.button("🔍 Correct", type="primary", key="err_btn"):
            if e_text.strip():
                p = f"""{build_system_header()}
Text: \"\"\"{e_text}\"\"\"
## Error Analysis
### Score: [X/10] — [Bengali + English]
### Error Table
| # | ❌ Original | ✅ Correct | Type | Rule | বাংলা |
|---|---|---|---|---|---|
### Corrected Text
> [Full polished version]
### Scorecard
| Category | /10 | Note |
|---|---|---|
| Grammar | | |
| Vocabulary | | |
| Style | | |
| Coherence | | |
### Top 3 Patterns to Fix
### BCS Connection"""
                with st.spinner("Analyzing..."):
                    res = call_ai(p)
                if res:
                    show_result(res, "error_fix")

    with tool_tabs[2]:
        wl_prompts = [
            "Impact of AI on Bangladesh's job market (5-6 sentences)",
            "News lead: natural disaster in South Asia",
            "Editorial: education reform in Bangladesh",
            "Press freedom and democracy",
            "Climate change and coastal Bangladesh",
            "Global energy crisis and developing nations",
            "Constitutional rights and digital surveillance",
        ]
        chosen = st.selectbox("Guided prompt:", wl_prompts, key="wl_sel")
        st.info(f"📝 {chosen}")
        w_text = st.text_area("Your writing:", height=180, key="wl_text")
        if st.button("📊 Get Feedback", type="primary", key="wl_btn"):
            if w_text.strip():
                p = f"""{build_system_header()}
Student writing: \"\"\"{w_text}\"\"\"
## Writing Evaluation
### Score: [X/10] [Bengali + English]
### ✅ Strengths [cite actual lines] | বাংলা: [...]
### ❌ Issues
| Problem | Example | Fix | Rule |
|---|---|---|---|
### Professional Rewrite [{pub_style}]
### Vocabulary Upgrades
| Used | Better | কেন ভালো |
|---|---|---|
### Priority Improvement (1→5)
### Next Challenge"""
                with st.spinner("Evaluating..."):
                    res = call_ai(p)
                if res:
                    show_result(res, "writing_feedback")

    with tool_tabs[3]:
        p_text = st.text_area("", height=140, key="para_text",
                              placeholder="Sentence or paragraph...")
        if st.button("🔄 Generate 4 Versions", type="primary", key="para_btn"):
            if p_text.strip():
                p = f"""{build_system_header()}
Original: \"\"\"{p_text}\"\"\"
## 4 Paraphrases
### 1. Academic/IELTS [Rewrite] | Techniques: [...]
### 2. {pub_style} [Rewrite] | Techniques: [...]
### 3. Simple/Clear [Rewrite] | Techniques: [...]
### 4. GRE Sophisticated [Rewrite] | Techniques: [...]
## Technique Table
| Technique | Used In | Bengali | English |
|---|---|---|---|
## Practice: 1.[...] 2.[...]"""
                with st.spinner("Creating..."):
                    res = call_ai(p)
                if res:
                    show_result(res, "paraphrase")

    with tool_tabs[4]:
        h_text = st.text_area("", height=120, key="hl_text",
                              placeholder="Topic or article summary...")
        if st.button("📰 Generate Headlines", type="primary", key="hl_btn"):
            if h_text.strip():
                p = f"""{build_system_header()}
Topic: \"\"\"{h_text}\"\"\"
## 12 Headlines
### Hard News (4): 1.[→ Technique] 2. 3. 4.
### Feature (3): 1. 2. 3.
### Opinion/Editorial (3): 1. 2. 3.
### Magazine (2): 1. 2.
## 5 Golden Rules
| Rule | Bengali | Example |
|---|---|---|
## Practice: 1.[...] 2.[...] 3.[...]"""
                with st.spinner("Crafting..."):
                    res = call_ai(p)
                if res:
                    show_result(res, "headlines")

    with tool_tabs[5]:
        q_words = st.text_input("", key="quiz_words",
                                placeholder="Words: resilience, curtailment, insolvency...")
        if st.button("🧠 Generate Quiz", type="primary", key="quiz_btn"):
            if q_words.strip():
                p = f"""{build_system_header()}
Words: {q_words}
## Vocabulary Quiz
### A — Fill in Blanks (5) [{pub_style} sentences + 4 options]
### B — Synonym (5)
### C — Root Word (5)
| Word | Root | Meaning | Family |
|---|---|---|---|
### D — BCS/Bank MCQ (5)
### E — Use in Sentence (3)
### ✅ Answer Key [Bengali + English]"""
                with st.spinner("Building..."):
                    res = call_ai(p)
                if res:
                    show_result(res, "vocab_quiz")

    with tool_tabs[6]:
        cc1, cc2 = st.columns(2)
        with cc1:
            st.caption("Text 1")
            cmp1 = st.text_area("", height=180, key="cmp1")
        with cc2:
            st.caption("Text 2")
            cmp2 = st.text_area("", height=180, key="cmp2")
        if st.button("⚖️ Compare", type="primary", key="cmp_btn"):
            if cmp1.strip() and cmp2.strip():
                p = f"""{build_system_header()}
Text 1: \"\"\"{cmp1}\"\"\"
Text 2: \"\"\"{cmp2}\"\"\"
## Comparison
### Side-by-Side
| Feature | Text 1 | Text 2 |
|---|---|---|
| Avg length | | |
| Complexity | | |
| Voice | | |
| Vocabulary | | |
| Tone | | |
### Strengths & Gaps
| | T1 ✅ | T1 ❌ | T2 ✅ | T2 ❌ |
|---|---|---|---|---|
### Verdict
| Category | Winner | T1/10 | T2/10 |
|---|---|---|---|
### Learning Points"""
                with st.spinner("Comparing..."):
                    res = call_ai(p)
                if res:
                    show_result(res, "compare")

    with tool_tabs[7]:
        n_text = st.text_area("", height=200, key="note_text",
                              placeholder="Paste text for standalone notes...")
        if st.button("📓 Generate Notes", type="primary", key="note_btn"):
            if n_text.strip():
                p = f"""{build_system_header()}
TEXT: \"\"\"{n_text}\"\"\"
# MASTER STUDY NOTES
## 1. Concept Map [Central Theme EN + বাংলা | 3 Key Arguments]
## 2. Context [Narrative EN + Bengali | 3 Famous Events story-format | BD Angle]
## 3. Vocabulary (12+) [Deep-dive format]
## 4. Exam Focus [High frequency table + 5 predicted MCQs]
## 5. Writing Formulas (5)
## 6. Revision Card [Screenshot-ready]"""
                ck = f"notes_{hash(n_text)}"
                with st.spinner("Building notes..."):
                    res = call_ai(p, cache_key=ck)
                if res:
                    show_result(res, "standalone_notes")
                    st.session_state.notes.append({
                        "time": datetime.now().strftime("%Y-%m-%d %H:%M"),
                        "preview": n_text[:70] + "...",
                        "content": res
                    })

        if st.session_state.notes:
            st.divider()
            st.markdown(f"**Saved Notes ({len(st.session_state.notes)})**")
            for note in reversed(st.session_state.notes):
                with st.expander(f"📝 {note['time']} — {note['preview']}"):
                    st.markdown(note['content'])

    with tool_tabs[8]:
        with st.form("wb_form"):
            wc1, wc2, wc3 = st.columns([2, 3, 1])
            with wc1:
                nw = st.text_input("Word", placeholder="resilience")
            with wc2:
                nm = st.text_input("Meaning",
                                   placeholder="স্থিতিস্থাপকতা | capacity to recover")
            with wc3:
                st.write("")
                st.write("")
                wb_add = st.form_submit_button("➕ Add")
            if wb_add and nw.strip():
                st.session_state.saved_vocab.append({
                    "word": nw.strip(),
                    "meaning": nm.strip(),
                    "added": datetime.now().strftime("%Y-%m-%d"),
                })
                st.success(f"✅ '{nw}' added!")
                st.rerun()

        if st.session_state.saved_vocab:
            st.divider()
            wc1, wc2, wc3 = st.columns(3)
            wc1.metric("Total", len(st.session_state.saved_vocab))
            today = datetime.now().strftime("%Y-%m-%d")
            wc2.metric("Today", sum(
                1 for w in st.session_state.saved_vocab if w["added"] == today
            ))
            wc3.metric("For Quiz", len(st.session_state.saved_vocab))

            wb_search = st.text_input("🔍 Search", key="wb_search")
            filtered = [
                w for w in st.session_state.saved_vocab
                if not wb_search
                or wb_search.lower() in w["word"].lower()
                or wb_search.lower() in w["meaning"].lower()
            ]

            for item in filtered:
                wc1, wc2, wc3, wc4 = st.columns([2, 4, 1, 1])
                wc1.markdown(f"**{item['word']}**")
                wc2.write(item["meaning"] or "—")
                wc3.caption(item["added"])
                idx = st.session_state.saved_vocab.index(item)
                if wc4.button("❌", key=f"del_{idx}_{item['word']}"):
                    st.session_state.saved_vocab.pop(idx)
                    st.rerun()

            st.divider()
            qc1, qc2 = st.columns(2)
            with qc1:
                if len(st.session_state.saved_vocab) >= 3:
                    if st.button("🧠 Quiz Me!", type="primary",
                                 use_container_width=True, key="wb_quiz"):
                        wstr = ", ".join(
                            w["word"] for w in st.session_state.saved_vocab[-15:]
                        )
                        with st.spinner("Building quiz..."):
                            res = call_ai(
                                f"{build_system_header()}\nWords: {wstr}\n"
                                "Full quiz: BCS MCQ + synonyms + fill blanks + root analysis"
                            )
                        if res:
                            show_result(res, "wb_quiz")
            with qc2:
                export = "# Word Bank\n\n| Word | Meaning | Added |\n|---|---|---|\n"
                for w in st.session_state.saved_vocab:
                    export += f"| {w['word']} | {w['meaning']} | {w['added']} |\n"
                st.download_button(
                    "📥 Export", export, "word_bank.md", use_container_width=True
                )

# ── Footer ──
st.markdown(
    "<p style='text-align:center; color:#bbb; font-size:0.82rem; padding:1rem 0 0;'>"
    "The Analyst · BCS · GRE · IELTS · Law · Journalism"
    "</p>",
    unsafe_allow_html=True
)