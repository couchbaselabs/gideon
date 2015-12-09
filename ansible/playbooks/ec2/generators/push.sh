python scalability_top.py > scalability_top.json
python scalability_vpc.py > scalability_vpc.json
python scalability_couchbase.py > scalability_couchbase.json

./aws.sh scalability_top.json $BUCKET_NAME $AWS_ACCESS_KEY_ID $AWS_SECRET_ACCESS_KEY
./aws.sh scalability_vpc.json $BUCKET_NAME $AWS_ACCESS_KEY_ID $AWS_SECRET_ACCESS_KEY
./aws.sh scalability_couchbase.json $BUCKET_NAME $AWS_ACCESS_KEY_ID $AWS_SECRET_ACCESS_KEY
