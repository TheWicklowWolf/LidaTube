![Build Status](https://github.com/TheWicklowWolf/LidaTube/actions/workflows/main.yml/badge.svg)
![Docker Pulls](https://img.shields.io/docker/pulls/thewicklowwolf/lidatube.svg)

<p align="center">
  <img src="/src/static/lidatube.png" alt="image">
</p>

<p align="center">
  Web GUI for finding and downloading missing Lidarr albums.
</p>

---

## Run using docker-compose

```yaml
version: "2.1"
services:
  lidatube:
    image: thewicklowwolf/lidatube:latest
    container_name: lidatube
    environment:
      - lidarr_address=http://192.168.1.2:8686
      - lidarr_api_key=1234567890
      - thread_limit=1
    volumes:
      - /data/media/lidatube:/lidatube/downloads
      - /etc/localtime:/etc/localtime:ro
    ports:
      - 5000:5000
    restart: unless-stopped
```

---

<p align="center">


![image](https://github.com/TheWicklowWolf/LidaTube/assets/111055425/f58062ec-4793-4b99-bc6b-67f73f232fba)



![image](https://github.com/TheWicklowWolf/LidaTube/assets/111055425/851388cc-364c-4b56-8d72-df2e75abb7fb)


</p>

---

https://hub.docker.com/r/thewicklowwolf/lidatube
