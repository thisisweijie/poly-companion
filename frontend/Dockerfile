FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app.py .
# Copy the templates folder so Jinja2 can find index.html at runtime
COPY templates/ templates/
EXPOSE 7862
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "7862"]
