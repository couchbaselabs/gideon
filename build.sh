pushd .

apt-get update
apt-get -y install gcc g++ make cmake git-core git-core
apt-get -y install python-dev python-pip
apt-get -y install libevent-dev libev-dev

# python deps
pip install gevent

# sdk
git clone git://github.com/couchbase/libcouchbase.git
mkdir libcouchbase/build
cd libcouchbase/build
../cmake/configure --prefix=/usr
make -j4
make install
cd /root
pip install git+git://github.com/couchbase/couchbase-python-client
pip install pyyaml

popd
