# IRONLUNG 3: SCHEMA SPECIFICATION

**Database Schema with Complete Field Definitions**

Version: 3.3  
Date: February 5, 2026  
Parent: Architecture Overview

---

## OVERVIEW

SQLite database. Single file. Local. Path: `~/.ironlung/ironlung3.db`

**9 tables:**
- companies
- prospects
- contact_methods
- activities
- data_freshness
- import_sources
- research_queue
- intel_nuggets
- prospect_tags
- schema_version

WAL mode enabled. Foreign keys enforced.

---

## COMPANIES

```sql
CREATE TABLE companies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    name_normalized TEXT NOT NULL,
    domain TEXT,
    loan_types TEXT,  -- JSON array
    size TEXT,  -- small/medium/large/enterprise
    state TEXT,  -- Two-letter code
    timezone TEXT NOT NULL DEFAULT 'central',
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_companies_normalized ON companies(name_normalized);
CREATE INDEX idx_companies_domain ON companies(domain);
```

**Timezone assignment cascade:**
1. If state populated → timezone from STATE_TO_TIMEZONE lookup
2. If state blank but phone area code exists → timezone from area code
3. Neither → default to 'central'

---

## PROSPECTS

```sql
CREATE TABLE prospects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id INTEGER NOT NULL,
    
    -- BASIC FIELDS (PREVIOUSLY MISSING)
    first_name TEXT NOT NULL,
    last_name TEXT NOT NULL,
    title TEXT,
    
    -- POPULATION & STAGE
    population TEXT NOT NULL DEFAULT 'broken',
    engagement_stage TEXT,  -- Only populated if population='engaged'
    
    -- SCHEDULING
    follow_up_date DATETIME,  -- DATETIME not DATE - supports hour-specific scheduling
    last_contact_date DATE,
    parked_month TEXT,  -- YYYY-MM format
    
    -- SCORING
    attempt_count INTEGER DEFAULT 0,
    prospect_score INTEGER DEFAULT 0,
    data_confidence INTEGER DEFAULT 0,
    
    -- CONTACT PREFERENCES (NEW)
    preferred_contact_method TEXT,  -- 'email', 'phone', 'either'
    
    -- SOURCE & TRACKING
    source TEXT,
    referred_by_prospect_id INTEGER,  -- NEW - referral tracking
    
    -- DEAD/LOST TRACKING
    dead_reason TEXT,
    dead_date DATE,
    lost_reason TEXT,
    lost_competitor TEXT,
    lost_date DATE,
    
    -- CLOSED WON
    deal_value DECIMAL(10,2),
    close_date DATE,
    close_notes TEXT,
    
    -- NOTES & CUSTOM
    notes TEXT,  -- Static context only (e.g., "CEO, hates cold calls")
    custom_fields TEXT,  -- JSON blob for user-defined variables
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (company_id) REFERENCES companies(id),
    FOREIGN KEY (referred_by_prospect_id) REFERENCES prospects(id)
);

CREATE INDEX idx_prospects_population ON prospects(population);
CREATE INDEX idx_prospects_follow_up ON prospects(follow_up_date);
CREATE INDEX idx_prospects_company ON prospects(company_id);
CREATE INDEX idx_prospects_score ON prospects(prospect_score);
CREATE INDEX idx_prospects_parked ON prospects(parked_month);
CREATE INDEX idx_prospects_referrer ON prospects(referred_by_prospect_id);
```

**Key decisions:**
- `follow_up_date` is DATETIME to support "call him at 2 PM his time"
- `first_name`, `last_name`, `title` explicitly defined (were missing)
- `preferred_contact_method` added for "email me, don't call" preferences
- `referred_by_prospect_id` added for referral tracking
- `notes` is static context; running interaction log lives in `activities.notes`

---

## CONTACT_METHODS

```sql
CREATE TABLE contact_methods (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    prospect_id INTEGER NOT NULL,
    type TEXT NOT NULL,  -- 'email' or 'phone'
    value TEXT NOT NULL,
    label TEXT,  -- 'work', 'personal', 'cell', 'main'
    is_primary BOOLEAN DEFAULT 0,
    is_verified BOOLEAN DEFAULT 0,
    verified_date DATE,
    confidence_score INTEGER DEFAULT 0,
    is_suspect BOOLEAN DEFAULT 0,  -- Flagged as potentially wrong
    source TEXT,  -- Where it was found
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (prospect_id) REFERENCES prospects(id) ON DELETE CASCADE
);

CREATE INDEX idx_contact_methods_prospect ON contact_methods(prospect_id);
CREATE INDEX idx_contact_methods_email ON contact_methods(value) WHERE type='email';
CREATE INDEX idx_contact_methods_phone ON contact_methods(value) WHERE type='phone';
```

