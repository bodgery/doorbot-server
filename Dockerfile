# syntax=docker/dockerfile:1
FROM python:3.13.7-trixie
ADD requirements.txt /requirements.txt
RUN pip3 install -r requirements.txt
RUN apt update
RUN apt install -y jq bsdmainutils
COPY . .


CMD [ "uwsgi", "--http-socket", ":5000", "--module", "app:app" ]
