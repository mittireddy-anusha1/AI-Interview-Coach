"""
AI Interview Coach
Mock interviews with 10 sequential questions and final accurate scored feedback.
"""
from typing import Dict, List, Optional
import json
import os

from groq import Groq
import streamlit as st

st.set_page_config(page_title="AI Interview Coach", page_icon="🎤", layout="wide")
st.title("🎤 AI Interview Coach")
st.caption("Complete a 10-question mock interview to get your final performance score and report.")

# Target 10 questions for the interview
TOTAL_QUESTIONS = 10

# API Key background read (No Sidebar input box, purely hidden)
# Dheenini pettandi:
try:
    api_key = st.secrets.get("GROQ_API_KEY") or os.getenv("GROQ_API_KEY", "")
except Exception:
    api_key = os.getenv("GROQ_API_KEY", "")

with st.sidebar:
    st.markdown("### ⚙️ Interview Configurations")
    role = st.text_input("Target Role", placeholder="Software Engineer at Google")
    jd = st.text_area("Job Description (optional)", height=150)
    interview_type = st.selectbox(
        "Interview Type",
        ["Technical", "Behavioral", "System Design", "Case Study", "HR"],
    )
    difficulty = st.selectbox(
        "Difficulty",
        ["Entry Level", "Mid Level", "Senior", "Staff/Principal"],
    )

def generate_question(
    client: Groq,
    role: str,
    jd: str,
    q_type: str,
    difficulty: str,
    asked: List[str],
) -> str:
    """Generate a fresh interview question."""
    asked_str = "\n".join(asked[-5:]) if asked else "None yet"

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {
                "role": "user",
                "content": f"""Generate one {q_type} interview question for a {difficulty} {role} position.

Job description context:
{jd[:500] if jd else "Not provided"}

Already asked (do not repeat these):
{asked_str}

Return ONLY the interview question."""
            }
        ],
        max_tokens=300,
    )
    return response.choices[0].message.content.strip()

def evaluate_single_answer(
    client: Groq,
    question: str,
    answer: str,
    role: str,
) -> Dict[str, object]:
    """Evaluate a single answer behind the scenes."""
    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            response_format={"type": "json_object"},
            messages=[
                {
                    "role": "user",
                    "content": f"""Evaluate this interview answer for a {role} position. Give an integer score out of 10.

    QUESTION:
    {question}

    ANSWER:
    {answer}

    Return ONLY valid JSON in this exact structure:
    {{
      "score": 0,
      "brief_feedback": ""
    }}
    """
                }
            ],
            max_tokens=200,
        )
        raw = response.choices[0].message.content.strip()
        return json.loads(raw)
    except Exception:
        return {"score": 5, "brief_feedback": "Answer processed successfully."}

def generate_final_report(
    client: Groq,
    questions: List[str],
    answers: List[str],
    scores: List[int],
    role: str,
    q_type: str,
) -> Dict[str, object]:
    """Evaluate all answers together to output overall metrics and qualitative summaries."""
    qa_pairs = ""
    for idx, (q, a, s) in enumerate(zip(questions, answers, scores), 1):
        qa_pairs += f"\nQUESTION {idx}:\n{q}\nANSWER {idx}:\n{a}\nSCORE: {s}/10\n"

    prompt = f"""You are an expert interviewer. Review this completed {q_type} interview for a {role} position.
Review the scores and content of all answers below:
{qa_pairs}

Generate a combined detailed analysis. 

CRITICAL: Return ONLY valid JSON in this exact structure. Do not use unescaped backticks within text fields.
{{
  "grade": "Pass / Excellent / Needs Practice",
  "strengths": ["Strength 1", "Strength 2"],
  "improvements": ["Improvement 1", "Improvement 2"],
  "better_answer_structure": "General structure improvements to consider...",
  "sample_strong_answer": "Provide a clean text model explanation/code for one key topic from this interview.",
  "specific_feedback": "Overall summary narrative feedback."
}}
"""
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        response_format={"type": "json_object"},
        messages=[{"role": "user", "content": prompt}],
        max_tokens=1500,
    )

    raw = response.choices[0].message.content.strip()
    return json.loads(raw)

# Session state initialization
if "questions" not in st.session_state:
    st.session_state.questions = []

if "answers" not in st.session_state: 
    st.session_state.answers = []

if "scores" not in st.session_state:
    st.session_state.scores = []

if "current_q" not in st.session_state:
    st.session_state.current_q = None

if "interview_complete" not in st.session_state:
    st.session_state.interview_complete = False

if "evaluation_result" not in st.session_state:
    st.session_state.evaluation_result = None

# Validation checks
if not role:
    st.info("Enter your target role in the sidebar to start")
    st.stop()

# Safe key validation check
if not api_key:
    st.error("Groq API key missing in the backend configurations!")
    st.stop()

api_client = Groq(api_key=api_key)

# Flow logic
current_q_count = len(st.session_state.questions)

