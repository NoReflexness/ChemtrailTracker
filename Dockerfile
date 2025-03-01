FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN apt-get update && apt-get install -y libpq-dev && rm -r /var/lib/apt/lists/*

COPY settings.conf /root/.config/pyopensky/settings.conf
COPY flight_tracker/ flight_tracker/

VOLUME /data

CMD ["gunicorn", "--worker-class", "eventlet", "-w", "1", "--timeout", "120", "--bind", "0.0.0.0:5000", "flight_tracker.__main__:app"]