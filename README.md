# gideon
Mighty small doc loader

Built on python's libcouchbase interface.  Achieves very high op rate via batching ops.
```bash
python gideon.py --create 100 --ops 20000
```


## Automate with Docker
Edit your [spec.yaml](https://github.com/couchbaselabs/gideon/blob/master/spec.yaml) to reflect your enviornment, then
```bash
docker build -t gideon .
docker run gideon
```
