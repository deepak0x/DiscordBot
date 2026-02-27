FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Expose port 8080 for Cloud Run
EXPOSE 8080

# Set PORT environment variable (optional, Cloud Run injects it)
ENV PORT=8080

# Run main.py
CMD ["python", "main.py"]