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

# Sidebar for Study Material Hub
st.sidebar.title("📚 Study Material Hub")
choice = st.sidebar.selectbox(
    "Select Format",
    ("Text", "PDF", "Word Document", "PPT", "Excel", "CSV")
)

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

with st.sidebar:
    uploaded_files = st.file_uploader(f"Upload {choice}", type=None, accept_multiple_files=True)
    if uploaded_files:
        with st.spinner("Processing study materials..."):
            extracted_text = extract_text(uploaded_files, choice)
            if not extracted_text.strip():
                st.warning("No readable text found in the material. It might be a scanned document or an image-based PDF.")
            st.session_state.materials_text = extracted_text
            st.success(f"Successfully loaded {len(uploaded_files)} file(s)!")

# Chat Display
for message in st.session_state.history:
    st.chat_message(message["role"]).markdown(message["content"])

query = st.chat_input("Ask a study question...")

if query:
    st.chat_message("user").markdown(query)
    st.session_state.history.append({"role": "user", "content": query})

    # Construct the query with context if available - Using a larger chunk of text since Gemini supports it
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
        final_answer = ""
        for part in raw_answer:
            if isinstance(part, dict) and "text" in part:
                final_answer += part["text"]
            elif isinstance(part, str):
                final_answer += part
        answer = final_answer
    else:
        answer = str(raw_answer)

    st.session_state.history.append({"role": "ai", "content": answer})
    st.chat_message("ai").markdown(answer)
