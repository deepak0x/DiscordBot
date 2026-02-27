"""
Unified LLM service — generates personalised outreach email content via the
user's selected provider (Gemini, OpenAI, or OpenRouter).
Supports fallback to environment variables if the user hasn't set custom keys.
"""
from __future__ import annotations

import logging

import aiohttp
import openai

import config
from bot.db import get_user_settings

logger = logging.getLogger(__name__)

_GEMINI_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    "gemini-2.5-flash:generateContent?key={key}"
)

def _build_prompt(
    to_email: str,
    message: str,
    sw_skills: str,
    sw_projects: str,
    ml_skills: str,
    ml_projects: str,
) -> str:
    profile = config.PROFILE
    return (
        "You are an expert assistant for writing highly professional, concise, "
        "and attention-grabbing cold emails for LinkedIn outreach. "
        "Your goal is to maximise the chance of a positive response from HR. "
        "Carefully analyse the user's message to extract the company name, role, "
        "required skills, preferred subject line, and any specific instructions.\n\n"
        "First, you MUST classify the target role based on the job description. "
        "Choose EXACTLY ONE of the following precise strings that best describes the role:\n"
        "- 'software developer' (For: SDE, SWE, Backend, Frontend, Fullstack, App Development, etc)\n"
        "- 'machine learning' (For: ML, Data Science, AI, Computer Vision, LLMs, NLP, Data Analysis, etc)\n\n"
        "Depending on your classification, strictly use ONLY the corresponding skills and projects below:\n"
        f"Option A (If you chose 'software developer'):\n  Skills: {sw_skills}\n  Projects:\n{sw_projects}\n\n"
        f"Option B (If you chose 'machine learning'):\n  Skills: {ml_skills}\n  Projects:\n{ml_projects}\n\n"
        f"Write an email (under 200 words) that:\n"
        f"- Starts with: 'Hi,' on the first line.\n"
        f"- Introduces the user: 'I am {profile['name']}, a {profile['year']} "
        f"student at {profile['university']}.'\n"
        "- Expresses enthusiasm for the specific role and company by name.\n"
        "- Highlights 2-3 relevant skills from your chosen set.\n"
        "- Briefly describes three relevant projects from your chosen set (technologies, purpose, impact).\n"
        "- Includes this experience naturally:\n"
        "    • Software Engineer Intern at Eve: 12+ REST APIs with DRF, GCP backend, ML collaboration.\n"
        "    • Mobile Developer Intern at Region Infinity: Flutter + Node.js app, role-based admin dashboard.\n"
        "    • Freelance data analyst: insights and automated reporting from complex datasets.\n"
        "- Generates a highly professional, strong, and concise subject line (e.g., 'Software Engineering Intern Application - Deepak Bhagat' or 'Deepak Bhagat - Backend Developer Role'). Do NOT use generic subjects like 'Reaching out' or 'Inquiry'.\n"
        "- Ends with: 'I'd appreciate the opportunity for a short call or interview.'\n"
        "- Does NOT include the sender's name in the closing.\n"
        "Details:\n"
        f"- Recipient Email: {to_email}\n"
        f"- User Message: {message}\n\n"
        "Return ONLY in this strict format:\n"
        "Role: {the exact role string you chose}\n"
        "Subject: {subject}\n"
        "{body}"
    )

async def _call_gemini(api_key: str, prompt: str) -> str:
    url = _GEMINI_URL.format(key=api_key)
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.7},
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=payload) as resp:
            resp.raise_for_status()
            result = await resp.json()

    try:
        return result["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError) as exc:
        raise RuntimeError(f"Unexpected Gemini response: {result}") from exc

async def _call_openai_compatible(api_key: str, prompt: str, is_openrouter: bool = False) -> str:
    if is_openrouter:
        client = openai.AsyncOpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=api_key,
        )
        model = "google/gemini-2.5-flash"  # Default fallback model on OpenRouter
    else:
        client = openai.AsyncOpenAI(api_key=api_key)
        model = "gpt-4o-mini"
        
    response = await client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7,
    )
    return response.choices[0].message.content

async def generate_email(
    user_id: str,
    to_email: str,
    message: str,
    sw_skills: str,
    sw_projects: str,
    ml_skills: str,
    ml_projects: str,
) -> tuple[str, str, str]:
    """
    Call the user's active LLM provider and return (role, subject, body).
    Raises Exception on API or parse errors.
    """
    settings = get_user_settings(user_id)
    provider = settings["active_provider"]
    user_keys = settings["keys"]

    prompt = _build_prompt(to_email, message, sw_skills, sw_projects, ml_skills, ml_projects)
    
    try:
        if provider == "openai":
            api_key = user_keys.get("openai") or config.OPENAI_API_KEY
            if not api_key:
                raise ValueError("OpenAI API key not configured. Use /setkey openai <key>.")
            text = await _call_openai_compatible(api_key, prompt, is_openrouter=False)
            
        elif provider == "openrouter":
            api_key = user_keys.get("openrouter") or config.OPENROUTER_API_KEY
            if not api_key:
                raise ValueError("OpenRouter API key not configured. Use /setkey openrouter <key>.")
            text = await _call_openai_compatible(api_key, prompt, is_openrouter=True)
            
        else: # Default gemini
            api_key = user_keys.get("gemini") or config.GEMINI_API_KEY
            if not api_key:
                raise ValueError("Gemini API key not configured. Use /setkey gemini <key>.")
            text = await _call_gemini(api_key, prompt)

    except Exception as exc:
        logger.exception("Failed to call LLM API for provider %s", provider)
        raise RuntimeError(f"LLM Error ({provider}): {str(exc)}") from exc

    logger.debug("Raw output (%s): %s", provider, text[:120])

    # Parse output: Role, Subject, Body
    lines = text.strip().splitlines()
    role_line = next((line for line in lines if line.lower().startswith("role:")), None)
    subject_line = next((line for line in lines if line.lower().startswith("subject:")), None)
    
    if not role_line or not subject_line:
        # Fallback if LLM formatting is weird
        inferred_role = "software developer"
        subject = subject_line.replace("Subject: ", "", 1).strip() if subject_line else "Application - Deepak Bhagat"
        body = text.strip()
    else:
        inferred_role = role_line.replace("Role: ", "", 1).strip()
        subject = subject_line.replace("Subject: ", "", 1).strip()
        # Find index of subject line to extract everything after it as the body
        subject_idx = lines.index(subject_line)
        body = "\n".join(lines[subject_idx + 1:]).strip()

    body += config.SIGNATURE

    return inferred_role, subject, body
