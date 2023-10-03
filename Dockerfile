FROM python:3.11-slim
COPY . /lidatube
WORKDIR /lidatube
RUN pip install -r requirements.txt
EXPOSE 5000
CMD ["gunicorn","src.lidatube:app", "-c", "gunicorn_config.py"]