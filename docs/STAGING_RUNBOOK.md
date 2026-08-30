# GoBus - Staging Deployment Runbook

This guide covers deploying the GoBus prototype to a Linux VPS (Virtual Private Server) for staging testing.

## Prerequisites
1. **VPS:** A Linux server running Ubuntu 24.04 (e.g., DigitalOcean Droplet, 4GB RAM recommended due to PostGIS).
2. **Domain:** A domain name (e.g., `api.transit.example.com`) with its A-record pointing to your VPS's public IP address.
3. **SSH Access:** Root or sudo access to the VPS.

## Step 1: Install Dependencies
Connect to your VPS via SSH and install Docker and Docker Compose:
```bash
# Add Docker's official GPG key:
sudo apt-get update
sudo apt-get install ca-certificates curl
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc

# Add the repository to Apt sources:
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt-get update

# Install Docker
sudo apt-get install docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
```

## Step 2: Deploy Repository
1. Clone the repository onto the server (or securely copy files).
```bash
git clone <repository_url> transit-platform
cd transit-platform
```

2. Configure environment variables for Staging:
```bash
cp .env.staging.example .env
nano .env
```
Update `.env` with secure secrets and your actual `DOMAIN_NAME`. *Do not commit this file to version control.*

3. Update the `Caddyfile` to use your actual domain:
```bash
nano Caddyfile
# Change {$DOMAIN_NAME} to your actual domain, e.g., api.transit.example.com
```

## Step 3: Start Services
Start the staging infrastructure:
```bash
docker compose -f docker-compose.staging.yml up -d --build
```
This will launch:
- `db`: The PostGIS database container
- `api`: The FastAPI backend container
- `caddy`: The reverse proxy generating a Let's Encrypt HTTPS certificate automatically.

*Note: Allow a minute or two for Caddy to negotiate the HTTPS certificate.*

## Step 4: Run Migrations and Seed Data
Execute database migrations on the `api` container:
```bash
docker compose -f docker-compose.staging.yml exec api alembic upgrade head
```

Seed the deterministic demo data:
```bash
docker compose -f docker-compose.staging.yml exec api python -m app.db.seed
```

Verify the backend is healthy by visiting: `https://api.yourdomain.com/health` in a browser.

## Step 5: Android Build
On your developer machine, compile the Android APK using the staging build variant:
```bash
cd apps/android
./gradlew assembleStaging
```
The staging variant uses `https://api.yourdomain.com` instead of the local emulator IP. Install the APK located at `app/build/outputs/apk/staging/app-staging.apk` onto the physical phone.

## Step 6: Testing
1. **Login:** Log in with `DRV001` / `operator123`.
2. **Telemetry:** Start a trip and begin tracking. Verify network requests are going to HTTPS.
3. **Passenger View:** Retrieve vehicle status at `https://api.yourdomain.com/api/passenger/vehicles/50000000-0000-0000-0000-000000000001` from any browser.
