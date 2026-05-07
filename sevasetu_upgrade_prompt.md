# SevaSetu — Industry-Ready Upgrade Master Prompt

---

## CONTEXT BLOCK (Read First, Never Skip)

You are a **senior full-stack engineer and NGO systems architect** working on
**SevaSetu** — a disaster response and volunteer coordination platform built
with **FastAPI (Python) + React 18 (Vite) + SQLite/PostgreSQL + Gemini AI**.

The repository has 4 sub-apps:
- `backend/` — FastAPI REST API, SQLAlchemy ORM, Pydantic schemas
- `admin-dashboard/` — React admin panel (port 5173)
- `volunteer-app/` — React mobile-first PWA (port 5174)
- `landing_page/` — Static React landing page

**Current state:** Working hackathon MVP. Goal: transform into an
**industry-ready, production-grade platform** in 15 days.

**Non-negotiable rules for every change you make:**
1. Never break existing working features — extend, don't replace
2. Every new backend route follows existing pattern: router → service → model
3. Every new React component inherits existing CSS variables from `index.css`
4. All DB changes go through SQLAlchemy models — no raw SQL migrations
5. Every new feature must work with the existing `dev-token` auth bypass in DEBUG mode
6. Maintain the existing `render.yaml` deployment structure

---

## PHASE 1 — CRITICAL INFRASTRUCTURE (Days 1–3)

### TASK 1.1 — PostgreSQL Migration

**File:** `backend/app/config.py`, `backend/requirements.txt`, `render.yaml`

Replace SQLite with PostgreSQL. The change must be backward-compatible
so SQLite still works in local dev when `DATABASE_URL` is not set.

Requirements:
- Add `psycopg2-binary==2.9.9` and `asyncpg==0.29.0` to `requirements.txt`
- In `config.py`, update the `DATABASE_URL` default to remain SQLite for local
- In `database.py`, conditionally set `connect_args` only for SQLite:
  ```python
  connect_args = {"check_same_thread": False} if "sqlite" in settings.DATABASE_URL else {}
  ```
- In `render.yaml`, add a PostgreSQL database service named `sevasetu-db`
  and inject `DATABASE_URL` from the managed DB into the backend service
- Add a health check in `/health` endpoint that reports which DB engine is active
- Document the exact Render setup steps in a `DEPLOYMENT.md` file

**Validation:** `GET /health` must return `"database_engine": "postgresql"` on Render.

---

### TASK 1.2 — WebSocket Real-Time Layer

**Files:**
- `backend/app/routes/realtime.py` (new)
- `backend/app/main.py` (add router)
- `admin-dashboard/src/services/websocket.js` (new)
- `admin-dashboard/src/pages/DashboardPage.jsx` (integrate)
- `volunteer-app/src/services/websocket.js` (new)

Replace the 30-second polling with a WebSocket connection.

**Backend — `realtime.py`:**
```python
# Implement a ConnectionManager class:
class ConnectionManager:
    def __init__(self):
        self.active_connections: dict[str, list[WebSocket]] = {
            "admin": [],
            "volunteer": [],
        }
    
    async def connect(self, websocket, room: str): ...
    async def disconnect(self, websocket, room: str): ...
    async def broadcast_to_room(self, room: str, message: dict): ...
    async def send_personal(self, websocket, message: dict): ...

manager = ConnectionManager()

# WebSocket endpoint:
@router.websocket("/ws/{room}/{token}")
async def websocket_endpoint(websocket, room, token, db): ...

# Emit helper (import and call this from other routes):
async def emit_event(event_type: str, data: dict, room: str = "admin"):
    await manager.broadcast_to_room(room, {
        "type": event_type,   # "need.created" | "need.updated" | "volunteer.updated" | "assignment.created"
        "data": data,
        "timestamp": datetime.now(timezone.utc).isoformat()
    })
```

