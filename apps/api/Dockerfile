FROM python:3.11-slim

# Defines the directory for work inside the container
WORKDIR /app

# Copies requirements.txt from the projetct root to the container
COPY requirements.txt ./requirements.txt

# Install dependencies  
RUN pip install --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# Copies the content from the API and dependencies (chat_saude + agents em /app/src/agents)
COPY apps/api ./api
COPY src/agents ./src/agents
COPY src/chat_saude ./src/chat_saude
ENV PYTHONPATH=/app:/app/src

# FastAPI Door
EXPOSE 8500

# Run the API
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8500", "--reload"]