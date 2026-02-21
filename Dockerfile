FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TOOL_STUDIO_MODE=demo \
    TOOL_STUDIO_TLS=0 \
    PORT=8080

COPY . /app

RUN mkdir -p /tmp/tool-studio-artifacts

EXPOSE 8080

CMD ["python", "tool_studio_server.py"]
