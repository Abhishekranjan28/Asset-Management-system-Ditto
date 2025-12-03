🚀 1. Eclipse Ditto Setup
1.1 Install Docker & Docker Compose

Download Docker Desktop:

👉 https://www.docker.com/products/docker-desktop/

1.2 Download Eclipse Ditto

Clone:

git clone https://github.com/eclipse-ditto/ditto.git


Or download a release:

👉 https://www.eclipse.org/ditto/download/

1.3 Navigate to Docker folder
cd ditto/deploy/docker

Default login:
Username:	ditto
Password:ditto
devops:	foobar

#In ditto deployment/docker/docker-compose.yml-gateway
      replace commented code DEVOPS-PASSWORD=foobar to DEVOPS-PASSWORD=ditto

1.4 Start Ditto
docker-compose up -d


Check containers:

docker ps

1.5 Verify Ditto

Open:

http://localhost:8080


You should see a JSON response.


✅ 1. Create the Policy File (policy.json)

Run:

nano policy.json


Paste this:

{
  "policyId": "default-camera-policy",
  "entries": {
    "camera-service": {
      "subjects": {
        "nginx:ditto": { "type": "user" }
      },
      "resources": {
        "things:/": {
          "grant": ["READ", "WRITE", "MODIFY"],
          "revoke": []
        },
        "features:/": {
          "grant": ["READ", "WRITE", "MODIFY"],
          "revoke": []
        },
        "messages:/": {
          "grant": ["READ", "WRITE"],
          "revoke": []
        }
      }
    }
  }
}


✔ This gives the user ditto/ditto full permissions needed by your Python code.

✅ 2. Upload the Policy to Ditto (Linux curl)

Run this:

curl -X PUT \
  -u ditto:ditto \
  -H "Content-Type: application/json" \
  --data @policy.json \
  http://localhost:8080/api/2/policies/default-camera-policy


Expected: 200 OK