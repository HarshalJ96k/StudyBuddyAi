import io
import fitz  # PyMuPDF for reliable PDF parsing
from docx import Document
import pandas as pd
from pptx import Presentation
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_community.utilities import GoogleSerperAPIWrapper
from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.memory import MemorySaver
import streamlit as st
import re
import youtube_transcript_api
from youtube_transcript_api import YouTubeTranscriptApi

# Page Config for Better UI
st.set_page_config(page_title="StudyGenie AI", page_icon="🤖", layout="wide")

load_dotenv()

# Initialize LLM and Tools - Using the most stable Gemini Pro model
llm = ChatGoogleGenerativeAI(model="gemini-3-flash-preview")
search = GoogleSerperAPIWrapper()
tools = [search.run]

# Custom CSS for Sidebar Look
st.markdown("""
    <style>
    /* Distinct Sidebar Style */
    section[data-testid="stSidebar"] {
        background-color: #1e293b !important;
        border-right: 1px solid #334155;
    }
    
    /* Style buttons in the sidebar */
    .stSidebar .stButton > button {
        background: linear-gradient(135deg, #6366f1 0%, #a855f7 100%);
        color: white;
        border: none;
        border-radius: 8px;
        transition: all 0.3s ease;
    }
    </style>
""", unsafe_allow_html=True)

# Memory and Session State Initialization
if "memory" not in st.session_state:
    st.session_state.memory = MemorySaver()
    st.session_state.history = []
    st.session_state.materials_text = ""

# Agent Setup with Study Helper Prompt
system_prompt = (
    "You are StudyGenie AI, a dedicated and supportive study assistant. "
    "Your mission is to help students understand their study materials, answer questions clearly, "
    "summarize content, and provide detailed explanations. "
    "\n\nCRITICAL RULE: When study materials are provided, you MUST prioritize information from those materials. "
    "If the answer is found in the uploaded documents, use it as the primary source. "
    "If the answer isn't in the material, you can use your general knowledge or search the web if needed, "
    "but clearly specify when you are doing so. "
    "\n\nAlways maintain an encouraging, academic, and professional tone."
)

agent = create_react_agent(
    model=llm,
    tools=tools,
    checkpointer=st.session_state.memory
)

# Web Interface Header
st.title("StudyGenie AI 🤖")
st.markdown("### Your Intelligent Study Companion")
st.write("Upload your notes, books, or data and ask anything related to your studies!")

#Different Tabs at Home Page
tab_chat,tab_video=st.tabs(["Chat","Video to Text"])

with tab_video:
    st.title("🎥 Lecture Video to Notes")

    video_url = st.text_input(
        "Paste lecture video link (YouTube / Drive)",
        placeholder="https://www.youtube.com/watch?v=..."
    )

    note_style = st.selectbox(
        "Notes Format",
        ["Short Notes", "Detailed Notes", "Bullet Points", "Exam-Oriented"]
    )

    def get_video_id(url):
        pattern = r"(?:v=|\/)([0-9A-Za-z_-]{11}).*"
        match = re.search(pattern, url)
        return match.group(1) if match else None

    if st.button("Generate Notes"):
        if video_url:
            with st.spinner("⏳ Extracting transcript and generating notes..."):
                try:
                    video_id = get_video_id(video_url)
                    if not video_id:
                        st.error("Invalid YouTube URL")
                        st.stop()
                    # Use fully qualified name to avoid any potential namespace issues
                    transcript_list = YouTubeTranscriptApi.get_transcript(video_id)
                    transcript_text = " ".join([i['text'] for i in transcript_list])
                    
                    # Use the transcript to generate accurate notes
                    prompt = f"""
                    You are StudyGenie AI. Convert the following lecture transcript into {note_style}.
                    Ensure the notes are accurate, easy to understand, and follow a logical structure.
                    
                    TRANSCRIPT:
                    {transcript_text[:15000]} # Limit to handle long videos
                    """
                    
                    response = llm.invoke(prompt)
                    st.success("✅ Notes Generated")
                    
                    st.markdown("### 📘 Generated Notes")
                    # Handle response content clean display
                    raw_content = response.content
                    if isinstance(raw_content, list):
                        clean_content = "".join([part.get("text", "") if isinstance(part, dict) else str(part) for part in raw_content])
                    else:
                        clean_content = str(raw_content)
                    st.markdown(clean_content)
                except Exception as e:
                    st.error(f"❌ Error: {str(e)}")
                    st.info("Try another video or ensure the video has subtitles/transcripts enabled.")
        else:
            st.warning("Please enter a YouTube video link")