**Events to emit (add `emit_event()` calls inside existing routes):**
- `needs.py POST /` → emit `need.created`
- `needs.py PATCH /{id}/` → emit `need.updated`
- `matching.py POST /assign/` → emit `assignment.created`
- `volunteers.py PATCH /availability/` → emit `volunteer.updated`

**Frontend — `websocket.js`:**
```javascript
// Singleton WebSocket manager
class WSManager {
  connect(room, token, onMessage) { ... }
  disconnect() { ... }
  isConnected() { ... }
}
// Export: wsManager.connect("admin", token, handler)
```

**DashboardPage integration:**
- Replace `setInterval(loadData, 30000)` with WebSocket subscription
- On `need.created` → prepend to needs list with a green flash animation
- On `volunteer.updated` → update volunteer count badge live
- Show a green pulsing dot "● Live" when WS is connected, red "○ Reconnecting" when not
- Auto-reconnect with exponential backoff (1s, 2s, 4s, max 30s)

**Validation:** Open admin and volunteer tabs simultaneously. Create a need in
volunteer app → it must appear on admin dashboard map within 500ms, no refresh.

---

### TASK 1.3 — Harden Admin Authentication

**Files:**
- `admin-dashboard/src/context/AuthContext.jsx` (rewrite)
- `admin-dashboard/src/pages/LoginPage.jsx` (keep UI, fix logic)
- `admin-dashboard/src/App.jsx` (add route guard)

Current `AuthContext` auto-logs in with a hardcoded dev token. Fix this:

```jsx
// AuthContext must:
// 1. Check localStorage for existing JWT token
// 2. Call GET /auth/me/ to validate it's still valid
// 3. If invalid → redirect to /login
// 4. Expose: { user, login, logout, loading, isAuthenticated }

// Login flow:
async function login(idToken) {
  const res = await auth.googleLogin(idToken, 'admin')
  setToken(res.access_token)
  setUser(res.user)
}

// Email login:
async function emailLogin(email, password) {
  const res = await auth.emailLogin(email, password)
  setToken(res.access_token)
  setUser(res.user)
}
```

Add a `<ProtectedRoute>` wrapper in `App.jsx`:
```jsx
function ProtectedRoute({ children }) {
  const { isAuthenticated, loading } = useAuth()
  if (loading) return <LoadingSpinner />
  if (!isAuthenticated) return <Navigate to="/login" />
  return children
}
```

Keep `DEBUG` dev-token bypass working: if token is `"dev-token"`, skip `/auth/me/`
validation and inject the hardcoded admin user.

---

## PHASE 2 — ADVANCED FEATURES (Days 4–12)

### TASK 2.1 — Predictive Need Forecasting Engine

**Files:**
- `backend/app/services/prediction_service.py` (new)
- `backend/app/routes/predictions.py` (new)
- `admin-dashboard/src/pages/DashboardPage.jsx` (add prediction panel)

**Logic:** When `DisasterAlertSystem` detects a disaster (severity ≥ 4), call
this engine to auto-generate **draft needs** based on historical patterns.

**`prediction_service.py`:**
```python
# Historical disaster-to-need probability map:
DISASTER_NEED_PATTERNS = {
    "FLOOD": [
        {"category": "food",    "probability": 0.92, "urgency": 5, "people_multiplier": 1.5},
        {"category": "shelter", "probability": 0.88, "urgency": 5, "people_multiplier": 1.2},
        {"category": "rescue",  "probability": 0.75, "urgency": 5, "people_multiplier": 0.3},
        {"category": "water",   "probability": 0.95, "urgency": 4, "people_multiplier": 2.0},
        {"category": "medical", "probability": 0.60, "urgency": 4, "people_multiplier": 0.5},
    ],
    "CYCLONE": [...],
    "EXTREME_HEAT": [...],
    "THUNDERSTORM": [...],
}

async def generate_predicted_needs(
    disaster_type: str,
    center_lat: float,
    center_lon: float,
    affected_radius_km: float,
    estimated_population: int,
    db: Session
) -> list[dict]:
    # 1. Look up pattern for disaster_type
    # 2. For each need with probability > 0.6:
    #    - Calculate estimated people_affected = estimated_population * multiplier
    #    - Generate title using Gemini: "Predicted: {category} shortage in {area}"  
    #    - Set status = "predicted" (add to NeedStatus enum)
    #    - Set source = "ai_prediction"
    # 3. Return list of draft needs for admin review
    # 4. Do NOT auto-create — return for human approval
```

