FROM python:3.12-alpine

# Set build arguments
ARG RELEASE_VERSION
ENV RELEASE_VERSION=${RELEASE_VERSION}

# Create User
ARG UID=1000
ARG GID=1000
RUN addgroup -g $GID general_user && \
    adduser -D -u $UID -G general_user -s /bin/sh general_user

# Install ffmpeg
RUN apk update && apk add --no-cache ffmpeg

# Create directories and set permissions
COPY . /lidatube
WORKDIR /lidatube
RUN mkdir -p /lidatube/downloads
RUN chown -R $UID:$GID /lidatube
RUN chmod -R 777 /lidatube/downloads

# Install requirements and run code as general_user
ENV PYTHONPATH /lidatube/src
RUN pip install --no-cache-dir -r requirements.txt
EXPOSE 5000
USER general_user
CMD ["gunicorn", "src.LidaTube:app", "-c", "gunicorn_config.py"]
