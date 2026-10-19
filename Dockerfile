FROM python:3.11-slim
RUN useradd --create-home --uid 10001 agent
WORKDIR /app
COPY . .
USER agent
ENTRYPOINT ["python", "agent.py"]
