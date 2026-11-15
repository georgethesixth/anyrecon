# anyrecon · Server edition
# Build from the repository root:  docker build -f editions/server/Dockerfile -t anyrecon .
FROM python:3.13-slim
RUN apt-get update && apt-get install -y --no-install-recommends tesseract-ocr \
 && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY pyproject.toml README.md app.py ui_theme.py ./
COPY .streamlit ./.streamlit
COPY static ./static
COPY anyrecon ./anyrecon
COPY examples/__init__.py examples/generate_samples.py ./examples/
RUN pip install --no-cache-dir ".[ui,ocr]" && useradd --system --uid 10001 anyrecon
USER anyrecon
ENV ANYRECON_EDITION=server \
    STREAMLIT_SERVER_HEADLESS=true \
    STREAMLIT_BROWSER_GATHER_USAGE_STATS=false \
    STREAMLIT_SERVER_MAX_UPLOAD_SIZE=200 \
    HOME=/tmp
EXPOSE 8501
HEALTHCHECK --interval=30s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8501/_stcore/health')"
CMD ["streamlit", "run", "app.py", "--server.address=0.0.0.0", "--server.port=8501"]
