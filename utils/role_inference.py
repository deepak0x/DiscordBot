"""
Role inference — maps the LLM-chosen role string to the correct resume file.
"""

# Resume paths keyed by role
_RESUME_MAP = {
    "software developer": "resumes/Deepak_Bhagat_Software_Engineer_Resume.pdf",
    "machine learning":   "resumes/Deepak_Bhagat_Data_Science_Resume.pdf",
}

def get_resume_path(role: str) -> str | None:
    """Return the filesystem path for the resume matching *role*, or None."""
    for key, path in _RESUME_MAP.items():
        if key in role.lower():
            return path
    return None
