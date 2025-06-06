#!/bin/sh

echo "Waiting for MinIO to be ready..."
sleep 5

echo "Configuring MinIO Client..."
mc alias set minio http://"$MINIO_HOST":"$MINIO_PORT" "$MINIO_ROOT_USER" "$MINIO_ROOT_PASSWORD"

if mc ls minio | grep -q "$MINIO_BUCKET"; then
    echo "Bucket '$MINIO_BUCKET' already exists. Skipping creation."
else
    echo "Creating bucket: $MINIO_BUCKET"
    mc mb minio/"$MINIO_BUCKET"
fi

echo "Setting bucket policy to public..."
mc anonymous set download minio/"$MINIO_BUCKET"

echo "Getting policy info..."
mc anonymous get minio/"$MINIO_BUCKET"

echo "Creating folders structure..."
mc mb minio/"$MINIO_BUCKET"/movies
mc mb minio/"$MINIO_BUCKET"/thumbnails
mc mb minio/"$MINIO_BUCKET"/trailers

echo "MinIO configuration completed!"
exit 0