def extract_text(files, format_choice):
    text_content = ""
    for file in files:
        if format_choice == "Text":
            try:
                text_content += file.read().decode("utf-8") + "\n"
            except Exception:
                file.seek(0)
                text_content += file.read().decode("latin-1", errors="replace") + "\n"
        elif format_choice == "PDF":
            # Using fitz for much better text extraction especially on large files
            doc = fitz.open(stream=file.read(), filetype="pdf")
            for page in doc:
                text_content += page.get_text() + "\n"
            doc.close()
        elif format_choice == "Word Document":
            doc = Document(file)
            for para in doc.paragraphs:
                text_content += para.text + "\n"
        elif format_choice == "PPT":
            prs = Presentation(file)
            for slide in prs.slides:
                for shape in slide.shapes:
                    if hasattr(shape, "text"):
                        text_content += shape.text + "\n"
        elif format_choice == "Excel" or format_choice == "CSV":
            df = pd.read_excel(file) if format_choice == "Excel" else pd.read_csv(file)
            text_content += df.to_string() + "\n"
    return text_content

# Sidebar for Study Material Hub
st.sidebar.title("📚 Study Material Hub")
choice = st.sidebar.selectbox(
    "Select Format",
    ("Text", "PDF", "Word Document", "PPT", "Excel", "CSV")
)

with st.sidebar:
    uploaded_files = st.file_uploader(f"Upload {choice}", type=None, accept_multiple_files=True)
    if uploaded_files:
        with st.spinner("Processing study materials..."):
            extracted_text = extract_text(uploaded_files, choice)
            if not extracted_text.strip():
                st.warning("No readable text found in the material. It might be a scanned document or an image-based PDF.")
            st.session_state.materials_text = extracted_text
            st.success(f"Successfully loaded {len(uploaded_files)} file(s)!")

with tab_chat:
    # Chat Display
    for message in st.session_state.history:
        st.chat_message(message["role"]).markdown(message["content"])

# Chat input MUST be at the top level (not inside tabs)
query = st.chat_input("Ask a study question...")

if query:
    # We can check which tab is currently active if needed, 
    # but usually chat input at bottom is expected behavior.
    st.chat_message("user").markdown(query)
    st.session_state.history.append({"role": "user", "content": query})

    # Construct the query with context if available
    full_prompt = query
    if st.session_state.materials_text:
        # Increase context window to 15000 characters for better book/document coverage
        full_prompt = f"STUDY MATERIAL (Extracted Text):\n{st.session_state.materials_text[:15000]}...\n\nQUESTION: {query}"

    with st.spinner("Thinking..."):
        config = {"configurable": {"thread_id": "1"}}
        response = agent.invoke(
            {"messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": full_prompt}
            ]},
            config
        )

    # Handle various response formats from the model
    raw_answer = response["messages"][-1].content
    if isinstance(raw_answer, list):
        answer = "".join([part.get("text", "") if isinstance(part, dict) else str(part) for part in raw_answer])
    else:
        answer = str(raw_answer)

    st.session_state.history.append({"role": "ai", "content": answer})
    st.chat_message("ai").markdown(answer)
    # Note: Because the script reruns, the new message will appear inside the Chat tab on the next pass.
