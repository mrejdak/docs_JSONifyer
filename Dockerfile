# Środowisko uruchomieniowe Odwołania2JSON: Python 3.13 + Tesseract 5 + zależności.
# Kod, konfiguracja, model OCR (models/tessdata) i .env NIE są kopiowane do obrazu — docker-compose.yml
# montuje katalog projektu (/opt/solution) jako /app. Zmiana kodu/configu nie wymaga przebudowy obrazu;
# przebudowa (docker compose build) tylko po zmianie requirements.txt albo tego pliku.
FROM python:3.13-slim-trixie

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONIOENCODING=utf-8 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Tesseract (Debian trixie: 5.5). Model rozpoznawania (tessdata_best, pol) jest w repozytorium:
# models/tessdata/pol.traineddata — config/settings.yaml, ocr.tessdata_dir.
RUN apt-get update \
 && apt-get install -y --no-install-recommends tesseract-ocr \
 && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /tmp/requirements.txt
RUN pip install -r /tmp/requirements.txt \
 && python -c "import cv2, numpy, pymupdf, rapidfuzz, yaml; print('zależności OK')" \
 && tesseract --version

WORKDIR /app
CMD ["python", "-m", "odw2json", "run", "--input", "input", "--output", "output"]
