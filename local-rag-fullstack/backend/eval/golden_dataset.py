"""
Golden dataset for evaluating retrieval + generation quality.

Fill in real questions from YOUR documents. For each one:
- question: something a real user would ask
- expected_source: which file SHOULD be retrieved (helps catch retrieval bugs)
- expected_answer: a short reference answer (used for keyword-overlap scoring)

Aim for 15-30 entries covering ALL your documents, with a mix of:
- Easy factual questions (name, email, dates)
- Harder questions requiring synthesis across a paragraph
- A few questions with NO answer in your docs (to test it correctly says "I don't know")
"""

GOLDEN_DATASET = [
    {
        "question": "What is Zain's email address?",
        "expected_source": "Updated CV_ZAIN.pdf",
        "expected_answer": "zaynqureshi4200@gmail.com",
    },
    {
        "question": "What is Zain's GitHub username?",
        "expected_source": "Updated CV_ZAIN.pdf",
        "expected_answer": "Zayn-Qureshi",
    },
    {
        "question": "What problem does the Real-Time Luggage Detection system solve?",
        "expected_source": "Fall 2021_FYP_Real Time Forgotton Lugguge Detection_BSCS 21s_Morning.pdf",
        "expected_answer": "Detecting forgotten or unattended luggage in public places for security.",
    },
    {
        "question": "What is the capital of France according to the documents?",
        "expected_source": None,
        "expected_answer": "Not stated in the provided documents.",
    },
    {
        "question": "What is Zain's favorite programming language according to the documents?",
        "expected_source": None,
        "expected_answer": "Not stated in the provided documents.",
    },
    # --- Add more from your FYP report and other documents below ---
]
