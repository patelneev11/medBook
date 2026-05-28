# Session 02 — Frontend Skeleton & Design System

## What Was Built

### Design system (`app/globals.css`, `app/layout.tsx`)
- Full CSS custom-property token system: 9 light-mode and 9 dark-mode tokens for backgrounds, text, borders, and brand colours
- Class-based dark mode via `@custom-variant dark` (toggled by `.dark` on `<html>`)
- Custom font-size scale: 12 / 13 / 14 / 15 / 18 / 22 / 28 / 36 px
- Warm off-white page background (`#F7F7F5` light, `#242424` dark), relaxed body line-height (1.65), tight heading line-height (1.25)
- Thin warm scrollbars using CSS variables
- 150 ms ease transition on background-color and colour for smooth dark/light toggle
- Inter font loaded via `next/font/google` with CSS variable `--font-inter`

### UI components (`components/ui/`)
| File | What it does |
|---|---|
| `Button.tsx` | primary / secondary / danger variants, loading spinner, disabled state, full-width via `className` prop |
| `Input.tsx` | label, placeholder, error state, disabled state, all input types |
| `Card.tsx` | white card with warm border, `--shadow-sm`, rounded corners |
| `Badge.tsx` | green (active) / gray (inactive) / blue (info) / red (error) pill variants |
| `Spinner.tsx` | sm / md / lg animated SVG spinner |
| `ThemeToggle.tsx` | Sun/Moon icon button; reads/writes `localStorage` key `mednotebook-theme`; syncs `.dark` class to `<html>` |

### Layout components (`components/layout/`)
| File | What it does |
|---|---|
| `Sidebar.tsx` | Fixed 240 px sidebar with logo, 5 nav links (active highlight), user avatar at bottom |
| `TopBar.tsx` | Page title (derived from pathname), search bar, ThemeToggle, bell icon, user avatar |
| `DashboardShell.tsx` | Client wrapper that owns mobile sidebar state; renders backdrop overlay, sidebar, topbar, and main content area |

### Pages
| File | Route | Description |
|---|---|---|
| `app/page.tsx` | `/` | "MedNotebook — Coming soon" placeholder |
| `app/login/page.tsx` | `/login` | Login form (email + password); "Sign in" → `/dashboard` |
| `app/signup/page.tsx` | `/signup` | Sign-up form (name + email + password + ToS checkbox); "Create account" → `/dashboard` |
| `app/preview/page.tsx` | `/preview` | Component preview: buttons, inputs, cards, badges, spinners, typography, colour swatches |
| `app/(dashboard)/layout.tsx` | — | Dashboard route group wrapper — renders `DashboardShell` |
| `app/(dashboard)/dashboard/page.tsx` | `/dashboard` | 4-stat cards, recent documents, recent activity, quick actions |
| `app/(dashboard)/dashboard/documents/page.tsx` | `/dashboard/documents` | Filter bar (search + type + sort dropdowns), empty state with upload CTA |
| `app/(dashboard)/dashboard/projects/page.tsx` | `/dashboard/projects` | "New project" button, empty state |
| `app/(dashboard)/dashboard/ask/page.tsx` | `/dashboard/ask` | Two-column chat UI (60/40); example question pills; disabled send with tooltip; sources panel |
| `app/(dashboard)/dashboard/settings/page.tsx` | `/dashboard/settings` | Left-nav (Profile / Team / Storage / Billing / Security); Profile form; others show "coming soon" |

---

## Frontend File Tree

```
frontend/
├── app/
│   ├── (dashboard)/
│   │   ├── layout.tsx                    # Wraps all /dashboard/* routes
│   │   └── dashboard/
│   │       ├── page.tsx                  # /dashboard
│   │       ├── ask/
│   │       │   └── page.tsx              # /dashboard/ask
│   │       ├── documents/
│   │       │   └── page.tsx              # /dashboard/documents
│   │       ├── projects/
│   │       │   └── page.tsx              # /dashboard/projects
│   │       └── settings/
│   │           └── page.tsx              # /dashboard/settings
│   ├── login/
│   │   └── page.tsx                      # /login
│   ├── signup/
│   │   └── page.tsx                      # /signup
│   ├── preview/
│   │   └── page.tsx                      # /preview
│   ├── globals.css                        # Design tokens, dark mode, typography
│   ├── layout.tsx                         # Root layout (Inter font, suppressHydrationWarning)
│   └── page.tsx                           # / (coming soon)
├── components/
│   ├── layout/
│   │   ├── DashboardShell.tsx             # Mobile sidebar state, shell wrapper
│   │   ├── Sidebar.tsx                    # Left navigation
│   │   └── TopBar.tsx                     # Header bar
│   └── ui/
│       ├── Badge.tsx
│       ├── Button.tsx
│       ├── Card.tsx
│       ├── Input.tsx
│       ├── Spinner.tsx
│       └── ThemeToggle.tsx
├── public/
├── package.json
├── tsconfig.json
├── postcss.config.mjs
└── next.config.ts
```

