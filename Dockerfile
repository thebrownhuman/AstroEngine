FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends curl unzip build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Place index is built from GeoNames dumps fetched at image build time.
# Swiss Ephemeris .se1 files are not baked in (see README) - mount a host
# ephe/ directory at runtime for full precision, or omit it to fall back to
# Moshier automatically.
RUN mkdir -p data \
    && curl -sSL -o data/cities5000.zip http://download.geonames.org/export/dump/cities5000.zip \
    && curl -sSL -o data/IN.zip http://download.geonames.org/export/dump/IN.zip \
    && curl -sSL -o data/admin1CodesASCII.txt http://download.geonames.org/export/dump/admin1CodesASCII.txt \
    && curl -sSL -o data/countryInfo.txt http://download.geonames.org/export/dump/countryInfo.txt \
    && unzip -p data/cities5000.zip cities5000.txt > data/cities5000.txt \
    && unzip -p data/IN.zip IN.txt > data/IN.txt \
    && rm data/cities5000.zip data/IN.zip \
    && python -m astro_engine.places build \
    && rm data/cities5000.txt data/IN.txt

ENV SE_EPHE_PATH=/app/ephe
EXPOSE 8000

CMD ["uvicorn", "astro_engine.api:app", "--host", "0.0.0.0", "--port", "8000"]
