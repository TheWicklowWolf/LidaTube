FROM python:3.11-slim
RUN apt-get update && apt-get install -y \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*
COPY . /lidatube
WORKDIR /lidatube
RUN pip install -r requirements.txt
EXPOSE 5000
CMD ["gunicorn","src.LidaTube:app", "-c", "gunicorn_config.py"]