---

## All Routes

| Route | Page | Notes |
|---|---|---|
| `/` | Coming soon | Will redirect to `/login` once auth is wired |
| `/login` | Login | Redirects to `/dashboard` (no real auth yet) |
| `/signup` | Sign up | Redirects to `/dashboard` (no real auth yet) |
| `/preview` | Design system preview | Dev-only; not linked from the main nav |
| `/dashboard` | Main dashboard | Stats, recent docs, recent activity, quick actions |
| `/dashboard/documents` | Documents | Filter bar + empty state |
| `/dashboard/projects` | Projects | Empty state |
| `/dashboard/ask` | Ask AI | Chat UI + sources panel |
| `/dashboard/settings` | Settings | Profile form; other sections are stubs |

---

## Placeholder / Not Yet Wired Up

| Feature | Status |
|---|---|
| Authentication | None. All pages are freely accessible. `/login` and `/signup` redirect to `/dashboard` unconditionally. |
| Route protection | No middleware guarding `/dashboard/*` routes from unauthenticated users. |
| File upload | Upload buttons exist but have no `onClick` handlers. No S3 integration. |
| Document list | Documents page shows empty state only. No real data. |
| Projects | Projects page shows empty state only. No real data. |
| Ask AI | Chat UI built but `HAS_DOCUMENTS = false` keeps send button disabled. No API calls. |
| Search | TopBar search input is purely visual. No search logic. |
| Notifications | Bell icon is visual only. |
| Settings save | "Save changes" button has no API call behind it. |
| User profile | Sidebar and TopBar show hardcoded "John Doe / JD". |
| Dark mode on first load | On first visit, the page renders with light-mode CSS, then ThemeToggle runs client-side. If the user had previously selected dark, there will be a brief flash of light before the `.dark` class is applied. Fix in a future session by reading the preference in a `<script>` tag in `layout.tsx` before React hydrates. |

---

## Known Issues / Watch-outs for Future Sessions

1. **Dark mode flash on reload** — `ThemeToggle` applies `.dark` in a client-side effect. If the user has dark mode saved, there is a very brief flash of light on page load. The standard fix is an inline `<script>` in the `<head>` that adds `.dark` synchronously before hydration. Consider adding in Session 9 when auth and UX polish are addressed.

2. **`HAS_DOCUMENTS` constant in ask/page.tsx** — Currently hardcoded `false`. Once document upload is built (Session 5), replace this with a real check (e.g. a prop or context value from the API).

3. **`next.config.ts` Turbopack warning** — Dev server prints a workspace-root warning about multiple `package-lock.json` files. Harmless but can be silenced by setting `turbopack.root` in `next.config.ts` when convenient.

4. **`app/(dashboard)/layout.tsx` is a server component** — It wraps `DashboardShell` (a client component). This is correct, but be careful not to add server-only code (DB calls, headers) to it until auth middleware is in place — otherwise unauthenticated users could trigger server logic.

5. **Sidebar hover implemented with inline `onMouseEnter/Leave`** — Used because Tailwind `dark:` and CSS-variable hover classes conflict in Tailwind v4. A cleaner long-term solution is a dedicated `NavLink` component with a CSS Module or a `group` utility.

---

## Session 03 — What Gets Built Next

**FastAPI backend + PostgreSQL database setup:**

- Install and configure PostgreSQL with the `pgvector` extension
- Define the SQLAlchemy data models:
  - `User` (id, email, hashed_password, name, created_at)
  - `Document` (id, user_id, filename, file_type, s3_key, extracted_text, created_at)
  - `DocumentChunk` (id, document_id, chunk_index, content, embedding vector)
  - `Project` (id, user_id, name, description, created_at)
- Write Alembic database migrations
- Create a `database.py` connection module with session management
- Add a `/health` endpoint that verifies the database connection is live
- Set up a local PostgreSQL instance (or Docker) for development
- Document how to run migrations and seed test data
