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

1.4 Start Ditto
docker-compose up -d


Check containers:

docker ps

1.5 Verify Ditto

Open:

http://localhost:8080


You should see a JSON response.

Default login:
Username	Password
ditto	ditto
devops	foobar