**New `NeedStatus` value:** Add `predicted = "predicted"` to the enum.
Predicted needs show in dashboard with a purple "AI PREDICTED" badge.
Admin can click "Confirm" to convert to `open` status, or "Dismiss."

**New API endpoint:**
```
POST /api/v1/predictions/generate/
Body: { disaster_type, lat, lon, radius_km, estimated_population }
Response: { predicted_needs: [...], confidence_score: float }

GET /api/v1/predictions/
Response: list of unreviewed predicted needs

PATCH /api/v1/predictions/{need_id}/confirm/
PATCH /api/v1/predictions/{need_id}/dismiss/
```

**Dashboard UI:** Add a `PredictionPanel` component below the AI Summary card.
Shows predicted needs with purple styling, confirm/dismiss buttons.
Auto-triggers when `DisasterAlertSystem` detects severity ≥ 4.

---

### TASK 2.2 — Volunteer Fatigue & Wellness Score

**Files:**
- `backend/app/models.py` (add fields to Volunteer)
- `backend/app/services/matching_engine.py` (integrate fatigue penalty)
- `backend/app/routes/volunteers.py` (add fatigue endpoint)
- `admin-dashboard/src/pages/VolunteersPage.jsx` (show fatigue indicator)

**New Volunteer model fields:**
```python
last_task_completed_at = Column(DateTime, nullable=True)
tasks_last_48h = Column(Integer, default=0)     # recalculated on each task completion
fatigue_score = Column(Float, default=0.0)       # 0.0 (fresh) to 1.0 (burned out)
rest_recommended = Column(Boolean, default=False)
```

**Fatigue calculation (call after every assignment completion):**
```python
def calculate_fatigue_score(volunteer: Volunteer) -> float:
    """
    Fatigue Score = weighted sum of:
    - Tasks in last 24h (weight: 0.5) — normalized to max 3 tasks
    - Tasks in last 48h (weight: 0.3) — normalized to max 5 tasks
    - Time since last rest (weight: 0.2) — hours without break
    
    Score 0.0-0.3 = Fresh (green)
    Score 0.3-0.6 = Moderate (yellow)  
    Score 0.6-0.8 = Tired (orange) — flag in UI
    Score 0.8-1.0 = Burned out (red) — rest_recommended = True
    """
```

**Matching engine integration:**
```python
# In calculate_match_score():
fatigue_penalty = volunteer.fatigue_score * 30  # max 30 point penalty
availability_score = availability_score * (1 - volunteer.fatigue_score * 0.5)

# If rest_recommended: append reason "⚠️ Rest recommended — high fatigue"
# Still show in results but ranked lower
```

**New API endpoint:**
```
GET /api/v1/volunteers/{id}/fatigue/
Response: { fatigue_score, tasks_last_48h, rest_recommended, next_available_at }
```

**VolunteersPage UI:**
- Add a fatigue bar (thin colored line under each volunteer card)
- Green → Yellow → Orange → Red based on score
- Show `🔋` icon with tooltip on cards where `rest_recommended = True`
- Add filter: "Show fresh volunteers only"

---

### TASK 2.3 — Resource Inventory System

**Files:**
- `backend/app/models.py` (new `Inventory`, `InventoryItem` models)
- `backend/app/routes/inventory.py` (new)
- `backend/app/services/matching_engine.py` (inventory-aware scoring)
- `admin-dashboard/src/pages/` → new `InventoryPage.jsx`
- `admin-dashboard/src/components/Layout.jsx` (add nav item)

