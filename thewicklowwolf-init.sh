#!/bin/sh

echo -e "\033[1;32mTheWicklowWolf\033[0m"
echo -e "\033[1;34mLidaTube\033[0m"
echo "Initializing app..."

cat << 'EOF'
_____________________________________

               .-'''''-.             
             .'         `.           
            :             :          
           :               :         
           :      _/|      :         
            :   =/_/      :          
             `._/ |     .'           
          (   /  ,|...-'             
           \_/^\/||__                
       _/~  `""~`"` \_               
     __/  -'/  `-._ `\_\__           
    /    /-'`  `\   \  \-.\          
_____________________________________
Brought to you by TheWicklowWolf   
_____________________________________

If you'd like to buy me a coffee:
https://buymeacoffee.com/thewicklow

EOF

echo "-----------------"
echo -e "\033[1mInstalled Versions\033[0m"
# Get the version of yt-dlp
echo -n "yt-dlp: "
pip show yt-dlp | grep Version: | awk '{print $2}'

# Get the version of ffmpeg
echo -n "FFmpeg: "
ffmpeg -version | head -n 1 | awk '{print $3}'
echo "-----------------"

PUID=${PUID:-1000}
PGID=${PGID:-1000}

echo "-----------------"
echo -e "\033[1mRunning with:\033[0m"
echo "PUID=${PUID}"
echo "PGID=${PGID}"
echo "-----------------"

# Create the required directories with the correct permissions
echo "Setting up directories.."
mkdir -p /lidatube/downloads /lidatube/config /lidatube/cache
chown -R ${PUID}:${PGID} /lidatube/downloads /lidatube/config /lidatube/cache

# Set XDG_CACHE_HOME to use the cache directory
export XDG_CACHE_HOME=/lidatube/cache

# Start the application with the specified user permissions
echo "Running LidaTube..."
exec su-exec ${PUID}:${PGID} gunicorn src.LidaTube:app -c gunicorn_config.py
