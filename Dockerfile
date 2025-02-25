FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install debugpy

COPY settings.conf /root/.config/pyopensky/settings.conf
COPY flight_tracker/ flight_tracker/

VOLUME /data

CMD ["python", "-m", "debugpy", "--listen", "0.0.0.0:5678", "-m", "flight_tracker"]