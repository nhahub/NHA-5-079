FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONIOENCODING=utf-8 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

# code only: no .env, no data, no results (those are mounted at run time)
COPY src/extract_crime.py src/merge_results.py ./

ENTRYPOINT ["python", "extract_crime.py"]