**Models:**
```python
class Inventory(Base):
    __tablename__ = "inventories"
    id = Column(String(36), primary_key=True, default=_uuid)
    name = Column(String(255))           # "Andheri NGO Warehouse"
    latitude = Column(Float)
    longitude = Column(Float)
    address = Column(String(500))
    managed_by = Column(String(36), ForeignKey("users.id"))
    items = relationship("InventoryItem", back_populates="inventory")

class InventoryItem(Base):
    __tablename__ = "inventory_items"
    id = Column(String(36), primary_key=True, default=_uuid)
    inventory_id = Column(String(36), ForeignKey("inventories.id"))
    category = Column(String(50))        # matches NeedCategory
    item_name = Column(String(255))      # "Food Packets - 1kg"
    quantity = Column(Integer)
    unit = Column(String(50))            # "packets", "liters", "sets"
    minimum_threshold = Column(Integer)  # alert when below this
    last_updated = Column(DateTime)
    inventory = relationship("Inventory", back_populates="items")
```

**API endpoints:**
```
POST   /api/v1/inventory/               — create inventory location
GET    /api/v1/inventory/               — list all with stock levels
POST   /api/v1/inventory/{id}/items/    — add/update item stock
PATCH  /api/v1/inventory/items/{id}/    — adjust quantity (+/-)
GET    /api/v1/inventory/nearby/?lat=&lon=&category= — nearest stock for a need
GET    /api/v1/inventory/alerts/        — items below minimum threshold
```

**Matching engine integration:**
When matching volunteers to a need, also return the nearest inventory
with available stock for that category:
```python
# MatchSuggestion response adds:
nearest_inventory: Optional[dict] = None  
# { "name": "Andheri Warehouse", "distance_km": 2.3, "stock": 500, "unit": "packets" }
```

**InventoryPage UI:**
- Table of all inventories with expandable item rows
- Color-coded stock levels: green/yellow/red
- Quick adjust buttons: `+10`, `-10`, custom input
- Alert banner for low-stock items (below `minimum_threshold`)
- Map view showing inventory locations as warehouse icons (📦)

---

### TASK 2.4 — Offline-First PWA (Volunteer App)

**Files:**
- `volunteer-app/public/sw.js` (new — Service Worker)
- `volunteer-app/src/main.jsx` (register SW)
- `volunteer-app/public/manifest.json` (new)
- `volunteer-app/vite.config.js` (PWA plugin)
- `volunteer-app/src/services/offlineQueue.js` (new)
- `volunteer-app/src/pages/ReportPage.jsx` (offline support)

**Install:** `npm install vite-plugin-pwa workbox-window`

**`vite.config.js` addition:**
```javascript
import { VitePWA } from 'vite-plugin-pwa'

VitePWA({
  registerType: 'autoUpdate',
  workbox: {
    globPatterns: ['**/*.{js,css,html,png,svg}'],
    runtimeCaching: [{
      urlPattern: /^https:\/\/sevasetu-bnup\.onrender\.com\/api\/v1\/(needs|volunteers)/,
      handler: 'NetworkFirst',
      options: { cacheName: 'api-cache', expiration: { maxAgeSeconds: 3600 } }
    }]
  }
})
```

**`offlineQueue.js` — IndexedDB queue for offline submissions:**
```javascript
// When navigator.onLine === false:
// Store pending need reports in IndexedDB
// On reconnect → flush queue → call API → show success toast
// Show pending count badge: "3 reports queued for sync"

export const offlineQueue = {
  async add(type, payload) { ... },     // add to IndexedDB
  async flush(apiCaller) { ... },       // submit all queued items
  async count() { ... },               // return pending count
  async list() { ... }                 // return all pending items
}
```

**`ReportPage.jsx` changes:**
- Detect `navigator.onLine`
- When offline: show yellow banner "📵 Offline Mode — Your report will sync automatically"
- Submit button changes to "Save for Sync" when offline
- On reconnect: auto-flush queue, show "✅ 3 reports synced" toast
- Show `offlineQueue.count()` badge in nav bar

