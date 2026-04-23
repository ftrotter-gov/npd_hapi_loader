#!/bin/bash

CONTAINER_NAME="hapi-fhir"

# Check if container exists (running or stopped)
if docker ps -a --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    echo "Container '${CONTAINER_NAME}' already exists. Starting it..."
    docker start ${CONTAINER_NAME}
    echo "Container '${CONTAINER_NAME}' started successfully."
else
    echo "Container '${CONTAINER_NAME}' does not exist. Creating and starting it..."
    docker run -p 8080:8080 \
      --name ${CONTAINER_NAME} \
      --network host \
      -e HAPI_FHIR_ENFORCE_REFERENTIAL_INTEGRITY_ON_WRITE=false \
      -e HAPI_FHIR_VALIDATE_ON_WRITE=false \
      -e HAPI_FHIR_IG_RUNTIME_UPLOAD_ENABLED=true \
      -e hapi.fhir.bulk_import_enabled=true \
      hapiproject/hapi:latest
fi
