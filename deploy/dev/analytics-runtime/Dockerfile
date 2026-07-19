FROM python:3.11-slim
WORKDIR /app
# Process-isolated analytics-runtime (shaped). Real Jupyter/Notebook7 later via profile.
RUN pip install --no-cache-dir fastapi==0.115.6 uvicorn==0.34.0
COPY app.py .
EXPOSE 8084
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8084"]
