import streamlit as st
from openai import OpenAI
import requests
from reportlab.lib.pagesizes import letter as letter_pagesize
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, HRFlowable
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
import io
from datetime import date

st.set_page_config(page_title="VA Support Tools", page_icon="🇺🇸", layout="wide")
st.title("🇺🇸 Veteran Support Tools")

# Always show both key fields in the sidebar
st.sidebar.header("API Keys")
openai_key = st.sidebar.text_input(
    "OpenAI API Key",
    type="password",
    value=st.secrets.get("OPENAI_API_KEY", "")
)
serpapi_key = st.sidebar.text_input(
    "SerpAPI Key",
    type="password",
    value=st.secrets.get("SERPAPI_API_KEY", "")
)

# Mode selector
mode = st.radio(
    "Select tool:",
    ["Veteran Claim Organizer", "Survivor Senator Letter"],
    horizontal=True,
    index=0
)

# ============================================================
# MODE 1: Veteran Claim Organizer
# ============================================================
if mode == "Veteran Claim Organizer":
    st.write("Organize your claim details, pull public criteria, and generate a structured summary PDF.")

    privacy_mode = st.toggle(
        "Privacy mode (clear sensitive data after PDF generation)",
        value=True
    )
    if privacy_mode:
        st.info("Privacy mode on. Sensitive session data can be cleared after generation.")

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
        focused_condition = st.text_input("Specify condition") or "unspecified condition"
    else:
        focused_condition = claim_type

    st.subheader("Military Background")
    col1, col2 = st.columns(2)
    service_branch = col1.text_input("Service Branch")
    discharge_year = col2.text_input("Discharge Year")

    st.subheader("Guided Checklist")
    q_diagnosed = st.radio("Official diagnosis by a doctor?", ["Yes", "No, but symptoms present", "Scheduling evaluation"])
    q_service_event = st.radio("In-service event / exposure / aggravation?", ["Specific incident/deployment", "Gradual onset while serving", "Aggravation of pre-existing condition", "Unsure / none identified"])
    q_records = st.radio("Service medical / incident records?", ["Yes, I have them", "VA can pull them", "Relying on buddy statements / journals"])
    q_continuity = st.radio("Continuity since discharge?", ["Constant ongoing problem", "Flare-ups but never fully gone", "Recent onset / worsening"])

    veteran_story = st.text_area(
        f"Your personal story about {focused_condition}",
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
        doc = SimpleDocTemplate(
            buffer,
            pagesize=letter_pagesize,
            rightMargin=54,
            leftMargin=54,
            topMargin=54,
            bottomMargin=54
        )
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

        doc.build(story)
        buffer.seek(0)
        return buffer.getvalue()

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
                except Exception as e:
                    st.error(f"Generation failed: {e}")

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

        if st.button("Clear generated report from session"):
            for key in ["pdf_bytes", "pdf_name", "report_text", "form_preview"]:
                st.session_state.pop(key, None)
            st.rerun()

# ============================================================
# MODE 2: Survivor Senator Letter (with VA language feature)
# ============================================================
elif mode == "Survivor Senator Letter":
    st.subheader("Letter to U.S. Senators — Surviving Family of 100% Service-Connected Veteran")
    st.write("Compose a formal letter enriched with authentic VA language and terminology.")

    st.markdown("### Your Information (Survivor)")
    col_a, col_b = st.columns(2)
    survivor_name = col_a.text_input("Your Full Name")
    relationship = col_b.selectbox("Your Relationship to the Veteran", ["Widow / Surviving Spouse", "Child", "Dependent", "Other"])
    your_address = st.text_area("Your Mailing Address", height=80)
    your_phone = st.text_input("Your Phone Number")
    your_email = st.text_input("Your Email Address")

    st.markdown("### Veteran Information")
    vet_name = st.text_input("Veteran’s Full Name")
    vet_branch = st.text_input("Veteran’s Branch of Service")
    vet_dates = st.text_input("Service Dates (approximate is fine)")
    rating_details = st.text_area("100% Service-Connected Rating Details (brief)", height=80)

    st.markdown("### Purpose of the Letter")
    letter_purpose = st.text_area("What would you like to ask your Senators to do or consider?", height=120)
    senator_names = st.text_input("Senator Names (optional)", placeholder="Leave blank for “My U.S. Senators”")

    def search_va_language(query_context: str, api_key: str) -> str:
        if not api_key:
            return "No SerpAPI key provided."
        params = {
            "engine": "google",
            "q": f"VA official language terminology survivor benefits 100% service-connected permanent total {query_context}",
            "hl": "en",
            "gl": "us",
            "api_key": api_key,
            "num": 6
        }
        try:
            r = requests.get("https://serpapi.com/search.json", params=params, timeout=15)
            r.raise_for_status()
            data = r.json()
            snippets = []
            for result in data.get("organic_results", [])[:5]:
                title = result.get("title", "")
                snippet = result.get("snippet", "")
                snippets.append(f"- {title}: {snippet}")
            return "\n".join(snippets) if snippets else "No additional VA language found."
        except Exception as e:
            return f"VA language search unavailable: {e}"

    def create_letter_pdf(letter_text: str) -> bytes:
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=letter_pagesize,
            rightMargin=72,
            leftMargin=72,
            topMargin=72,
            bottomMargin=72
        )
        styles = getSampleStyleSheet()
        body_style = ParagraphStyle(
            "LetterBody",
            parent=styles["Normal"],
            fontSize=11,
            leading=16,
            spaceAfter=12
        )
        safe_text = (letter_text or "").replace("\n", "<br/>")
        story = [Paragraph(safe_text, body_style)]
        doc.build(story)
        buffer.seek(0)
        return buffer.getvalue()

    if st.button("Generate Senator Letter", type="primary"):
        if not openai_key:
            st.error("OpenAI API key required.")
        elif not survivor_name or not vet_name or not letter_purpose:
            st.warning("Please fill in at least your name, the Veteran’s name, and the purpose of the letter.")
        else:
            try:
                with st.spinner("Gathering relevant VA language and terminology..."):
                    va_context = search_va_language(f"{rating_details} {letter_purpose}", serpapi_key)

                client = OpenAI(api_key=openai_key)
                today = date.today().strftime("%B %d, %Y")
                senators = senator_names.strip() if senator_names else "My U.S. Senators"

                prompt = (
                    f"Write a formal, respectful, and professional letter dated {today} from {survivor_name} "
                    f"({relationship} of the late Veteran {vet_name}) to {senators}.\n\n"
                    f"Survivor contact information:\n"
                    f"Address: {your_address or 'Not provided'}\n"
                    f"Phone: {your_phone or 'Not provided'}\n"
                    f"Email: {your_email or 'Not provided'}\n\n"
                    f"Veteran background: {vet_name}, {vet_branch or 'U.S. Armed Forces'}, served {vet_dates or 'during active duty'}. "
                    f"Rated 100% service-connected ({rating_details or 'details not specified'}).\n\n"
                    f"Purpose of the letter: {letter_purpose}\n\n"
                    f"Relevant VA language, terminology, and official phrasing to incorporate naturally:\n{va_context}\n\n"
                    "Instructions:\n"
                    "- Format with proper date and sender address block, formal salutation, clear body paragraphs, and respectful closing.\n"
                    "- Inundate the letter with authentic VA language and terminology from the provided context whenever it fits naturally.\n"
                    "- Keep the tone dignified and factual. Do not invent details."
                )

                with st.spinner("Generating letter with VA language..."):
                    response = client.chat.completions.create(
                        model="gpt-4o-mini",
                        messages=[{"role": "user", "content": prompt}],
                        temperature=0.3
                    )
                    letter_content = response.choices[0].message.content or ""

                st.session_state["senator_letter"] = letter_content
                st.session_state["letter_pdf"] = create_letter_pdf(letter_content)
                st.session_state["letter_filename"] = f"Senator_Letter_{survivor_name.replace(' ', '_')}.pdf"
                st.session_state["va_context_used"] = va_context
                st.success("Letter generated with VA language context.")
            except Exception as e:
                st.error(f"Could not generate letter: {type(e).__name__}: {e}")

    if "senator_letter" in st.session_state:
        st.markdown("---")
        st.subheader("Your Letter")
        st.text_area("Letter text", value=st.session_state["senator_letter"], height=400)
        st.download_button(
            "Download Letter as PDF",
            data=st.session_state["letter_pdf"],
            file_name=st.session_state["letter_filename"],
            mime="application/pdf"
        )
        with st.expander("View VA language context used"):
            st.text(st.session_state.get("va_context_used", "None"))
        if st.button("Clear letter"):
            for k in ["senator_letter", "letter_pdf", "letter_filename", "va_context_used"]:
                st.session_state.pop(k, None)
            st.rerun()

st.markdown("---")
st.caption("Self-help organizer tools. Not affiliated with the Department of Veterans Affairs.")
