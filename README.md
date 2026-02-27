# Telegram Outreach Bot

A Telegram bot for automating cold outreach emails. It crafts highly tailored, personalized emails using LLMs (Gemini, OpenAI, or OpenRouter), automatically selects the best matching resume based on the job description, and provides a preview/edit interface inside Telegram before sending.

---

## Features

- **Telegram Interface:** Interact with the bot using commands like `/email` and `/batch_email`.
- **Intelligent Email Generation:** Uses advanced LLMs to identify the target role (e.g., Software Engineering vs Machine Learning) and crafts a dense, highly personalized email.
- **Dynamic Resume Attachment:** Automatically chooses the correct resume PDF to attach based on the LLM's role inference.
- **Inline Editing:** Before sending, preview the generated email and click "Edit" to dynamically adjust the text natively inside Telegram.
- **Provider Switching:** Jump between LLM endpoints (`/provider`) and configure custom API keys (`/setkey`) directly from chat.
- **Batch Processing:** Send an entire campaign of emails by uploading a CSV.
- **MongoDB Tracking:** Tracks the number of emails sent by each user.

---

## Setup

### 1. Clone the Repository

```sh
git clone https://github.com/deepak0x/DiscordBot.git
cd DiscordBot
```

### 2. Configure Personal Details

For privacy, personal data is not stored in Git. You must copy the example templates and fill in your own information:

```sh
cp config.example.py config.py
cp utils/email_composer.example.py utils/email_composer.py
```

- Edit `config.py` to add your Name, LinkedIn, GitHub, etc.
- Edit `utils/email_composer.py` to add your Software Developer / Data Scientist skills and projects.

### 3. Environment Variables

Create a `.env` file in the root directory:

```env
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
SMTP_EMAIL=your_gmail_address@gmail.com
SMTP_PASSWORD=your_gmail_app_password
MONGODB_URI=your_mongodb_connection_string

# Optional (Can also be set via Telegram commands)
GEMINI_API_KEY=your_gemini_api_key
OPENAI_API_KEY=your_openai_api_key
OPENROUTER_API_KEY=your_openrouter_api_key
```

### 4. Prepare Resumes

Place your resume PDFs in the `resumes/` directory. By default, the bot looks for:
- `resumes/Deepak_Bhagat_Software_Engineer_Resume.pdf`
- `resumes/Deepak_Bhagat_Data_Science_Resume.pdf`

*(You can change these mapping filenames inside `utils/role_inference.py`)*

---

## Usage (Docker)

The easiest way to run the bot is with Docker Compose.

```sh
docker compose build
docker compose up -d
```

---

## Commands

Once running, send a message to your bot on Telegram:
- `/start` or `/help` — Show the welcome message.
- `/email` — Start drafting a new outreach email manually.
- `/batch_email` — Upload a CSV to bulk-generate and send emails.
- `/provider` — Toggle active LLM (Gemini, OpenAI, OpenRouter).
- `/setkey <provider> <key>` — Save a custom API key for an LLM endpoint.
- `/health` — Ping the server.
- `/cancel` — Unload your current state.

### How to use `/email`
1. Type `/email`.
2. Paste the target Recruiter Email and the Job Description into the chat.
3. The AI generates the subject and body, and chooses the resume.
4. An inline keyboard appears. You can hit **Send**, **Edit**, or **Cancel**.

---

## Developer Requirements

If not using Docker, you can run locally:

```sh
pip install -r requirements.txt
python main.py
```