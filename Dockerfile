FROM python:3.11-slim
ARG UID=1000
ARG GID=1000
RUN groupadd -g $GID general_user && \
    useradd -m -u $UID -g $GID -s /bin/bash general_user
RUN apt-get update && apt-get install -y \
    ffmpeg && \
    rm -rf /var/lib/apt/lists/*
COPY . /lidatube
WORKDIR /lidatube
RUN mkdir -p /lidatube/downloads
RUN chown -R $UID:$GID /lidatube
RUN chmod -R 777 /lidatube/downloads
RUN pip install -r requirements.txt
EXPOSE 5000
USER general_user
CMD ["gunicorn", "src.LidaTube:app", "-c", "gunicorn_config.py"]