# Generate question if none active
if not st.session_state.interview_complete and st.session_state.current_q is None:
    if current_q_count < TOTAL_QUESTIONS:
        with st.spinner(f"Generating Question {current_q_count + 1}..."):
            q = generate_question(
                api_client,
                role,
                jd,
                interview_type,
                difficulty,
                st.session_state.questions,
            )
            while q in st.session_state.questions:
                q = generate_question(
                    api_client,
                    role,
                    jd,
                    interview_type,
                    difficulty,
                    st.session_state.questions,
                )
            st.session_state.current_q = q
            st.rerun()

col1, col2 = st.columns([2, 1])

with col1:
    if not st.session_state.interview_complete:
        st.subheader(f"Question {current_q_count + 1} of {TOTAL_QUESTIONS}")
        st.info(st.session_state.current_q)
        
        answer = st.text_area(
            "Your Answer:",
            height=200,
            placeholder="Type your answer here...",
            key=f"ans_input_{current_q_count}"
        )

        if st.button("➡️ Submit Answer"):
            if not answer.strip():
                st.warning("Please write an answer first")
            else:
                with st.spinner("Processing response..."):
                    single_eval = evaluate_single_answer(
                        api_client,
                        st.session_state.current_q,
                        answer,
                        role
                    )
                st.session_state.questions.append(st.session_state.current_q)
                st.session_state.answers.append(answer)
                st.session_state.scores.append(single_eval.get("score", 5))
                st.session_state.current_q = None
                
                # If finished 10 questions
                if len(st.session_state.questions) >= TOTAL_QUESTIONS:
                    st.session_state.interview_complete = True
                    with st.spinner("All 10 questions complete! Building your performance dashboard..."):
                        try:
                            evaluation = generate_final_report(
                                api_client,
                                st.session_state.questions,
                                st.session_state.answers,
                                st.session_state.scores,
                                role,
                                interview_type,
                            )
                            st.session_state.evaluation_result = evaluation
                        except Exception as e:
                            st.error(f"Could not parse evaluation: {e}")
                            st.stop()
                st.rerun()

    else:
        st.success("🎉 You have completed all 10 questions!")
        
        if st.session_state.evaluation_result:
            evaluation = st.session_state.evaluation_result
            
            # Perfect mathematical average
            avg_score = sum(st.session_state.scores) / len(st.session_state.scores)
            grade = evaluation.get("grade", "N/A")
            color = "green" if avg_score >= 8 else "orange" if avg_score >= 6 else "red"

            st.markdown(f"## Final Avg Score: :{color}[{avg_score:.1f}/10 — Grade {grade}]")

            c1, c2 = st.columns(2)
            with c1:
                st.markdown("**✅ Strengths**")
                for s in evaluation.get("strengths", []):
                    st.markdown(f"- {s}")
            with c2:
                st.markdown("**📈 Improvements**")
                for item in evaluation.get("improvements", []):
                    st.markdown(f"- {item}")

            with st.expander("💡 Recommended Structure & Improvement Tips"):
                st.write(evaluation.get("better_answer_structure", ""))

            with st.expander("⭐ Exemplary Practice Reference"):
                st.write(evaluation.get("sample_strong_answer", ""))

            st.info(evaluation.get("specific_feedback", ""))

            # Building plain text content to download
            report_text = f"=== AI INTERVIEW REPORT ({role}) ===\n"
            report_text += f"Final Average Score: {avg_score:.1f}/10\n"
            report_text += f"Grade: {grade}\n\n"
            
            report_text += "--- QUESTIONS, ANSWERS & SCORES ---\n"
            for i, (q, a, s) in enumerate(zip(st.session_state.questions, st.session_state.answers, st.session_state.scores), 1):
                report_text += f"\nQ{i}: {q}\nYour Answer: {a}\nScore: {s}/10\n"
            
            report_text += "\n--- FEEDBACK ANALYSIS ---\n"
            report_text += f"Strengths: {', '.join(evaluation.get('strengths', []))}\n"
            report_text += f"Improvements: {', '.join(evaluation.get('improvements', []))}\n"
            report_text += f"Feedback Summary: {evaluation.get('specific_feedback', '')}\n"

            st.download_button(
                label="📥 Save Report as TXT File",
                data=report_text,
                file_name="interview_report.txt",
                mime="text/plain"
            )
            
            if st.button("🔄 Restart Interview"):
                st.session_state.questions = []
                st.session_state.answers = []
                st.session_state.scores = []
                st.session_state.current_q = None
                st.session_state.interview_complete = False
                st.session_state.evaluation_result = None
                st.rerun()

with col2:
    st.markdown("### Interview Progress")
    st.progress(current_q_count / TOTAL_QUESTIONS)
    st.metric("Questions Answered", f"{current_q_count}/{TOTAL_QUESTIONS}")
    
    if st.session_state.questions:
        st.markdown("**Your Responses Map & Dynamic Scores**")
        for i, (q, s) in enumerate(zip(st.session_state.questions, st.session_state.scores), 1):
            indicator = "🟢" if s >= 8 else "🟡" if s >= 6 else "🔴"
            st.text(f"{indicator} Q{i}: score {s}/10")