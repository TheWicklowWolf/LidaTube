![Build Status](https://github.com/TheWicklowWolf/LidaTube/actions/workflows/main.yml/badge.svg)
![Docker Pulls](https://img.shields.io/docker/pulls/thewicklowwolf/lidatube.svg)

<p align="center">

  ![lidatube](https://github.com/TheWicklowWolf/LidaTube/assets/111055425/81b23a80-a42e-41b4-9acc-6072692620da)

</p>

Web GUI for adding missing Lidarr albums to metube.


## Run using docker-compose

```yaml
version: "2.1"
services:
  huntorr:
    image: thewicklowwolf/lidatube:latest
    container_name: lidatube
    environment:
      - lidarr_address=http://192.168.1.2:8686
      - lidarr_api_key=1234567890
      - metube_address=http://192.168.1.2:8080
    ports:
      - 5000:5000
    restart: unless-stopped
```

---
https://hub.docker.com/r/thewicklowwolf/lidatube