**`manifest.json`:** Configure name, icons, theme color, `display: standalone`.

---

### TASK 2.5 — SOS Panic Button

**Files:**
- `volunteer-app/src/pages/HomePage.jsx` (add SOS button)
- `volunteer-app/src/services/sos.js` (new)
- `backend/app/routes/volunteers.py` (add SOS endpoint)
- `backend/app/services/fcm_service.py` (add SOS notification)

**`sos.js`:**
```javascript
export async function triggerSOS() {
  // 1. Get GPS coordinates (navigator.geolocation.getCurrentPosition)
  // 2. POST /api/v1/volunteers/sos/ with { lat, lon, message: "SOS triggered" }
  // 3. Backend creates urgency-5 need, broadcasts to admins, sends FCM
  // 4. Return { sos_id, message, estimated_response_time }
}
```

**Backend SOS endpoint:**
```python
@router.post("/sos/")
async def trigger_sos(body: SOSRequest, current_user=Depends(get_current_user), db=Depends(get_db)):
    # 1. Create Need with urgency=5, category="rescue", source="sos", status="open"
    # 2. Title: f"🆘 SOS — {current_user.name} needs immediate help"
    # 3. Broadcast FCM to all admin users
    # 4. Emit WebSocket event "sos.triggered" to admin room
    # 5. Return need_id + estimated response time
```

**HomePage SOS UI:**
```jsx
// Big red pulsing button at the bottom of HomePage
// Position: fixed, bottom center
// Hold 3 seconds to activate (prevents accidental triggers)
// Progress ring shows hold progress
// On activate: full-screen red overlay → "SOS Sent — Help is coming"
// Shows countdown timer, cancel option in first 10 seconds

<SOSButton 
  holdDuration={3000}
  onActivate={triggerSOS}
  onCancel={cancelSOS}
/>
```

Show SOS as a priority alert on admin dashboard map with 🆘 marker and pulsing animation.

---

### TASK 2.6 — Impact Certificate Generator

**Files:**
- `backend/app/routes/volunteers.py` (add certificate trigger)
- `volunteer-app/src/pages/ProfilePage.jsx` (add certificate section)
- `volunteer-app/src/services/certificate.js` (new — jsPDF generator)
- `admin-dashboard/src/pages/VolunteersPage.jsx` (admin certificate view)

**Certificate triggers:**
- First task completed → "First Responder" certificate
- 5 tasks → "Active Volunteer" certificate
- 10 tasks → "Community Hero" certificate
- 25 tasks → "Disaster Relief Champion" certificate

**`certificate.js` (jsPDF, already in admin deps — add to volunteer app too):**
```javascript
export function generateCertificate(volunteerData, tier) {
  const doc = new jsPDF({ orientation: 'landscape', unit: 'mm', format: 'a4' })
  
  // Gold border frame
  // SevaSetu logo (top center)
  // "Certificate of Appreciation" (Playfair Display font style)
  // "This certifies that {name} has completed {tasks} disaster relief missions"
  // Tier badge (color-coded by tier)
  // Digital issue date + certificate ID (UUID)
  // "Issued by SevaSetu — Smart Disaster Response Platform"
  
  doc.save(`SevaSetu_Certificate_${volunteerData.name}_${tier}.pdf`)
}
```

**Backend endpoint:**
```
GET /api/v1/volunteers/{id}/certificate/
Response: { eligible_tiers: [...], current_tier: str, tasks_to_next: int }
```

**ProfilePage UI:** Certificate section with unlocked/locked tiers shown as cards.
Download button only on unlocked tiers. Lock icon with progress on locked ones.

---

### TASK 2.7 — Voice-to-Need (Web Speech API)

**Files:**
- `volunteer-app/src/pages/ReportPage.jsx` (add voice button)
- `volunteer-app/src/services/voiceInput.js` (new)

