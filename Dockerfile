FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
# Install CPU-only torch first to avoid pulling multi-GB CUDA packages
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
ENV PYTHONPATH=/app/src
CMD ["streamlit", "run", "apps/ui/app.py", "--server.address=0.0.0.0"]