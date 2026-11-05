import streamlit as st
from openai import OpenAI
import requests
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, HRFlowable
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
import io

st.set_page_config(page_title="VA Claim Organizer", page_icon="🇺🇸", layout="wide")
st.title("🇺🇸 Veteran VA Claim Organizer & Evidence Helper")
st.write("Organize your claim details, pull public criteria, and generate a structured summary PDF.")

# Privacy
privacy_mode = st.toggle(
    "Privacy mode (clear sensitive data after PDF generation)",
    value=True,
    help="Clears the generated report from session after you download or clear it. Closing the browser tab also clears everything."
)
if privacy_mode:
    st.info("Privacy mode on. Sensitive session data can be cleared after generation.")

# API keys
if "openai" in st.secrets and "serpapi" in st.secrets:
    openai_key = st.secrets["openai"]["api_key"]
    serpapi_key = st.secrets["serpapi"]["api_key"]
else:
    st.sidebar.header("API Keys (or use Streamlit secrets)")
    openai_key = st.sidebar.text_input("OpenAI API Key", type="password")
    serpapi_key = st.sidebar.text_input("SerpAPI Key", type="password")

# Claim type
claim_type = st.selectbox(
    "1. Condition / claim type",
    [
        "Mental Health (PTSD, Anxiety, Depression)",
        "Hearing (Tinnitus, Hearing Loss)",
        "Musculoskeletal (Back, Neck, Hip, Knee, Joints)",
        "Respiratory (Asthma, Sleep Apnea, COPD, Toxic Exposure)",
        "Gastrointestinal (GERD, IBS, etc.)",
        "Podiatry / Foot Conditions",
        "Neurological (Migraines, Sciatica, Radiculopathy)",
        "Skin / Dermatology",
        "Other / Not Listed"
    ]
)
if claim_type == "Other / Not Listed":
    focused_condition = st.text_input("Specify condition", placeholder="e.g., Chronic Fatigue Syndrome") or "unspecified condition"
else:
    focused_condition = claim_type

# Military background
st.subheader("Military Background")
col1, col2 = st.columns(2)
service_branch = col1.text_input("Service Branch", placeholder="Army, Navy, Air Force, Marines, Coast Guard, Space Force")
discharge_year = col2.text_input("Discharge Year", placeholder="e.g. 2018")

# Checklist
st.subheader("Guided Checklist")
q_diagnosed = st.radio("Official diagnosis by a doctor?", ["Yes", "No, but symptoms present", "Scheduling evaluation"])
q_service_event = st.radio("In-service event / exposure / aggravation?", ["Specific incident/deployment", "Gradual onset while serving", "Aggravation of pre-existing condition", "Unsure / none identified"])
q_records = st.radio("Service medical / incident records?", ["Yes, I have them", "VA can pull them", "Relying on buddy statements / journals"])
q_continuity = st.radio("Continuity since discharge?", ["Constant ongoing problem", "Flare-ups but never fully gone", "Recent onset / worsening"])

# Narrative
veteran_story = st.text_area(
    f"Your personal story about {focused_condition}",
    placeholder="Describe what happened in service, your job/MOS, symptoms then and now, and how it limits work or daily life...",
    height=160
)

def search_va_evidence(condition: str, api_key: str) -> str:
    if not api_key:
        return "No SerpAPI key — skipping live search."
    params = {
        "engine": "google",
        "q": f"VA disability rating criteria 38 CFR {condition} medical nexus",
        "hl": "en",
        "gl": "us",
        "api_key": api_key,
        "num": 5
    }
    try:
        r = requests.get("https://serpapi.com/search.json", params=params, timeout=15)
        r.raise_for_status()
        data = r.json()
        snippets = []
        for result in data.get("organic_results", [])[:4]:
            title = result.get("title", "")
            snippet = result.get("snippet", "")
            link = result.get("link", "")
            snippets.append(f"- **{title}**: {snippet} ([source]({link}))")
        return "\n".join(snippets) if snippets else "No relevant results found."
    except Exception as e:
        return f"Search failed: {e}"

