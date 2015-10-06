FROM ubuntu:14.04

WORKDIR /root

# sys deps
RUN apt-get update
RUN apt-get -y install gcc g++ make cmake git-core git-core
RUN apt-get -y install python-dev python-pip
RUN apt-get -y install libevent-dev libev-dev

# python deps
RUN pip install gevent

# sdk
RUN git clone git://github.com/couchbase/libcouchbase.git
RUN mkdir libcouchbase/build
WORKDIR libcouchbase/build
RUN ../cmake/configure --prefix=/usr
RUN make
RUN make install
WORKDIR /root
RUN pip install git+git://github.com/couchbase/couchbase-python-client

# src
RUN git clone https://github.com/couchbaselabs/gideon.git
WORKDIR gideon

