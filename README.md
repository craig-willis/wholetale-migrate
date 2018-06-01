# Migrate from GridFS to WebDav

This repository contains the Docker images definition and script used to migrate user data from the original GridFS assetstore to the new `wt_home_dir` WebDav assetstore.

## Migration process

The first step is to backup the production Mongo database.  Since v0.2 has not been deployed, this means manually downloading and running `rclone` from a production mongo container:

On your local machine, setup the `rclone` configuration for Box.
```
rclone --config rclone.conf config
```

`ssh` to the production environment then:
```
$ docker exec -it <mongo container>
# cd /tmp
# cat > rclone.conf
<contents of rclone.conf
^D
# ./rclone --config rclone.conf  lsd backup:WT/wt-prod
# ./rclone --config rclone.conf mkdir backup:WT/wt-prod/20180601
# mongodump --gzip --archive=/tmp/mongodump-20180601.tgz
# ./rclone --config rclone.conf copy mongodump-20180601.tgz backup:WT/wt-prod/20180601
# ./rclone --config rclone.conf ls backup:WT/wt-prod/
```

Deploy the staging environment using `terraform apply`. 

Restore the latest production database. 
`ssh` to the staging NFS node.

```
$ docker run --rm --network wt_mongo -v /mnt/homes:/backup -v /home/core/rclone/:/conf wholetale/backup bash
# cd /tmp
# rclone --config /conf/rclone.conf copy backup:/WT/wt-prod/20180601/mongodump-20180601.tgz /tmp
# mongo_host="wt_mongo1:27017,wt_mongo2:27017,wt_mongo3:27017"
# mongorestore --drop --host=$mongo_host --gzip --archive=/tmp/mongodump-20180601.tgz
```

Via Girder UI, Enable "WholeTale Home Directory Plugin"  and restart. After restart, set `homes wtassetstore` as default assetstore.


Run the migration container, then run `girder-shell` to run the migration script
```
docker run --rm -it \
    --name wholetale_migrate \
    --label traefik.enable=false \
    -v /:/host \
    -v /var/cache/davfs2:/var/cache/davfs2 \
    -v /run/mount.davfs:/run/mount.davfs \
    --device /dev/fuse \
    --cap-add SYS_ADMIN \
    --cap-add SYS_PTRACE \
    --network wt_mongo \
    --entrypoint /bin/bash \
    craigwillis/wholetale-migrate
    
$ girder-shell

[1] % run ./migrate.py -a <GridFS assetstoreId>
```    

Use the REST API to confirm the assetstore has no more files.

Confirm all file counts after migration
* Compare /mnt/homes to files that were downloaded
* Compare /mnt/homes to files in Girder production

There are several files missing after migration:
* 2 belong to admin user (ignored)
* 1 has an error (Item id is None for 59a6df45615678000159c2ea)
* 7 are 0 byte and currently not created.


