import streamlit as st
import os
import requests
from pdf2docx import Converter
from docx import Document
import tempfile
import csv

CSV_PATH = "data/qa_history.csv"
API_KEY = "AIzaSyBJo4sK0hzzeopDSj4GOUzsL6A9DEzTNZ4"
URL_API = (
    f"https://generativelanguage.googleapis.com/v1beta/models/"
    f"gemini-2.0-flash:generateContent?key={API_KEY}"
)

def save_qa_to_csv(question, answer):
    with open(CSV_PATH, mode="a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([question, answer])

def load_previous_context():
    if not os.path.exists(CSV_PATH):
        return ""
    with open(CSV_PATH, mode="r", encoding="utf-8") as f:
        reader = csv.reader(f)
        history = list(reader)
        context = ""
        for q, a in history[-3:]:
            context += f"Q: {q}\nA: {a}\n"
        return context

def call_gemini(question: str, content: str):
    previous_context = load_previous_context()
    prompt = (
        f"""Use the document content and previous conversation to answer the question.
        ## Document Content:
        {content}

        ## Previous Conversation:
        {previous_context}

        ## Current Question:
        {question}
        """
    )
    headers = {"Content-Type": "application/json"}
    payload = {"contents": [{"parts": [{"text": prompt}]}]}

    try:
        response = requests.post(URL_API, json=payload, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json().get("candidates", [])
        if not data:
            return "API returned no valid candidates."
        return data[0]["content"]["parts"][0]["text"].strip()
    except Exception as e:
        return f"Error calling Gemini API: {e}"

if "messages" not in st.session_state:
    st.session_state["messages"] = []
if "doc_text" not in st.session_state:
    st.session_state["doc_text"] = ""
if "uploaded_filename" not in st.session_state:
    st.session_state["uploaded_filename"] = None

with st.sidebar:
    st.header("📂 Upload PDF")
    uploaded_file = st.file_uploader("", type=["pdf"])
    if uploaded_file:
        if st.session_state["uploaded_filename"] != uploaded_file.name:
            st.session_state["uploaded_filename"] = uploaded_file.name

            st.success(f"Uploaded: {uploaded_file.name}")
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_pdf:
                tmp_pdf.write(uploaded_file.read())
                pdf_path = tmp_pdf.name

            docx_path = pdf_path.replace(".pdf", ".docx")
            with st.spinner("Converting PDF to DOCX..."):
                cv = Converter(pdf_path)
                cv.convert(docx_path, start=0, end=None)
                cv.close()

            with st.spinner("Extracting text from DOCX..."):
                doc = Document(docx_path)
                full_text = "\n".join([para.text for para in doc.paragraphs])

            st.session_state["doc_text"] = full_text

            os.remove(pdf_path)
            os.remove(docx_path)

    if st.session_state["doc_text"]:
        with st.expander("📄 View Extracted Content"):
            st.text_area("Text from PDF", st.session_state["doc_text"], height=300)
    else:
        st.info("Please upload a PDF file to provide context.")

st.markdown('<div class="chat-container">', unsafe_allow_html=True)
for msg in st.session_state["messages"]:
    if msg["role"] == "user":
        st.chat_message("user").write(msg["text"])
    else:
        st.chat_message("assistant").write(msg["text"])
st.markdown("</div>", unsafe_allow_html=True)

if st.session_state["doc_text"]:
    user_input = st.chat_input("Enter your question...")
else:
    user_input = None

if user_input:
    if not st.session_state["doc_text"]:
        st.warning("Please upload a PDF file to provide context.")
    else:
        st.session_state["messages"].append({"role": "user", "text": user_input})
        st.chat_message("user").write(user_input)

        with st.spinner("Generating response..."):
            answer_text = call_gemini(user_input, st.session_state["doc_text"])

        st.session_state["messages"].append({"role": "assistant", "text": answer_text})
        st.chat_message("assistant").write(answer_text)

        save_qa_to_csv(user_input, answer_text)
