"""
Email context builder — maps a role to the correct skills list and
project highlights.

Rename this file to email_composer.py and fill in your own credentials.
"""
from __future__ import annotations

_SW_SKILLS = (
    "Python, Node.js, React, Docker, SQL, AWS, etc"
)

_SW_PROJECTS = (
    "1. Example Project 1\n"
    "   • Built something awesome using X and Y.\n"
    "   • Achieved Z impact.\n\n"

    "2. Example Project 2\n"
    "   • Designed an app to do something cool.\n"
    "   • Enabled feature using cool tech.\n\n"

    "3. Example Project 3\n"
    "   • Developed a tool for a specific problem.\n"
    "   • Sent X items increasing Y."
)

_ML_SKILLS = (
    "TensorFlow, PyTorch, Scikit-learn, Pandas, LLaMA, "
    "Flask, React, Computer Vision, NLP"
)

_ML_PROJECTS = (
    "1. ML Project 1\n"
    "   • Developed a model for document-based question answering.\n"
    "   • Achieved 90%+ accuracy.\n\n"

    "2. ML Project 2\n"
    "   • Created an AI-based system that does something.\n"
    "   • Used Flask backend and distributed scraping.\n\n"

    "3. ML Project 3\n"
    "   • Automated workflows using LLMs.\n"
    "   • Tracked activity and improved efficiency."
)

def build_email_context() -> tuple[str, str, str, str]:
    """Return (sw_skills, sw_projects, ml_skills, ml_projects) strings for the LLM to choose from."""
    return _SW_SKILLS, _SW_PROJECTS, _ML_SKILLS, _ML_PROJECTS
