#!/bin/bash

# Upload implementation guide package to HAPI FHIR server
# Uses the $install operation with base64-encoded package

base64 < ./ndh_package.tgz | tr -d '\n' > ndh_package.b64 && \
curl -i -X POST \
  -H "Content-Type: application/fhir+json" \
  --data-binary @- \
  'http://localhost:8080/fhir/ImplementationGuide/$install' <<EOF
{
  "resourceType": "Parameters",
  "parameter": [
    {
      "name": "npmContent",
      "valueBase64Binary": "$(cat ndh_package.b64)"
    }
  ]
}
EOF
