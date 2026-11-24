import streamlit as st
from openai import OpenAI
import requests
from reportlab.lib.pagesizes import letter as letter_pagesize
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, HRFlowable
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
import io
from datetime import date

st.set_page_config(page_title="VSO Letter Editor", page_icon="🇺🇸", layout="wide")
st.title("🇺🇸 VSO Letter Editor")
st.caption("Professional, fact-focused letters for your Veteran Service Officer. Removes grievances and keeps the focus on your disability evidence.")

# ---------- Secrets + Sidebar fallback ----------
def get_secret(key: str, label: str):
    if key in st.secrets:
        return st.secrets[key]
    return st.sidebar.text_input(label, type="password")

openai_key = get_secret("OPENAI_API_KEY", "OpenAI API Key")
serpapi_key = get_secret("SERPAPI_API_KEY", "SerpAPI Key")

if "OPENAI_API_KEY" not in st.secrets:
    st.sidebar.info("Add keys to `.streamlit/secrets.toml` to hide these inputs.")

# ---------- Cached OpenAI client ----------
@st.cache_resource
def get_openai_client(api_key: str):
    return OpenAI(api_key=api_key)

# ---------- Session state ----------
for key in ["letter_text", "letter_pdf", "letter_filename", "research_context"]:
    st.session_state.setdefault(key, None)

# ---------- Main form ----------
with st.form("vso_form"):
    st.subheader("1. Your Instructions (optional but recommended)")
    veteran_prompt = st.text_area(
        "Tell the app what you want this letter to do",
        placeholder="Example: Make this professional for my VSO. Focus on my back condition and the service connection. Remove any complaints about the VA.",
        height=100
    )

    st.subheader("2. Your Statement")
    st.caption("Paste or type everything here — personal story, templated text, medical notes, timeline, etc. The app will clean and organize it.")
    veteran_statement = st.text_area(
        "Your information",
        height=300,
        placeholder="Paste your draft, notes, or templated statement here..."
    )

    col1, col2 = st.columns(2)
    with col1:
        generate_btn = st.form_submit_button("Generate / Regenerate VSO Letter", type="primary")
    with col2:
        clear_btn = st.form_submit_button("Clear Letter")

# ---------- Helper functions ----------
def search_va_criteria(statement: str, api_key: str) -> str:
    if not api_key or not statement.strip():
        return ""
    # Extract a short query from the statement
    query = f"VA disability rating criteria 38 CFR {statement[:120]}"
    params = {
        "engine": "google",
        "q": query,
        "hl": "en",
        "gl": "us",
        "api_key": api_key,
        "num": 4
    }
    try:
        r = requests.get("https://serpapi.com/search.json", params=params, timeout=12)
        r.raise_for_status()
        data = r.json()
        snippets = []
        for result in data.get("organic_results", [])[:3]:
            title = result.get("title", "")
            snippet = result.get("snippet", "")
            snippets.append(f"- {title}: {snippet}")
        return "\n".join(snippets) if snippets else ""
    except Exception:
        return ""

def create_pdf(text: str) -> bytes:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter_pagesize,
        rightMargin=54,
        leftMargin=54,
        topMargin=54,
        bottomMargin=54
    )
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "Title", parent=styles["Heading1"], fontSize=15,
        textColor=colors.HexColor("#1A365D"), alignment=1, spaceAfter=12
    )
    body_style = ParagraphStyle(
        "Body", parent=styles["Normal"], fontSize=11, leading=15, spaceAfter=8
    )
    story = [
        Paragraph("<b>Statement for Veteran Service Officer</b>", title_style),
        HRFlowable(width="100%", thickness=1, color=colors.HexColor("#1A365D"), spaceAfter=12),
        Paragraph("<i>Fact-focused draft for VSO use. Self-help document only.</i>", body_style),
        Spacer(1, 10)
    ]
    for line in text.split("\n"):
        line = line.strip()
        if line:
            story.append(Paragraph(line.replace("\n", "<br/>"), body_style))
        else:
            story.append(Spacer(1, 6))
    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()

# ---------- Generation ----------
if generate_btn:
    if not openai_key:
        st.error("OpenAI API key required.")
    elif not veteran_statement.strip():
        st.warning("Please enter your statement.")
    else:
        client = get_openai_client(openai_key)
        with st.spinner("Researching relevant VA criteria..."):
            research = search_va_criteria(veteran_statement, serpapi_key)
            st.session_state["research_context"] = research

        with st.spinner("Generating clean VSO letter..."):
            system_prompt = """
You are a professional claims organizer assisting a Veteran in preparing a statement for their Veteran Service Officer (VSO).

Rules:
- Remove all grievances, complaints, accusations, or negative commentary about the VA, federal government, claim processors, or the claims process.
- Stick strictly to factual information about the Veteran’s disability condition(s), symptoms, service connection, medical evidence, continuity, and functional impact.
- Organize the content clearly and professionally so a VSO can use it effectively when submitting the claim.
- Do not invent facts. Only use information provided by the Veteran.
- Keep the tone neutral, factual, and respectful.
- Structure the output as a clean, ready-to-use statement or letter for the VSO.
"""
            user_content = f"""
Veteran’s instructions:
{veteran_prompt or "Make this professional and fact-focused for my VSO."}

Veteran’s raw statement:
{veteran_statement}

Relevant public VA criteria research (use only if helpful and accurate):
{research or "None available."}
"""
            try:
                response = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_content}
                    ],
                    temperature=0.3
                )
                letter = response.choices[0].message.content or ""
                st.session_state["letter_text"] = letter
                st.session_state["letter_pdf"] = create_pdf(letter)
                st.session_state["letter_filename"] = f"VSO_Statement_{date.today().strftime('%Y%m%d')}.pdf"
                st.success("Letter generated. Review it below. You can edit your input and regenerate as many times as needed.")
            except Exception as e:
                st.error(f"Generation failed: {e}")

if clear_btn:
    for k in ["letter_text", "letter_pdf", "letter_filename", "research_context"]:
        st.session_state.pop(k, None)
    st.rerun()

# ---------- Display ----------
if st.session_state.get("letter_text"):
    st.markdown("---")
    st.subheader("Generated VSO Letter")
    st.text_area("Letter (editable copy)", value=st.session_state["letter_text"], height=400, key="display_letter")
    st.download_button(
        "Download as PDF",
        data=st.session_state["letter_pdf"],
        file_name=st.session_state["letter_filename"],
        mime="application/pdf"
    )
    with st.expander("View research context used (if any)"):
        st.text(st.session_state.get("research_context") or "None")

st.markdown("---")
st.caption("Self-help tool for organizing statements for your VSO. Not affiliated with the Department of Veterans Affairs. Always review the output carefully before using it.")
