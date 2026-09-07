# GoBus Transit Platform — Team Admin Web Access Guide
**Kolkata Transit Authority — Remote Data-Entry Access**

---

### Admin Web Public URL
**URL**: `https://population-butterfly-continuously-entity.trycloudflare.com`

### Application Credentials
- **Email**: `admin@kolkatatransit.local`
- **Password**: *Use the shared Admin password provided separately by the project owner.*

---

### Team Instructions for Data Entry
1. **Open the URL**: Navigate to `https://population-butterfly-continuously-entity.trycloudflare.com` on any smartphone, tablet, or laptop browser with Internet access.
2. **Sign In**: Enter `admin@kolkatatransit.local` and the shared password, then click **Sign In**.
3. **Canonical Data-Entry Order** (as specified in Build 5):
   - **Step 1: Stops Management** (`/stops`) — Create the 40 stops and their aliases.
   - **Step 2: Fare Management** (`/fares`) — Create Ordinary Bus and AC Express distance slab configurations.
   - **Step 3: Route Management** (`/routes`) — Create Route `SD5` and assign the 40 ordered stops via *Manage Stops*.
   - **Step 4: Services Management** (`/services`) — Create `SD5-REG` and `SD5-EXP` linking to Route `SD5` and their respective fare configurations.
   - **Step 5: Schedules** (`/services/:id/schedules`) — Add directional service schedules.
   - **Step 6: Vehicles** (`/vehicles`) — Register fleet vehicles (`WB-04-E-1001`, etc.).
   - **Step 7: Users** (`/users`) — Add drivers and conductors.
   - **Step 8: Depot Schedules** (`/depot-schedules`) — Assign vehicles to services for dispatch.
4. **Data Safety Rules**:
   - Do NOT open low-level database tools (psql, pgAdmin, etc.).
   - Do NOT change tunnel, environment, or deployment settings.
   - Enter authentic coordinates; do not fabricate placeholder coordinates.
5. **Connectivity Support**:
   - This temporary access is powered by a Cloudflare Quick Tunnel running on the host machine.
   - If the URL stops responding, contact the host machine owner to confirm the tunnel session is active.
