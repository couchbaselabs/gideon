# docker build -t ubuntu1604py36
FROM ubuntu:16.04

RUN apt-get update  --fix-missing
RUN apt-get install -y software-properties-common vim wget git
RUN add-apt-repository ppa:jonathonf/python-3.6
RUN apt-get update

RUN apt-get install -y build-essential python3.6 python3.6-dev python3-pip python3.6-venv

# update pip
RUN python3.6 -m pip install pip --upgrade
RUN python3.6 -m pip install wheel

# sdk
RUN wget http://packages.couchbase.com/releases/couchbase-release/couchbase-release-1.0-6-amd64.deb
RUN dpkg -i couchbase-release-1.0-6-amd64.deb
RUN python3.6 -m pip install couchbase==3.0.0a4
RUN python3.6 -m pip install pyyaml gevent requests eventlet

RUN mkdir gideon
COPY . gideon/
WORKDIR gideon
ENTRYPOINT ["python3.6","gideon.py"]