FROM python:3.12-alpine

# Set build arguments
ARG RELEASE_VERSION
ENV RELEASE_VERSION=${RELEASE_VERSION}

# Install ffmpeg and su-exec
RUN apk update && apk add --no-cache ffmpeg su-exec deno

# Create directories and set permissions
COPY . /lidatube
WORKDIR /lidatube

# Install requirements
ENV PYTHONPATH=/lidatube/src
RUN pip install --no-cache-dir -r requirements.txt

# Make the script executable
RUN chmod +x thewicklowwolf-init.sh

# Expose port
EXPOSE 5000

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD wget -q --spider http://localhost:5000/ || exit 1

# Start the app
ENTRYPOINT ["./thewicklowwolf-init.sh"]