def create_pdf(text: str) -> bytes:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=54, leftMargin=54, topMargin=54, bottomMargin=54)
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("Title", parent=styles["Heading1"], fontSize=16, textColor=colors.HexColor("#1A365D"), alignment=1, spaceAfter=12)
    header_style = ParagraphStyle("Header", parent=styles["Heading2"], fontSize=12, textColor=colors.HexColor("#2C3E50"), spaceBefore=12, spaceAfter=6)
    body_style = ParagraphStyle("Body", parent=styles["Normal"], fontSize=10, leading=14, spaceAfter=6)

    story = [
        Paragraph("<b>VA CLAIM STRATEGY BRIEF (SELF-HELP DRAFT)</b>", title_style),
        HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#1A365D"), spaceAfter=12),
        Paragraph("<i>This is a self-help organizer document only.</i>", body_style),
        Spacer(1, 12)
    ]

    for line in text.split("\n"):
        line = line.strip()
        if not line:
            story.append(Spacer(1, 6))
            continue
        if line.startswith(("1.", "2.", "3.", "4.", "5.", "###")):
            clean = line.replace("###", "").strip()
            story.append(Paragraph(f"<b>{clean}</b>", header_style))
        else:
            story.append(Paragraph(line, body_style))

    story.append(Spacer(1, 20))
    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()

# Generation
if st.button("Generate Claim Summary & PDF", type="primary"):
    if not openai_key:
        st.error("OpenAI API key required.")
    elif not veteran_story.strip():
        st.warning("Please enter your story.")
    else:
        with st.spinner("Searching public VA criteria & medical sources..."):
            live_evidence = search_va_evidence(focused_condition, serpapi_key)

        with st.spinner("Generating structured summary..."):
            try:
                client = OpenAI(api_key=openai_key)
                user_payload = (
                    f"SERVICE BRANCH: {service_branch or 'Not specified'}\n"
                    f"DISCHARGE YEAR: {discharge_year or 'Not specified'}\n"
                    f"CONDITION: {focused_condition}\n"
                    f"DIAGNOSIS: {q_diagnosed}\n"
                    f"IN-SERVICE EVENT: {q_service_event}\n"
                    f"RECORDS: {q_records}\n"
                    f"CONTINUITY: {q_continuity}\n\n"
                    f"NARRATIVE:\n{veteran_story}\n\n"
                    f"SEARCH CONTEXT:\n{live_evidence}"
                )
                system_prompt = (
                    "You are a careful claims organizer assistant. "
                    "Synthesize the veteran's information with the provided search results into a clear, factual draft. "
                    "Structure exactly as:\n"
                    "1. MILITARY PROFILE & MEDICAL EVIDENCE SUMMARY\n"
                    "2. IN-SERVICE INCIDENT & SERVICE CONNECTION NEXUS\n"
                    "3. CHRONICITY / CONTINUITY OF SYMPTOMS\n"
                    "4. OCCUPATIONAL & SOCIAL IMPAIRMENT (aligned with general 38 CFR concepts)\n"
                    "5. RELEVANT PUBLIC CITATIONS & 38 CFR NOTES\n\n"
                    "Be objective and supportive. Do not invent facts."
                )
                response = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_payload}
                    ],
                    temperature=0.2
                )
                output_text = response.choices[0].message.content
                pdf_bytes = create_pdf(output_text)

                st.session_state["pdf_bytes"] = pdf_bytes
                st.session_state["pdf_name"] = f"VA_Claim_Summary_{focused_condition.replace(' ', '_')[:40]}.pdf"
                st.session_state["report_text"] = output_text
                st.session_state["form_preview"] = {
                    "box11": focused_condition,
                    "box13": f"Service connection pathway developed during {service_branch or 'military service'}. See attached summary for details and citations.",
                    "box14": f"Continuity: {q_continuity}. Impacts daily function consistent with claimed condition."
                }
                st.success("Summary generated.")
                if privacy_mode:
                    st.info("Privacy mode: you can clear the report from session below after downloading.")
            except Exception as e:
                st.error(f"Generation failed: {e}")

# Display results
if "report_text" in st.session_state:
    st.markdown("---")
    tab1, tab2 = st.tabs(["Structured Report", "Form Field Preview"])

    with tab1:
        st.subheader("Draft Summary")
        st.markdown(st.session_state["report_text"])
        st.download_button(
            "Download PDF Summary",
            data=st.session_state["pdf_bytes"],
            file_name=st.session_state["pdf_name"],
            mime="application/pdf"
        )

    with tab2:
        st.subheader("Suggested text for VA Form 21-526EZ (manual entry)")
        preview = st.session_state.get("form_preview", {})
        st.markdown("**Box 11 – Current Disability(ies) Claimed**")
        st.write(preview.get("box11", ""))
        st.markdown("**Box 13 – Service Connection Context**")
        st.write(preview.get("box13", ""))
        st.markdown("**Box 14 – Chronicity / Impact Notes**")
        st.write(preview.get("box14", ""))

    if st.button("Clear generated report from session (privacy)"):
        for key in ["pdf_bytes", "pdf_name", "report_text", "form_preview"]:
            st.session_state.pop(key, None)
        st.rerun()

st.markdown("---")
st.caption("Self-help organizer tool. Not affiliated with the Department of Veterans Affairs.")
