FROM python:3.11-slim
WORKDIR /app
# 157 · true Jupyter Notebook 7 MVP (Dev only; not customer package)
COPY requirements-jupyter.txt .
RUN pip install --no-cache-dir -r requirements-jupyter.txt
COPY app.py .
RUN mkdir -p /notebooks
ENV AOS_ANALYTICS_ENGINE=jupyter \
    AOS_JUPYTER_ROOT=/notebooks \
    AOS_JUPYTER_PORT=8888 \
    AOS_JUPYTER_PUBLIC_URL=http://127.0.0.1:8888 \
    AOS_ANALYTICS_PUBLIC_URL=http://127.0.0.1:8084
EXPOSE 8084 8888
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8084"]
