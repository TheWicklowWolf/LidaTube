#!/bin/bash

# Clean codec testing script
CODEC=$1
PORT=$2
LIDARR_API_KEY=$3
LIDARR_HOST=$4

if [ -z "$CODEC" ] || [ -z "$PORT" ] || [ -z "$LIDARR_API_KEY" ] || [ -z "$LIDARR_HOST" ]; then
    echo "Usage: ./test_codec_clean.sh <codec> <port> <lidarr_api_key> <lidarr_host>"
    echo "Example: ./test_codec_clean.sh opus 5645 1234567890 192.168.1.25"
    exit 1
fi

echo "Remember to build the container before running this script!"

echo "🧹 Cleaning up previous test..."
docker stop lidatube-test 2>/dev/null
docker rm lidatube-test 2>/dev/null
docker volume rm lidatube-${CODEC}-test-config 2>/dev/null
docker volume rm lidatube-${CODEC}-test-downloads 2>/dev/null

echo "📦 Creating fresh volumes..."
docker volume create lidatube-${CODEC}-test-config
docker volume create lidatube-${CODEC}-test-downloads

echo "🚀 Starting clean container for ${CODEC} on port ${PORT}..."
docker run -d \
  --name lidatube-test \
  -p ${PORT}:5000 \
  -v lidatube-${CODEC}-test-config:/lidatube/config:rw \
  -v lidatube-${CODEC}-test-downloads:/lidatube/downloads:rw \
  -e preferred_codec=${CODEC} \
  -e lidarr_address=http://${LIDARR_HOST}:8686 \
  -e lidarr_api_key=${LIDARR_API_KEY} \
  lidatube-test

echo "✅ Lidatube ready! Access at http://localhost:${PORT}"
echo "🔍 To check every file in the downloads folder: docker exec lidatube-test find /lidatube/downloads -type f"
echo "🔍 To check for specific files with the extension ${CODEC}: docker exec lidatube-test find /lidatube/downloads -name "*.${CODEC}" | wc -l"
echo "🛑 To stop the test container either run: docker stop lidatube-test && docker rm lidatube-test"
echo "or start a new run with the same command, it will automatically stop the old one"
echo ""
echo "📋 Do you want to check the logs? (y/n)"
read -n 1 -s check_logs
echo ""
if [ "$check_logs" = "y" ]; then
    docker logs -f lidatube-test
fi