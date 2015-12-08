#!/bin/bash
key_id="$3"
key_secret="$4"
file="$1"
bucket="$2"
content_type="application/octet-stream"
date="$(LC_ALL=C date -u +"%a, %d %b %Y %X %z")"
md5="$(openssl md5 -binary < "$file" | base64)"

sig="$(printf "PUT\n$md5\n$content_type\n$date\n/$bucket/$file" | openssl sha1 -binary -hmac "$key_secret" | base64)"

curl -T $file http://$bucket.s3.amazonaws.com/$file \
    -H "Date: $date" \
    -H "Authorization: AWS $key_id:$sig" \
    -H "Content-Type: $content_type" \
    -H "Content-MD5: $md5"