**`voiceInput.js`:**
```javascript
export class VoiceRecorder {
  start() {
    // Use Web Speech API (SpeechRecognition)
    // interimResults: true for live transcript display
    // language: 'hi-IN' || 'en-IN' (auto-detect or let user choose)
  }
  
  stop() { ... }  // Returns final transcript string
  
  isSupported() { return 'SpeechRecognition' in window || 'webkitSpeechRecognition' in window }
}
```

**ReportPage integration:**
```jsx
// Add mic button next to description field
// On press: red pulsing recording indicator + live transcript shown
// On stop: transcript auto-fills description field
// Then call existing Gemini OCR "structuring" logic 
//   (POST to a new endpoint: /api/v1/ocr/structure-text/)
//   to extract: category, urgency, location, people_affected
// Auto-fill all form fields from Gemini response
// User reviews and submits

// Language selector: 🇮🇳 Hindi | 🇬🇧 English
// Fallback: if not supported, hide button gracefully
```

**New backend endpoint:**
```
POST /api/v1/ocr/structure-text/
Body: { text: str, language: str }
Response: OCRStructuredData (same schema as OCR extract)
# Internally calls gemini_service with the text (no image processing needed)
```

---

## PHASE 3 — PRODUCTION HARDENING (Days 13–15)

### TASK 3.1 — Rate Limiting

**Files:**
- `backend/requirements.txt` (add `slowapi==0.1.9`)
- `backend/app/main.py` (add limiter middleware)
- `backend/app/routes/ocr.py` (strict limit)
- `backend/app/routes/auth.py` (auth limit)

```python
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Apply limits:
@router.post("/ocr/extract/")
@limiter.limit("10/minute")           # OCR: 10 per minute (Gemini quota protection)
async def extract_ocr(...): ...

@router.post("/auth/login/")
@limiter.limit("5/minute")            # Auth: prevent brute force

@router.post("/auth/register/")
@limiter.limit("3/minute")

@router.post("/broadcast/")
@limiter.limit("20/hour")             # Broadcast: prevent spam

@router.post("/predictions/generate/")
@limiter.limit("5/minute")            # Predictions: Gemini quota
```

---

### TASK 3.2 — Audit Trail Frontend

**Files:**
- `admin-dashboard/src/pages/AuditPage.jsx` (new)
- `admin-dashboard/src/components/Layout.jsx` (add nav item: "Audit Trail")
- `backend/app/routes/analytics.py` (add audit endpoints)

**New API endpoints:**
```
GET /api/v1/analytics/audit/?page=1&limit=50&action=&user_id=&from=&to=
Response: { items: [AuditLog], total, page, total_pages }

GET /api/v1/analytics/audit/summary/
Response: { actions_today, top_actors, most_common_actions, suspicious_activity }
```

**`AuditPage.jsx` UI:**
- Filterable table: by action type, by user, by date range
- Color-coded action badges:
  - `auth.*` → blue
  - `need.*` → green
  - `assignment.*` → purple
  - `broadcast.*` → red/orange
- "Suspicious Activity" tab: flags >10 failed logins, mass deletions, unusual hours
- Export as CSV button

**Wire up existing `AuditLog` model** — it's in `models.py` but never queried.
Add `emit_audit()` calls in all existing routes where they're missing.

---

### TASK 3.3 — Volunteer Skill Verification System

**Files:**
- `backend/app/models.py` (add `SkillVerification` model)
- `backend/app/routes/volunteers.py` (verification endpoints)
- `admin-dashboard/src/pages/VolunteersPage.jsx` (verify button)
- `backend/app/services/matching_engine.py` (verified skill bonus)

**Model:**
```python
class SkillVerification(Base):
    __tablename__ = "skill_verifications"
    id = Column(String(36), primary_key=True, default=_uuid)
    volunteer_id = Column(String(36), ForeignKey("volunteers.id"))
    skill = Column(String(100))
    verified = Column(Boolean, default=False)
    verified_by = Column(String(36), ForeignKey("users.id"), nullable=True)
    certificate_url = Column(String(512), nullable=True)  # uploaded proof
    verified_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=_utcnow)
```

