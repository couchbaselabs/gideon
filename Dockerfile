FROM ubuntu:16.04

WORKDIR /root

# sys deps
RUN apt-get update
RUN apt-get -y install gcc g++ make cmake git-core git-core wget lsb-release
RUN apt-get -y install python-dev python-pip
RUN apt-get -y install libevent-dev libev-dev

# python deps
RUN pip install gevent

# sdk
RUN wget http://packages.couchbase.com/releases/couchbase-release/couchbase-release-1.0-4-amd64.deb
RUN dpkg -i couchbase-release-1.0-4-amd64.deb
RUN apt-get update
RUN apt-get -y install libcouchbase-dev libcouchbase2-bin build-essential

WORKDIR /root
RUN pip install git+git://github.com/couchbase/couchbase-python-client
RUN pip install pyyaml
RUN pip install eventlet

# src
RUN git clone https://github.com/couchbaselabs/gideon.git
WORKDIR gideon

COPY spec.yaml spec.yaml
CMD python gideon.py kv --spec spec.yaml
