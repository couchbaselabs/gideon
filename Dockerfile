# docker build -t ubuntu1604py36
FROM python:3.8

RUN apt-get update  --fix-missing
RUN apt-get install -y software-properties-common vim wget git
RUN apt-get update

RUN apt-get install -y python3-dev python3-pip python3-setuptools cmake build-essential

# update pip
RUN python3.8 -m pip install pip --upgrade
RUN python3 -m pip install --upgrade pip setuptools wheel

#sdk
RUN python3.8 -m pip install couchbase==3.0.6
RUN python3.8 -m pip install pyyaml gevent requests eventlet httplib2

RUN mkdir gideon
COPY . gideon/
WORKDIR gideon
ENTRYPOINT ["python3.8","gideon.py"]