# BRAIN has zero pip dependencies for its core, so the image only needs
# Python itself. Optional extras (faster-whisper for the microphone) can
# still be installed later, the same way the Windows UI offers to.
FROM python:3.12-slim

WORKDIR /app

# Only copy what the program actually needs to run, so edits elsewhere on
# your machine don't force a full rebuild and no dev-only files end up in
# the image (see .dockerignore).
COPY brain/ brain/
COPY main.py pyproject.toml ./

# BRAIN keeps all its data under this folder; mount a volume here (see
# docker-compose.yml) so your pantry, chat history, backups, etc. survive
# container rebuilds and upgrades.
ENV BRAIN_DATA=/data
VOLUME ["/data"]

# Only reachable from inside the Docker network by default; map the port
# in docker-compose.yml (or `docker run -p`) to reach it from your LAN.
ENV BRAIN_HOST=0.0.0.0
EXPOSE 8765

# No browser inside a container; open the URL yourself once it's running.
CMD ["python3", "main.py", "--web", "--no-browser"]