---

## ACTIVITIES

```sql
CREATE TABLE activities (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    prospect_id INTEGER NOT NULL,
    activity_type TEXT NOT NULL,
    outcome TEXT,
    
    -- CALL TRACKING (NEW)
    call_duration_seconds INTEGER,  -- Duration in seconds
    
    -- POPULATION & STAGE TRACKING
    population_before TEXT,
    population_after TEXT,
    stage_before TEXT,
    stage_after TEXT,
    
    -- EMAIL TRACKING
    email_subject TEXT,
    email_body TEXT,
    
    -- FOLLOW-UP
    follow_up_set DATETIME,
    
    -- ATTEMPT TRACKING
    attempt_type TEXT,  -- 'personal' or 'automated'
    
    -- NOTES
    notes TEXT,  -- The running log - the enduring memory
    
    created_by TEXT,  -- 'user' or 'system'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (prospect_id) REFERENCES prospects(id) ON DELETE CASCADE
);

CREATE INDEX idx_activities_prospect ON activities(prospect_id);
CREATE INDEX idx_activities_date ON activities(created_at);
CREATE INDEX idx_activities_type ON activities(activity_type);
```

**Key decision:**
- `call_duration_seconds` added - differentiates 45-second no-answer from 20-minute discovery call

---

## DATA_FRESHNESS

```sql
CREATE TABLE data_freshness (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    prospect_id INTEGER NOT NULL,
    field_name TEXT NOT NULL,
    verified_date DATE NOT NULL,
    verification_method TEXT,
    confidence INTEGER,
    previous_value TEXT,
    
    FOREIGN KEY (prospect_id) REFERENCES prospects(id) ON DELETE CASCADE
);

CREATE INDEX idx_freshness_prospect ON data_freshness(prospect_id);
CREATE INDEX idx_freshness_date ON data_freshness(verified_date);
```

---

## IMPORT_SOURCES

```sql
CREATE TABLE import_sources (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_name TEXT NOT NULL,
    filename TEXT,
    total_records INTEGER,
    imported_records INTEGER,
    duplicate_records INTEGER,
    broken_records INTEGER,
    dnc_blocked_records INTEGER,
    import_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_import_date ON import_sources(import_date);
```

---

## RESEARCH_QUEUE

```sql
CREATE TABLE research_queue (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    prospect_id INTEGER NOT NULL,
    priority INTEGER DEFAULT 0,
    status TEXT DEFAULT 'pending',  -- 'pending', 'in_progress', 'completed', 'failed'
    attempts INTEGER DEFAULT 0,
    last_attempt_date TIMESTAMP,
    findings TEXT,  -- JSON
    
    FOREIGN KEY (prospect_id) REFERENCES prospects(id) ON DELETE CASCADE
);

CREATE INDEX idx_research_prospect ON research_queue(prospect_id);
CREATE INDEX idx_research_status ON research_queue(status);
```

---

## INTEL_NUGGETS

```sql
CREATE TABLE intel_nuggets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    prospect_id INTEGER NOT NULL,
    category TEXT NOT NULL,  -- 'pain_point', 'competitor', 'loan_type', 'decision_timeline', 'key_fact'
    content TEXT NOT NULL,
    source_activity_id INTEGER,
    extracted_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (prospect_id) REFERENCES prospects(id) ON DELETE CASCADE,
    FOREIGN KEY (source_activity_id) REFERENCES activities(id)
);

CREATE INDEX idx_nuggets_prospect ON intel_nuggets(prospect_id);
CREATE INDEX idx_nuggets_category ON intel_nuggets(category);
```

---

## PROSPECT_TAGS

```sql
CREATE TABLE prospect_tags (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    prospect_id INTEGER NOT NULL,
    tag_name TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (prospect_id) REFERENCES prospects(id) ON DELETE CASCADE,
    UNIQUE(prospect_id, tag_name)
);

CREATE INDEX idx_tags_prospect ON prospect_tags(prospect_id);
CREATE INDEX idx_tags_name ON prospect_tags(tag_name);
```

