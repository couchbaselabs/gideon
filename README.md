# gideon
Mighty small doc loader

Built on python's libcouchbase interface.  Achieves very high op rate via batching ops.

python gideon.py --create 100 --ops 20000

client logging in consumer.log

Build and run from Docker!
docker build -t gideon .
