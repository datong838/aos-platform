FROM python:3.11-slim
WORKDIR /app
# Process-isolated OpenAI-compatible sidecar (LiteLLM-shaped).
# Optional: pip install litellm inside for library path; urllib→echo always works.
RUN pip install --no-cache-dir fastapi==0.115.6 uvicorn==0.34.0 pydantic==2.10.4
COPY app.py .
EXPOSE 4000
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "4000"]