**API:**
```
POST /api/v1/volunteers/{id}/verify-skill/
Body: { skill: str, certificate_url: str (optional) }
# Admin only — marks skill as verified

GET /api/v1/volunteers/{id}/skill-verifications/
```

**Matching engine bonus:**
```python
# In calculate_match_score():
verified_skills = get_verified_skills(volunteer.id, db)
verified_match = len(set(volunteer.skills_list) & set(required_skills) & set(verified_skills))
unverified_match = matched - verified_match

skill_score = (verified_match * 1.5 + unverified_match * 1.0) / len(required_skills) * 100
# Capped at 100
```

**UI:** Blue ✓ badge next to each verified skill. Admin can click any skill
in volunteer detail view → "Mark as Verified" button with optional proof URL input.

---

## OUTPUT FORMAT RULES (Follow for Every Task)

When implementing each task:

1. **Start with the model/schema changes** — data shape first
2. **Then service layer** — pure business logic, no HTTP concerns
3. **Then route layer** — thin, delegates to service
4. **Then frontend** — component → service → API call
5. **For every new file:** include the full file, never partial snippets
6. **For modified files:** show only the changed functions with clear `# MODIFIED` and `# NEW` comments
7. **Never delete** existing working code — extend it
8. **Test each task** by describing the exact curl command or UI steps to validate it works

---

## DEMO FLOW TO BUILD TOWARD

Every feature must serve this end-to-end demo scenario:

```
1. OWM detects cyclone approaching Mumbai coast
2. DisasterAlertSystem shows RED ALERT banner
3. Prediction engine auto-generates 5 draft needs (food, shelter, rescue, water, medical)
4. Admin reviews and confirms 3 of them → they appear on map instantly via WebSocket
5. Volunteer in field opens PWA (offline zone) → submits voice report in Hindi
6. Report syncs when connectivity returns → new need on map
7. Volunteer hits SOS button (3-second hold) → admin gets instant alert
8. Smart Match finds nearest non-fatigued volunteer with verified medical skill
9. Nearest inventory warehouse shows 200 food packets available 2km away
10. Admin assigns → volunteer accepts → task completed
11. Certificate auto-generated for volunteer's 5th task
12. Audit trail shows full chain of events
13. Impact dashboard shows: 150 people helped, 4.2h avg response, 0 volunteer burnouts
```

If a feature doesn't contribute to this flow, deprioritize it.

---

## IMPLEMENTATION ORDER (Strict)

```
Week 1 (Days 1-7):
├── Day 1: Task 1.1 (PostgreSQL) + Task 1.3 (Auth hardening)
├── Day 2: Task 1.2 (WebSocket backend)
├── Day 3: Task 1.2 (WebSocket frontend integration)
├── Day 4: Task 2.1 (Prediction engine backend)
├── Day 5: Task 2.1 (Prediction UI)
├── Day 6: Task 2.2 (Fatigue score)
├── Day 7: Task 2.5 (SOS button — full stack)

Week 2 (Days 8-15):
├── Day 8:  Task 2.3 (Inventory system backend)
├── Day 9:  Task 2.3 (Inventory UI)
├── Day 10: Task 2.4 (Offline PWA)
├── Day 11: Task 2.7 (Voice input)
├── Day 12: Task 2.6 (Certificates)
├── Day 13: Task 3.1 (Rate limiting)
├── Day 14: Task 3.2 (Audit trail) + Task 3.3 (Skill verification)
├── Day 15: Full demo flow test + deploy + DEPLOYMENT.md
```

---

## HOW TO USE THIS PROMPT

Paste this entire prompt followed by ONE of these task selectors:

```
> IMPLEMENT: Task 1.1
> IMPLEMENT: Task 1.2 — Backend only
> IMPLEMENT: Task 1.2 — Frontend only
> IMPLEMENT: Task 2.1
... etc.
```

The AI will implement exactly that task, following all rules above,
producing complete production-ready code.

Do not ask for all tasks at once. One task per session.
After each task, run validation, then move to next.
