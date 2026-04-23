#!/bin/bash

echo "Stopping HAPI FHIR container (hapi-fhir)..."
docker stop hapi-fhir 2>&1

echo "Removing HAPI FHIR container (hapi-fhir)..."
docker rm hapi-fhir 2>&1

echo "Container hapi-fhir has been deleted."
