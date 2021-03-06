# syntax=docker/dockerfile:1
FROM python:3.9.5
ADD requirements.txt /requirements.txt
RUN pip3 install -r requirements.txt
COPY . .


CMD [ "uwsgi", "--http-socket", ":5000", "--module", "app:app" ]
