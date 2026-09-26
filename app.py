import streamlit as st
import google.generativeai as genai
from datetime import datetime
import threading

st.set_page_config(
    page_title="The Analyst",
    page_icon="📰",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Playfair+Display:wght@700&family=Inter:wght@400;500;600&display=swap');

* { font-family: 'Inter', sans-serif; }
.block-container { padding: 2rem 3rem; max-width: 1200px; }
h1, h2, h3 { font-family: 'Playfair Display', serif; color: #1a1a2e; }

section[data-testid="stSidebar"] { background: #1a1a2e; }
section[data-testid="stSidebar"] * { color: white !important; }
section[data-testid="stSidebar"] .stSelectbox > div > div,
section[data-testid="stSidebar"] .stTextInput > div > div {
    background: #16213e; border: 1px solid #0f3460;
}

.stTabs [data-baseweb="tab-list"] {
    background: #f8f9fa; border-radius: 12px; padding: 4px; gap: 2px;
}
.stTabs [data-baseweb="tab"] {
    border-radius: 8px; padding: 8px 18px;
    font-weight: 600; font-size: 0.85rem; color: #666;
}
.stTabs [aria-selected="true"] {
    background: #1a1a2e !important; color: white !important;
}

.stButton > button[kind="primary"] {
    background: linear-gradient(135deg, #1a1a2e, #16213e);
    color: white; border: none; border-radius: 8px;
    padding: 10px 28px; font-weight: 600; font-size: 0.95rem;
    transition: all 0.2s;
}
.stButton > button[kind="primary"]:hover {
    transform: translateY(-1px);
    box-shadow: 0 4px 12px rgba(26,26,46,0.3);
}

.stTextArea textarea {
    border: 1.5px solid #e0e0e0; border-radius: 10px;
    font-size: 0.95rem; line-height: 1.6;
}
.stTextArea textarea:focus { border-color: #1a1a2e; }

.result-wrap {
    background: #ffffff; border: 1px solid #e8e8e8;
    border-radius: 14px; padding: 2rem 2.5rem; margin-top: 1rem;
    box-shadow: 0 2px 20px rgba(0,0,0,0.06);
    line-height: 1.9; font-size: 0.97rem;
}

.tab-status-done {
    display: inline-block; background: #d1fae5;
    color: #065f46; padding: 2px 10px; border-radius: 20px;
    font-size: 0.78rem; font-weight: 600; margin-left: 8px;
}
.tab-status-loading {
    display: inline-block; background: #fef3c7;
    color: #92400e; padding: 2px 10px; border-radius: 20px;
    font-size: 0.78rem; font-weight: 600; margin-left: 8px;
}
.tab-status-wait {
    display: inline-block; background: #f1f5f9;
    color: #64748b; padding: 2px 10px; border-radius: 20px;
    font-size: 0.78rem; font-weight: 600; margin-left: 8px;
}

.progress-card {
    background: #f8faff; border: 1px solid #e0e7ff;
    border-radius: 12px; padding: 1.2rem 1.5rem; margin: 1rem 0;
}

.strip-blue {
    background: #eff6ff; border-left: 4px solid #2563eb;
    padding: 10px 16px; border-radius: 6px;
    margin-bottom: 1rem; font-size: 0.9rem; color: #1e3a8a;
}

div[data-testid="metric-container"] {
    background: #16213e; border-radius: 10px; padding: 12px;
}
div[data-testid="metric-container"] label { color: #94a3b8 !important; }
div[data-testid="metric-container"] div { color: white !important; }

.stDownloadButton > button {
    background: transparent; border: 1.5px solid #1a1a2e;
    color: #1a1a2e; border-radius: 8px; font-weight: 600;
}
.stDownloadButton > button:hover { background: #1a1a2e; color: white; }

table { width: 100%; border-collapse: collapse; font-size: 0.9rem; margin: 1rem 0; }
th { background: #1a1a2e; color: white; padding: 10px 14px; text-align: left; }
td { padding: 9px 14px; border-bottom: 1px solid #f0f0f0; }
tr:hover td { background: #f8f9ff; }
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div style='text-align:center; padding: 1.5rem 0 0.5rem;'>
  <h1 style='font-size:2.4rem; margin-bottom:0.2rem;'>📰 The Analyst</h1>
  <p style='color:#666; font-size:1rem; margin:0;'>
    Premium English Intelligence · BCS · GRE · IELTS · Law · Journalism
  </p>
</div>
<hr style='border:none; border-top:2px solid #e8e8e8; margin: 1rem 0 1.5rem;'>
""", unsafe_allow_html=True)

# ══════════════════════════════════════════
#  SESSION STATE
# ══════════════════════════════════════════
SECTIONS = [
    "sentences",
    "vocabulary",
    "context",
    "grammar",
    "collocations",
    "formulas",
    "exam",
    "mistakes",
    "revision",
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
    "results": {},        # section → result text
    "current_text": "",   # the article being analyzed
    "analysis_done": False,
    "generating": False,
}.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ══════════════════════════════════════════
#  SIDEBAR
# ══════════════════════════════════════════
with st.sidebar:
    st.markdown("## ⚙️ Control Panel")
    st.divider()

    api_key = st.text_input("🔑 API Key", type="password", placeholder="Gemini API key...")

    model_choice = st.selectbox("🤖 Model", [
        "gemini-3.5-flash-lite",
        "gemini-2.0-flash",
        "gemini-1.5-flash-8b",
        "gemini-1.5-flash",
        "gemini-1.5-pro",
    ], index=0)

    difficulty = st.select_slider(
        "📊 Level",
        ["Beginner", "Intermediate", "Advanced", "Expert"],
        value="Advanced"
    )

    pub_style = st.selectbox("🎯 Style", [
        "The Economist",
        "New York Times",
        "The Guardian",
        "BBC News",
        "Academic / IELTS",
        "Legal / Constitutional",
    ])

    analysis_type = st.selectbox("📋 Mode", [
        "General (News / Editorial)",
        "Law / Constitutional",
        "Economics / Business",
        "Political Science",
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
        st.success("Cleared!")
        st.rerun()


# ══════════════════════════════════════════
#  HELPERS
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
            st.markdown(result)  # ← সরাসরি markdown
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
| বাংলা অনুবাদ | [natural Bengali — precise, not word-for-word] |
| Clause Type | [Simple / Compound / Complex / Compound-Complex] |
| Clause Breakdown | [label each — Main, Subordinate, Relative, Noun, Adverbial] |
| Grammar Device | [Parallelism / Inversion / Fronting / Passive / Cleft / Ellipsis] |
| কেন এই গঠন? | [Bengali — why this structure serves the argument] |
| Why It Works | [English — journalistic/academic reason] |
| BCS / Exam Link | [if this grammar pattern has appeared in exams] |

---

(repeat for every sentence)

## Sentence Transformation Exercises
Five BCS/Bank style transforms from sentences in this text:
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
[All important words — minimum 12]

---

## Deep-Dive (every word)

#### 🔤 [WORD]
**[Bengali meaning] · [Concise English definition]**

| | |
|---|---|
| 🌱 Root | [root] → [language] → "[meaning]" |
| 📖 Etymology | [Brief, interesting origin story — 2 sentences] |
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

**🧠 Memory Hook (Bengali mnemonic):**
[Clever, unforgettable Bengali trick]

**📰 {pub_style} Sentence:**
> [Professional example]

**🏆 Exam Record:**
| Exam | Year | Question | Answer |
|---|---|---|---|

---
(repeat for every word)
"""


def prompt_context(text):
    return f"""
{build_system_header()}
TEXT: \"\"\"{text}\"\"\"

# 🌍 CONTEXT & HISTORICAL INTELLIGENCE

## What This Is Really About
**EN:** [2-3 sentences — the real issue beneath the surface]
**বাংলা:** [same in Bengali]

## The Immediate Context
[What happened / what crisis / what debate — narrative explanation]
বাংলা: [Bengali paragraph]

## Historical Timeline
| Year | Event | Where | Why It Matters |
|---|---|---|---|
[5-6 real, specific events directly related to THIS text's topic]

## Famous & Notorious Related Events
*(Tell the story — not just a bullet point)*

**[Event Name]** ([Year], [Place])
[4-5 sentences — what happened, why it was controversial/landmark, what changed because of it]
বাংলা: [Bengali version]

**[Event 2]**
[Same treatment]

**[Event 3]**
[Same treatment]

## 🇧🇩 Bangladesh Dimension
[Specific facts, laws, dates, figures, economic data]
বাংলা: [Bengali]

{"## ⚖️ Constitutional & Legal Map" if "Law" in analysis_type or "Constitutional" in analysis_type else ""}
{"**Bangladesh Constitution articles / amendments relevant here:**" if "Law" in analysis_type else ""}
{"[Specific articles + what they say + how they connect to this text]" if "Law" in analysis_type else ""}
{"**Landmark Cases:**" if "Law" in analysis_type else ""}
{"[Real cases — Bangladesh High Court / Supreme Court / international — with brief facts and rulings]" if "Law" in analysis_type else ""}

## 📆 On This Day ({datetime.now().strftime('%B %d')})
[Notable event on today's date related to this topic — if exists]
"""


def prompt_grammar(text):
    return f"""
{build_system_header()}
TEXT: \"\"\"{text}\"\"\"

# 🏛️ GRAMMAR LABORATORY

## Advanced Syntax Devices Found
| Device | Example from Text | কেন কার্যকর (Bengali) | Why Effective (English) | BCS Use |
|---|---|---|---|---|

## Clause Architecture Map
For each complex/compound sentence, diagram the clause structure:

**"[sentence]"**
```
Main Clause: [...]
  └─ Subordinate Clause ([type]): [...]
       └─ Relative Clause: [...]
```
বাংলা ব্যাখ্যা: [why this layering works]

## Special Grammar Points in This Text
[5-6 notable grammar features — passive constructions, subjunctive, ellipsis, etc.]
[Each with: Bengali explanation + English rule + BCS exam connection]

## Grammar Rules That Appear in BCS/Bank
| Rule Found in Text | BCS/Bank Frequency | Sample Past Question | Answer |
|---|---|---|---|

## Transformation Exercises (BCS/IELTS style)
**Exercise 1 — Voice:**
Original: [sentence from text]
Transform to [Active/Passive]: ✅ [answer]
বাংলা নিয়ম: [rule]

**Exercise 2 — Degree:**
Original: [sentence]
Transform: ✅ [answer]

**Exercise 3 — Conditional:**
Original: [sentence]
Transform: ✅ [answer]

**Exercise 4 — Narration:**
Original: [sentence]
Transform to Indirect: ✅ [answer]

**Exercise 5 — Simple ↔ Complex:**
Original: [sentence]
Transform: ✅ [answer]
"""


def prompt_collocations(text):
    return f"""
{build_system_header()}
TEXT: \"\"\"{text}\"\"\"

# 🔗 COLLOCATION & PHRASE INTELLIGENCE

## Collocations Found
| Expression | Type | বাংলা | English | Register | Better Alternatives |
|---|---|---|---|---|---|

## Deep Analysis — Top 5 Collocations
For each:
**[collocation]**
- বাংলা: [meaning]
- Why it collocates: [English explanation]
- Wrong version students write: ❌ [common mistake]
- Correct: ✅ [collocation]
- {pub_style} example: > [sentence]

## Idioms & Fixed Expressions
| Expression | বাংলা | English | Origin | Exam |
|---|---|---|---|---|

## Phrasal Verbs
| Verb | বাংলা | Formal Equivalent | Example | Exam |
|---|---|---|---|---|

## Transition & Cohesion Map
| Transition Used | Category | বাংলা | Level | Better Options |
|---|---|---|---|---|

**Reference Chains:**
[What does each pronoun/reference word in the text refer to?]
- "it" (line X) → refers to: [...]
- "they" (line X) → refers to: [...]
- "this" (line X) → refers to: [...]
"""


def prompt_formulas(text):
    return f"""
{build_system_header()}
TEXT: \"\"\"{text}\"\"\"

# ✍️ WRITING FORMULA LABORATORY

Extract 6 reusable writing patterns from this text:

---

### Formula 1: [Pattern Name]
**Template:**
```
[SUBJECT] + [VERB], [CONCESSIVE/CONDITIONAL], [MAIN ASSERTION].
```
**From text:** *"[exact sentence]"*
**New example:** [fresh sentence on different topic]
**কখন ব্যবহার (Bengali):** [when to use this]
**When to use (English):** [guidance]
**IELTS/BCS Bonus:** [how this pattern lifts your score]

---

### Formula 2: [Pattern Name]
[Same structure]

### Formula 3: [Pattern Name]
[Same]

### Formula 4: [Pattern Name]
[Same]

### Formula 5: [Pattern Name]
[Same]

### Formula 6: [Pattern Name]
[Same]

---

## Writing Drills

**Drill 1:** Use Formula 1 to write about: [related current topic]
Must use these 3 words from the text: [word1], [word2], [word3]

**Drill 2 — Paraphrase Challenge:**
Most complex sentence → 3 versions:
- Simpler:
- More formal:
- Different structure, same meaning:

**Drill 3 — Paragraph Build ({pub_style} tone):**
Write 5-6 sentences on [related topic]
Requirements: 4 vocab words + 1 transition + 1 formula
"""


def prompt_exam(text):
    return f"""
{build_system_header()}
TEXT: \"\"\"{text}\"\"\"

# 🏆 COMPETITIVE EXAM INTELLIGENCE

## BCS Previous Questions (Real — from this text's words/concepts)
| Word / Concept | BCS | Year | Exact Question | Options | Answer | Explanation |
|---|---|---|---|---|---|---|

## High Frequency Word Alert
| Word | 🔴🟡🟢 | বাংলা | Why High Frequency | Predicted Exam |
|---|---|---|---|---|

## Predicted BCS MCQs (5)
**Q1.** [question from vocabulary/grammar in this text]
A) &nbsp;&nbsp; B) &nbsp;&nbsp; C) &nbsp;&nbsp; D)
✅ **Answer:** [X] — [Bengali + English explanation]

**Q2.** [question]
A) B) C) D)
✅ **Answer:** [X] — [explanation]

**Q3.** [question]
A) B) C) D)
✅ **Answer:** [X] — [explanation]

**Q4.** [question]
A) B) C) D)
✅ **Answer:** [X] — [explanation]

**Q5.** [question]
A) B) C) D)
✅ **Answer:** [X] — [explanation]

## Bank Recruitment Style (3)
[Questions + full answers]

## IELTS / GRE Vocabulary Style (3)
[Questions + answers]

## BCS Written / Viva (3 questions)
[Open questions + model answers — Bengali + English]

## GK Facts from This Text for Exams
| Fact | Appeared In | Year | Question Format |
|---|---|---|---|
"""


def prompt_mistakes(text):
    return f"""
{build_system_header()}
TEXT: \"\"\"{text}\"\"\"

# ❌ BENGALI SPEAKER MISTAKE RADAR

## Error Table
| ❌ What Bangladeshis Write | ✅ Correct Form | Error Type | Rule (English) | বাংলা ব্যাখ্যা | Fix |
|---|---|---|---|---|---|
[6-8 specific errors a Bengali speaker makes with THIS type of text]

## Top 3 Mother Tongue Interference Errors
*(The deepest, most stubborn Bengali→English transfer problems)*

### MTI Error 1: [Name of the interference pattern]
**Why it happens:** [How Bengali grammar causes this English error]
বাংলা: [explanation]
❌ Example: [wrong]
✅ Correct: [right]
**The Rule:** [clear English grammar rule]
**Remember with:** [memory trick]

### MTI Error 2: [Name]
[Same structure]

### MTI Error 3: [Name]
[Same structure]

## Punctuation Traps
| ❌ Common Error | ✅ Correct | Rule |
|---|---|---|

## Register Errors
[When students use informal words where formal ones are needed — specific to this text's topic]
"""


def prompt_revision(text):
    return f"""
{build_system_header()}
TEXT: \"\"\"{text}\"\"\"

# 📸 RAPID REVISION CARD + POWER LINES

## ⭐ Power Lines
*(The 4-5 most important sentences — worth memorizing)*

| Line (exact) | কেন গুরুত্বপূর্ণ (Bengali) | Why It Matters (English) | Reuse In |
|---|---|---|---|

## Core Message
**EN:** [The real argument in 2 sentences]
**বাংলা:** [Same]

## Revision Card
```
╔══════════════════════════════════════════════════════╗
║  📌 TOPIC: [one line]                                ║
╠══════════════════════════════════════════════════════╣
║  🔑 TOP 5 WORDS:                                     ║
║   1. [word] = [Bengali] | Root: [root]               ║
║   2. [word] = [Bengali] | Root: [root]               ║
║   3. [word] = [Bengali] | Root: [root]               ║
║   4. [word] = [Bengali] | Root: [root]               ║
║   5. [word] = [Bengali] | Root: [root]               ║
╠══════════════════════════════════════════════════════╣
║  🏛️ GRAMMAR RULE: [one key rule]                     ║
║  📅 HISTORY FACT: [event + year]                     ║
║  🇧🇩 BD LINK: [specific Bangladesh fact]             ║
║  🏆 BCS LINK: [exam + year + question]               ║
║  ✍️ FORMULA: [one reusable template]                 ║
╚══════════════════════════════════════════════════════╝
```

## 5-Minute Study Plan
If you only have 5 minutes before the exam, read this:
[Compact, dense, exam-focused summary — Bengali + English]
1. [Most important vocabulary fact]
2. [Most important grammar point]
3. [Most important historical fact]
4. [Most likely exam question]
5. [The one writing formula to remember]
"""


# ══════════════════════════════════════════
#  SECTION → PROMPT MAPPING
# ══════════════════════════════════════════
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
#  MAIN ANALYSIS ENGINE
#  Generates all sections sequentially
#  with live progress updates
# ══════════════════════════════════════════
def run_full_analysis(text):
    """Generate all sections one by one, storing results as they complete."""
    st.session_state.results = {}
    st.session_state.analysis_done = False
    st.session_state.current_text = text
    st.session_state.generating = True

    for section in SECTIONS:
        ck = f"{section}_{hash(text)}"
        prompt_fn = SECTION_PROMPTS[section]
        result = call_ai(prompt_fn(text), cache_key=ck)
        st.session_state.results[section] = result if result else "❌ Generation failed."

    st.session_state.analysis_done = True
    st.session_state.generating = False


# ══════════════════════════════════════════
#  INPUT AREA — TOP OF PAGE
# ══════════════════════════════════════════
st.markdown("### 📋 Paste Your Article")
article_text = st.text_area(
    "",
    height=200,
    key="main_article",
    placeholder="Paste any English newspaper article, editorial, legal text, or academic passage here..."
)

col1, col2, col3 = st.columns([2, 2, 6])
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

# ── Trigger analysis ──
if analyze_btn:
    if not article_text.strip():
        st.warning("⚠️ Please paste an article first.")
    elif not api_key:
        st.warning("⚠️ API Key দিন — sidebar-এ।")
    else:
        # Check if same text already analyzed
        if (st.session_state.current_text == article_text.strip()
                and st.session_state.analysis_done):
            st.info("✅ Already analyzed! Scroll down to see results.")
        else:
            # Progress display
            st.markdown('<div class="progress-card">', unsafe_allow_html=True)
            st.markdown("#### ⏳ Generating all sections...")
            progress_bar = st.progress(0)
            status_text = st.empty()

            results_temp = {}
            text = article_text.strip()
            st.session_state.results = {}
            st.session_state.analysis_done = False
            st.session_state.current_text = text

            for i, section in enumerate(SECTIONS):
                label = SECTION_LABELS[section]
                status_text.markdown(f"🔄 Generating **{label}**... ({i+1}/{len(SECTIONS)})")
                progress_bar.progress((i) / len(SECTIONS))

                ck = f"{section}_{hash(text)}"
                prompt_fn = SECTION_PROMPTS[section]
                result = call_ai(prompt_fn(text), cache_key=ck)
                st.session_state.results[section] = (
                    result if result else "❌ Generation failed."
                )
                progress_bar.progress((i + 1) / len(SECTIONS))

            status_text.markdown("✅ **All sections ready!** Scroll down to explore.")
            st.session_state.analysis_done = True
            st.markdown('</div>', unsafe_allow_html=True)
            st.rerun()

# ══════════════════════════════════════════
#  RESULTS DISPLAY — TABS
# ══════════════════════════════════════════
if st.session_state.analysis_done and st.session_state.results:
    st.divider()
    st.markdown("### 📊 Analysis Results")
    st.markdown(
        '<div class="strip-blue">✅ সব sections ready — যেকোনো tab-এ click করুন, result দেখুন।</div>',
        unsafe_allow_html=True
    )

    # Build tab labels with status
    tab_labels = [SECTION_LABELS[s] for s in SECTIONS]

    tabs = st.tabs(tab_labels)

    for i, (tab, section) in enumerate(zip(tabs, SECTIONS)):
        with tab:
            result = st.session_state.results.get(section, "")
            if result:
                show_result(result, filename_prefix=section)
            else:
                st.info("⏳ Not generated yet.")

elif not st.session_state.analysis_done:
    st.markdown("""
    <div style='text-align:center; padding:3rem; color:#999;'>
        <div style='font-size:3rem;'>📰</div>
        <p style='font-size:1.1rem; margin-top:1rem;'>
            Paste an article above and click <strong>Analyze All Sections</strong>
        </p>
        <p style='font-size:0.9rem;'>
            All 9 sections will be generated at once —
            Sentences · Vocabulary · Context · Grammar ·
            Collocations · Formulas · Exam · Mistakes · Revision
        </p>
    </div>
    """, unsafe_allow_html=True)

# ══════════════════════════════════════════
#  EXTRA TOOLS — COLLAPSIBLE BOTTOM
# ══════════════════════════════════════════
st.divider()
with st.expander("🛠️ Extra Tools", expanded=False):
    tool_tabs = st.tabs([
        "🔀 Translate",
        "📝 Error Fix",
        "✍️ Writing Lab",
        "🔄 Paraphrase",
        "📰 Headlines",
        "🧠 Vocab Quiz",
        "⚖️ Compare",
        "📓 Standalone Notes",
        "📚 Word Bank",
    ])

    # ── Translate ──
    with tool_tabs[0]:
        direction = st.radio("", ["Bengali → English", "English → Bengali"], horizontal=True, key="tr_dir")
        t_text = st.text_area("", height=140, key="tr_text",
                              placeholder="Text to translate...")
        if st.button("🔀 Translate", type="primary", key="tr_btn"):
            if t_text.strip():
                def _translation_prompt(txt, dir_):
                    if dir_ == "Bengali → English":
                        return f"""{build_system_header()}
Bengali: \"\"\"{txt}\"\"\"
## Translation Lab
### 1. Literal Version
[Direct] | বাংলা নোট: [how done]
### 2. {pub_style} Version
[Polished] | Why better: [...] | কেন ভালো: [...]
### 3. Step-by-Step
| Step | Action | Result |
|---|---|---|
### 4. Three Alternatives (Easy→Advanced)
1. Simple: 2. Standard: 3. Premium:
### 5. Bengali Speaker Traps
| ❌ | ✅ | Why | Rule |
|---|---|---|---|
### 6. Key Vocabulary
| Word | বাংলা | Definition | Root | Exam |
|---|---|---|---|---|"""
                    else:
                        return f"""{build_system_header()}
English: \"\"\"{txt}\"\"\"
## Translation Lab (EN→BN)
### 1. Standard Bengali
[Natural, fluent]
### 2. Journalistic Bengali
[Newspaper quality]
### 3. Word Breakdown
| English | বাংলা | Note |
|---|---|---|
### 4. Structure Comparison
[Diagram showing difference]
### 5. Exam Vocabulary
| Word | বাংলা | Synonym | Antonym | BCS |
|---|---|---|---|---|"""

                with st.spinner("Translating..."):
                    res = call_ai(_translation_prompt(t_text, direction))
                if res:
                    show_result(res, "translation")

    # ── Error Fix ──
    with tool_tabs[1]:
        e_text = st.text_area("", height=180, key="err_text",
                              placeholder="Your English writing here...")
        if st.button("🔍 Correct", type="primary", key="err_btn"):
            if e_text.strip():
                p = f"""{build_system_header()}
Text: \"\"\"{e_text}\"\"\"
## Error Analysis
### Score: [X/10]
[Bengali + English assessment]
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
### BCS Connection
"""
                with st.spinner("Analyzing..."):
                    res = call_ai(p)
                if res:
                    show_result(res, "error_fix")

    # ── Writing Lab ──
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
### Score: [X/10]
[Bengali + English]
### ✅ Strengths
[Specific — cite actual lines]
বাংলা: [...]
### ❌ Issues
| Problem | Example | Fix | Rule |
|---|---|---|---|
### Professional Rewrite
[Full {pub_style} version]
### Vocabulary Upgrades
| Used | Better | কেন ভালো |
|---|---|---|
### Priority Improvement (1-5)
### Next Challenge
"""
                with st.spinner("Evaluating..."):
                    res = call_ai(p)
                if res:
                    show_result(res, "writing_feedback")

    # ── Paraphrase ──
    with tool_tabs[3]:
        p_text = st.text_area("", height=140, key="para_text",
                              placeholder="Sentence or paragraph to paraphrase...")
        if st.button("🔄 Generate 4 Versions", type="primary", key="para_btn"):
            if p_text.strip():
                p = f"""{build_system_header()}
Original: \"\"\"{p_text}\"\"\"
## 4 Paraphrases
### 1. Academic/IELTS
[Rewrite] | Techniques: [...]
### 2. {pub_style}
[Rewrite] | Techniques: [...]
### 3. Simple/Clear
[Rewrite] | Techniques: [...]
### 4. GRE-level Sophisticated
[Rewrite] | Techniques: [...]
## Technique Table
| Technique | Used In | Bengali | English |
|---|---|---|---|
## Practice
Paraphrase these independently:
1. [...] 2. [...]"""
                with st.spinner("Creating..."):
                    res = call_ai(p)
                if res:
                    show_result(res, "paraphrase")

    # ── Headlines ──
    with tool_tabs[4]:
        h_text = st.text_area("", height=120, key="hl_text",
                              placeholder="Topic or article summary...")
        if st.button("📰 Generate Headlines", type="primary", key="hl_btn"):
            if h_text.strip():
                p = f"""{build_system_header()}
Topic: \"\"\"{h_text}\"\"\"
## 12 Headlines
### Hard News (4)
1. [...] → Technique: [Bengali + English]
2. 3. 4.
### Feature (3)
1. 2. 3.
### Opinion/Editorial (3)
1. 2. 3.
### Magazine/Digital (2)
1. 2.
## 5 Golden Rules
| Rule | Bengali | Example |
|---|---|---|
## Practice Topics
Write headlines for: 1. [...] 2. [...] 3. [...]"""
                with st.spinner("Crafting..."):
                    res = call_ai(p)
                if res:
                    show_result(res, "headlines")

    # ── Vocab Quiz ──
    with tool_tabs[5]:
        q_words = st.text_input("", key="quiz_words",
                                placeholder="Words: resilience, curtailment, insolvency...")
        if st.button("🧠 Generate Quiz", type="primary", key="quiz_btn"):
            if q_words.strip():
                p = f"""{build_system_header()}
Words: {q_words}
## Vocabulary Quiz
### A — Fill in Blanks (5)
[{pub_style}-style sentences + 4 options]
### B — Synonym Challenge (5)
### C — Root Word Analysis (5)
| Word | Root | Meaning | Family |
|---|---|---|---|
### D — BCS/Bank MCQ (5)
[Exact competitive format]
### E — Use in Sentence (3)
### ✅ Answer Key
[All answers with Bengali + English explanations]"""
                with st.spinner("Building..."):
                    res = call_ai(p)
                if res:
                    show_result(res, "vocab_quiz")

    # ── Compare ──
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
| Avg sentence length | | |
| Complexity | | |
| Voice | | |
| Vocabulary level | | |
| Tone | | |
### Vocabulary Battle
### Strengths & Gaps
| | T1 ✅ | T1 ❌ | T2 ✅ | T2 ❌ |
|---|---|---|---|---|
### Verdict
| Category | Winner | T1/10 | T2/10 |
|---|---|---|---|
### Learning Points
"""
                with st.spinner("Comparing..."):
                    res = call_ai(p)
                if res:
                    show_result(res, "compare")

    # ── Standalone Notes ──
    with tool_tabs[7]:
        st.caption("Independent note-making (separate from main analysis)")
        n_text = st.text_area("", height=200, key="note_text",
                              placeholder="Paste any text for standalone notes...")
        if st.button("📓 Generate Notes", type="primary", key="note_btn"):
            if n_text.strip():
                p = f"""{build_system_header()}
TEXT: \"\"\"{n_text}\"\"\"
# MASTER STUDY NOTES
## 1. Concept Map
Central Theme: EN + বাংলা
Key Arguments: 3 points EN + বাংলা each
## 2. The Event in Context
[Narrative — Bengali paragraph + English paragraph]
Famous Related Events (3): Story format for each
Bangladesh Angle: [specific facts]
## 3. Vocabulary (12+ words)
[Deep-dive format — same as main analysis]
## 4. Exam Focus
High frequency table + 5 predicted MCQs
## 5. Writing Formulas (5)
## 6. Revision Card
[Screenshot-ready card]"""
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

    # ── Word Bank ──
    with tool_tabs[8]:
        with st.form("wb_form"):
            wc1, wc2, wc3 = st.columns([2, 3, 1])
            with wc1:
                nw = st.text_input("Word", placeholder="resilience")
            with wc2:
                nm = st.text_input("Meaning", placeholder="স্থিতিস্থাপকতা | capacity to recover")
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
            wc2.metric("Today", sum(1 for w in st.session_state.saved_vocab if w["added"] == today))
            wc3.metric("For Quiz", len(st.session_state.saved_vocab))

            wb_search = st.text_input("🔍 Search", key="wb_search")
            filtered = [w for w in st.session_state.saved_vocab
                        if not wb_search
                        or wb_search.lower() in w["word"].lower()
                        or wb_search.lower() in w["meaning"].lower()]

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
                    if st.button("🧠 Quiz Me!", type="primary", use_container_width=True, key="wb_quiz"):
                        wstr = ", ".join(w["word"] for w in st.session_state.saved_vocab[-15:])
                        with st.spinner("Building quiz..."):
                            res = call_ai(f"{build_system_header()}\nWords: {wstr}\n[Full quiz — BCS MCQ + synonyms + fill blanks + root analysis]")
                        if res:
                            show_result(res, "wb_quiz")
            with qc2:
                export = "# Word Bank\n\n| Word | Meaning | Added |\n|---|---|---|\n"
                for w in st.session_state.saved_vocab:
                    export += f"| {w['word']} | {w['meaning']} | {w['added']} |\n"
                st.download_button("📥 Export", export, "word_bank.md", use_container_width=True)

# ── Footer ──
st.markdown(
    "<p style='text-align:center; color:#bbb; font-size:0.82rem; padding:1rem 0 0;'>"
    "The Analyst · BCS · GRE · IELTS · Law · Journalism"
    "</p>",
    unsafe_allow_html=True
)
