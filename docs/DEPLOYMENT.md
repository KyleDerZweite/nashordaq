# Deployment Guide

## Prerequisites

- A server with [Podman](https://podman.io/) and `podman-compose` installed.
- A domain name with DNS pointing to your server (or to your Pangolin tunnel endpoint).
- A [Riot Games API key](https://developer.riotgames.com/).
- A running [Pangolin](https://pangolin.net/) instance (Enterprise Edition for SSO header forwarding).

## 1. Environment File

Create a `.env` file in the project root:

```env
# Riot Games API
NASHORDAQ_RIOT_API_KEY=RGAPI-xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx

# Domain (used for CORS)
NASHORDAQ_DOMAIN=nashordaq.example.com

# Pangolin / Newt tunnel credentials
PANGOLIN_ENDPOINT=https://pangolin.example.com
NEWT_ID=your-newt-id
NEWT_SECRET=your-newt-secret
```

### Optional Variables

| Variable | Default | Description |
|---|---|---|
| `NASHORDAQ_AUTH_HEADER` | `Remote-User` | Header containing the authenticated username |
| `NASHORDAQ_STARTING_BALANCE` | `10000.0` | Initial balance for new users |
| `NASHORDAQ_ENFORCE_TRUSTED_PROXY` | `false` | Reject auth headers from non-trusted source IPs |
| `NASHORDAQ_TRUSTED_PROXY_CIDRS` | `127.0.0.1/32,::1/128` | Allowed proxy CIDR ranges (when enforcement is on) |
| `NASHORDAQ_RIOT_API_BASE_URL` | `https://europe.api.riotgames.com` | Riot account/match API region |
| `NASHORDAQ_RIOT_API_REGION_URL` | `https://euw1.api.riotgames.com` | Riot league/summoner API region |

### Market Update Cadence

Market updates are dynamic:

- Effective interval in minutes = `number of tracked players`
- Example: 10 tracked players => market update runs every ~10 minutes

The scheduler wakes every 30 seconds internally and runs immediately on startup, but only performs a full Riot fetch/order execution cycle when the dynamic interval is due.

## 2. Tracked Players

Tracked players are created through user self-onboarding. On first authenticated visit, each user must enter their own Riot `game_name`, `tag_line`, and `display_name`. After submission, their linked Riot account is added to the tracked player set.

This replaces static player seeding and does not require editing JSON files during deployment.

## 3. Build and Run

```bash
podman-compose up --build -d
```

The frontend is served on port 80. The backend runs internally on port 8000 with Nginx reverse-proxying `/api/` requests.

## 4. Pangolin Configuration

Pangolin Enterprise Edition forwards user identity headers automatically when a resource is protected with SSO authentication. The headers Nashordaq relies on:

| Pangolin Header | Used By Backend |
|---|---|
| `Remote-User` | Identifies the user (required) |
| `Remote-Email` | Forwarded through Nginx (informational) |
| `Remote-Name` | Forwarded through Nginx (informational) |

### 4a. Create a Site

1. In the Pangolin dashboard, go to **Sites** and create a new site.
2. Note the **Site ID** and **Site Secret** -- these become `NEWT_ID` and `NEWT_SECRET` in your `.env`.
3. The Newt container in `podman-compose.yaml` connects to Pangolin using these credentials.

### 4b. Create a Resource

1. Go to **Resources** and create a new **Public** resource.
2. Set the domain to your desired hostname (e.g., `nashordaq.example.com`).
3. Under **Targets**, point it to the frontend container's address (`http://nashordaq-frontend:80` or as appropriate for your Newt setup).

### 4c. Enable SSO Authentication

This is the critical step that makes Pangolin inject the `Remote-User` header.

1. Open the resource you created.
2. Go to the **Authentication** tab.
3. Enable **Pangolin SSO** (Platform SSO). This is on by default for new public resources.
4. Optionally restrict access to specific **Users** or **Roles** in your Pangolin organization.

When SSO is active, unauthenticated visitors are redirected to the Pangolin login page. After authentication, Pangolin proxies the request with identity headers (`Remote-User`, `Remote-Email`, `Remote-Name`, `Remote-Role`) attached. See [Pangolin Forwarded Headers docs](https://docs.pangolin.net/manage/access-control/forwarded-headers) for details.

### 4d. External Identity Providers (Optional)

If you want users to log in with Google, Azure, or another OIDC provider instead of Pangolin-native accounts:

1. Go to **Identity Providers** in the Pangolin dashboard.
2. Add your provider (Google, Azure Entra ID, generic OIDC, etc.).
3. The forwarded headers will still be populated from the SSO session.

See [Pangolin Identity Providers docs](https://docs.pangolin.net/manage/identity-providers/add-an-idp) for setup guides per provider.

### Authentication Methods That Do NOT Forward Headers

The following Pangolin auth methods provide access control but do **not** inject identity headers, so they are incompatible with Nashordaq:

- PIN Code
- Password
- Shareable Links

You must use **SSO** (Platform SSO or External IdP) for Nashordaq to identify users.

## 5. Verify

Once everything is running:

```bash
# Health check (no auth required)
curl https://nashordaq.example.com/api/health

# Authenticated request (through Pangolin SSO in a browser)
# Navigate to https://nashordaq.example.com
# Log in through Pangolin, and the dashboard should load with your user auto-provisioned.
```

## 6. Local Development (Without Pangolin)

For local development, the Vite dev server proxies `/api` to `http://localhost:8000`. You need to manually provide the identity header since there is no Pangolin in the loop.

Start the backend:

```bash
cd backend
NASHORDAQ_RIOT_API_KEY=your-key uv run uvicorn app.main:app --reload
```

Start the frontend:

```bash
cd frontend
pnpm run dev
```

To simulate an authenticated user, send the header manually:

```bash
curl -H "Remote-User: kyle" http://localhost:8000/api/user/me
```

Or use a browser extension (e.g., ModHeader) to inject `Remote-User: kyle` when accessing `http://localhost:5173`.
