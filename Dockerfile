FROM python:3.10-alpine

COPY requirements.txt /tmp/requirements.txt

RUN apk update \
 && apk add --no-cache --virtual build-deps gcc g++ python3-dev musl-dev \
 && apk add --no-cache postgresql postgresql-dev mariadb-connector-c-dev \
 && pip install --no-cache-dir --upgrade uvicorn \
 && pip install --no-cache-dir psycopg2==2.9.3 mysqlclient==2.1.1 pysqlite3==0.4.7 \
 && pip install --no-cache-dir -r /tmp/requirements.txt \
 && apk del build-deps

COPY app /app

HEALTHCHECK --start-period=30s --interval=10s --timeout=5s --retries=3 CMD curl --fail http://localhost/status || exit 1
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "443", "--app-dir", "/app", "--proxy-headers"]
