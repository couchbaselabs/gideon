# gideon
Featuring the mighty, small, doc loader

Built on python's libcouchbase interface.  Achieves very high op rate via batching ops.

```bash
# pre-reqs
./build.sh

#run
python gideon.py --ops 50000  --create 30 --get 60 --delete 10
```

Or run from a spec
```yaml
---
bucket: default
ops: 50000 
create: 10 
update: 0
get: 85 
delete: 5
miss: 0
expire: 0
ttl: 15
hosts:
  - 172.23.122.197 
  - 172.23.122.198 
  - 172.23.122.208
  - 172.23.122.218
  - 172.23.122.219
```

```bash
python gideon.py --spec spec.yaml
```


## Automate with Docker
Edit your [spec.yaml](https://github.com/couchbaselabs/gideon/blob/master/spec.yaml) to reflect your enviornment, then
```bash
docker build -t gideon .
docker run gideon
```
