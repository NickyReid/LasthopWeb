# syntax=docker/dockerfile:1
FROM ubuntu:latest

RUN apt-get update \
  && apt-get install -y python3-pip \
  && cd /usr/local/bin \
  && ln -s /usr/bin/python3 python \
  && pip3 install --upgrade pip

WORKDIR /LasthopWeb

COPY requirements.txt requirements.txt
RUN pip3 install -r requirements.txt

COPY . .

EXPOSE 8080

CMD [ "python3", "app.py"]