**Tags are flexible labels:**
- "hot-referral", "conference-lead", "needs-pricing-call"
- Filterable in Pipeline tab
- Visible on cards
- Bulk-applicable
- No transition rules, don't affect cadence or DNC

---

## SCHEMA_VERSION

```sql
CREATE TABLE schema_version (
    version INTEGER PRIMARY KEY,
    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

INSERT INTO schema_version (version) VALUES (1);
```

---

## ENUMERATIONS

All stored as TEXT in SQLite.

### Population
- `broken` - Missing phone or email
- `unengaged` - Complete data, Jeff is chasing, system-paced
- `engaged` - Showed interest, prospect-paced
- `parked` - Date-specific pause, auto-reactivates
- `dead_dnc` - Do Not Contact, permanent, absolute
- `lost` - Went with competitor or decided not to buy
- `partnership` - Non-prospect contact
- `closed_won` - Deal closed, $$$

### EngagementStage
Only used when population='engaged':
- `pre_demo` - Working toward scheduling
- `demo_scheduled` - Date certain on calendar
- `post_demo` - Warming tray, percolating
- `closing` - Active contract negotiation

### ActivityType
- `call`
- `voicemail`
- `email_sent`
- `email_received`
- `demo`
- `demo_scheduled`
- `demo_completed`
- `note`
- `status_change`
- `skip`
- `defer`
- `import`
- `enrichment`
- `verification`
- `reminder`
- `task`

### ActivityOutcome
- `no_answer`
- `left_vm`
- `spoke_with`
- `interested`
- `not_interested`
- `not_now`
- `demo_set`
- `demo_completed`
- `closed_won`
- `closed_lost`
- `bounced`
- `replied`
- `ooo` (out of office)
- `referral`

### DeadReason
- `dnc` - Do Not Contact (permanent, absolute, no exceptions)

### LostReason
- `lost_to_competitor`
- `not_buying`
- `timing`
- `budget`
- `out_of_business`

### ContactMethodType
- `email`
- `phone`

### AttemptType
- `personal` - Jeff's direct outreach
- `automated` - System-sent nurture

### ResearchStatus
- `pending`
- `in_progress`
- `completed`
- `failed`

### IntelCategory
- `pain_point`
- `competitor`
- `loan_type`
- `decision_timeline`
- `key_fact`

---

## TIMEZONE LOOKUP

```python
STATE_TO_TIMEZONE = {
    'AL': 'central', 'AK': 'alaska', 'AZ': 'mountain',
    'AR': 'central', 'CA': 'pacific', 'CO': 'mountain',
    'CT': 'eastern', 'DE': 'eastern', 'FL': 'eastern',
    'GA': 'eastern', 'HI': 'hawaii', 'ID': 'mountain',
    'IL': 'central', 'IN': 'eastern', 'IA': 'central',
    'KS': 'central', 'KY': 'eastern', 'LA': 'central',
    'ME': 'eastern', 'MD': 'eastern', 'MA': 'eastern',
    'MI': 'eastern', 'MN': 'central', 'MS': 'central',
    'MO': 'central', 'MT': 'mountain', 'NE': 'central',
    'NV': 'pacific', 'NH': 'eastern', 'NJ': 'eastern',
    'NM': 'mountain', 'NY': 'eastern', 'NC': 'eastern',
    'ND': 'central', 'OH': 'eastern', 'OK': 'central',
    'OR': 'pacific', 'PA': 'eastern', 'RI': 'eastern',
    'SC': 'eastern', 'SD': 'central', 'TN': 'central',
    'TX': 'central', 'UT': 'mountain', 'VT': 'eastern',
    'VA': 'eastern', 'WA': 'pacific', 'WV': 'eastern',
    'WI': 'central', 'WY': 'mountain'
}
```

---

## FIXES APPLIED IN v3.3

**Schema additions:**
1. Added `first_name`, `last_name`, `title` to prospects (previously missing)
2. Changed `follow_up_date` from DATE to DATETIME (supports hour-specific scheduling)
3. Added `preferred_contact_method` to prospects (email/phone preference)
4. Added `call_duration_seconds` to activities (distinguish call types)
5. Added `referred_by_prospect_id` to prospects (referral tracking with FK)

**All fixes requested by Jeff on 2026-02-05 are now in the schema.**

---

**See also:**
- `ARCHITECTURE-OVERVIEW.md` - The big picture
- `layers/LAYER-1-SLAB.md` - Database implementation details
- `build/PHASE-1-SLAB.md` - Build steps and tests
