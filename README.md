# Self-Hosted Email Tracker

This project is a lightweight email tracking system for logging opens and clicks of emails sent from Gmail (including mobile). It uses a Google Apps Script to process drafted emails and a Python FastAPI backend deployed via Docker to a Raspberry Pi (or any server).

## Components
- Python FastAPI Server (Dockerized, Multi-arch for Raspberry Pi).
- SQLite Database for logging tracking data locally.
- Google Apps Script snippet for injecting tracking links/pixels into drafts.

## Setup Instructions

### 1. Server Setup (Raspberry Pi/Linux)

1. Make sure Docker and Docker Compose are installed on your device.
2. Clone this repository to your Raspberry Pi.
3. Open a terminal in the repository folder and run the following to build the app and start the server:
   ```bash
   docker compose up -d --build
   ```
4. The service will be running on port `8081` (you can change this in `docker-compose.yml` if it conflicts with another service).
5. Check if it's working by visiting `http://<your-pi-ip>:8081/dashboard`.
6. To make the service accessible from the outside (which is required for tracking to work), we recommend using **Cloudflare Tunnels**.
   - Install `cloudflared` on your Raspberry Pi and configure a Tunnel.
   - **Permanent Tunnel with Custom Domain**: 
     Log into the Cloudflare Zero Trust Dashboard, go to Networks -> Tunnels, create a new tunnel, and follow the installation command provided to point it to `http://localhost:8081`.
   - **Securing Your Tunnel**: In the Cloudflare Zero Trust Dashboard (Access -> Applications), secure your tunnel's domain by requiring authentication (e.g., email OTP). **Crucially**, you must create "Bypass" rules for the `/open*` and `/click*` paths. This ensures your dashboard remains private while the tracking pixels and links remain publicly accessible.
   - Make a note of your public URL to use in the Google Apps Script setup.

### 2. Google Apps Script Setup

1. In your Gmail account, create a new label named `TrackMe`.
2. Go to [script.google.com](https://script.google.com) and create a new project.
3. Copy the contents of the `google_apps_script.js` file into the editor.
4. Update the `TRACKING_SERVER_URL` variable at the top of the file to your public URL from the server setup phase.
5. Save the project setup.
6. Set up a Time-driven Trigger:
   - Click the **Triggers** icon (the clock 🕒 on the left).
   - Click **Add Trigger**.
   - Choose `processTrackedDrafts` as the function to run.
   - Set the event source to **Time-driven**.
   - Set the type to **Minutes timer** (e.g., every 1 or 5 minutes).
   - Save the trigger. (Google might ask you to authorize the script; follow the prompts to grant permission).

## Usage

1. In Gmail (desktop or your mobile app), compose a new email.
2. Save it as a Draft.
3. Apply the `TrackMe` label to that draft.
4. Let the Google Apps Script run (based on your timer). The script will append a tracking pixel, wrap any links for tracking, send the email automatically, and delete the draft.
5. You can view your tracking stats by visiting `http://<your-public-url>/dashboard`.

## Database

The tracking events are logged into a local `tracking.db` SQLite file created inside the container and mounted via Docker Compose.

**Backing up your database:**
If you want to back up your database to Google Drive, OneDrive, or another cloud service on your Raspberry Pi, you can change the volume mount location in `docker-compose.yml`. Simply change `./tracking.db` to the absolute path of your sync folder (e.g., `/home/pi/GoogleDrive/tracking.db`).
