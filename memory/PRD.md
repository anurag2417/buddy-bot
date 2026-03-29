# BuddyBot - Children's AI Chatbot PRD

## Problem Statement
Build a Chatbot/AI Assistant with a conversational UI specifically designed for children, with a hidden moderation layer using ReAct pattern. Enhanced with a Chrome Extension that tracks browsing activity and feeds it into the AI safety system.

## Architecture
- **Frontend**: React + Tailwind CSS (Nunito/Quicksand fonts, pastel theme)
- **Backend**: FastAPI + MongoDB + emergentintegrations (OpenAI gpt-4.1-mini)
- **Chrome Extension**: Manifest V3, tracks searches + URLs, filters ads/tracking, syncs to backend
- **Database**: MongoDB (test_database) - collections: conversations, messages, alerts, browsing_packets

## User Personas
1. **Child (5-12 years)**: Uses chat interface, sees safety indicator while browsing
2. **Parent/Guardian**: Uses dashboard to monitor conversations, browsing, and safety alerts

## Core Requirements (Static)
- Child-friendly chat interface with playful design
- AI companion using ReAct safety thinking pattern
- Hard-coded profanity/safety filter middleware
- Restricted topic detection (violence, privacy, adult content, substance, self-harm)
- Parent Dashboard with stats, alerts, conversation logs, and browsing activity
- Chrome Extension for browsing monitoring (normal + incognito)
- PIN-protected extension settings
- Visible safety indicator for transparency
- AI-powered browsing pattern analysis

## What's Been Implemented

### Phase 1 (March 28, 2026)
1. Chat Page (`/`): Sidebar, new chat, message input, typing indicator
2. AI Engine: ReAct pattern with [THOUGHT], [SAFETY], [RESPONSE] parsing
3. Safety Layer: Profanity filter (60+ blocked words), restricted topic detection (5 categories)
4. Parent Dashboard (`/parent`): Stats, alerts, conversations, resolve alerts
5. Conversation Detail: Full message thread with AI thoughts, safety badges

### Phase 2 (March 29, 2026)
6. **Chrome Extension** (`/app/extension/`):
   - manifest.json (Manifest V3), background.js (service worker), content.js
   - Popup (popup.html/js/css): Status display, recent activity, PIN-gated toggle/settings
   - Options page (options.html/js/css): Server URL config, PIN setup, incognito guide, data clear
   - Filters out ads, tracking, CDN, static assets (FILTERED_DOMAINS + FILTERED_EXTENSIONS)
   - Tracks search queries from Google, Bing, YouTube, DuckDuckGo, Yahoo
   - Supports incognito mode (requires user to enable "Allow in Incognito")
   - Visible "BuddyBot is keeping you safe" indicator on search pages
   - Periodic sync (every 30s) to backend via alarms API
7. **Backend Extension Endpoints**:
   - POST /api/extension/packets - Receive & store browsing packets, auto-create alerts
   - GET /api/extension/status/:device_id - Device statistics
   - GET /api/parent/browsing/stats - Browsing overview stats
   - GET /api/parent/browsing/searches - Recent search queries with flags
   - GET /api/parent/browsing/visits - Recent URL visits
   - GET /api/parent/browsing/analysis - AI-powered browsing pattern analysis
8. **Enhanced AI**: Chat now includes browsing context from extension data
9. **Updated Parent Dashboard**: New Browsing Activity tab with stats, searches, visits, AI analysis button

## API Endpoints
### Chat
- POST /api/chat/send
- POST /api/chat/conversations
- GET /api/chat/conversations
- GET /api/chat/conversations/:id

### Extension
- POST /api/extension/packets
- GET /api/extension/status/:device_id

### Parent Dashboard
- GET /api/parent/dashboard
- GET /api/parent/alerts
- PUT /api/parent/alerts/:id/resolve
- GET /api/parent/conversations
- GET /api/parent/conversations/:id
- GET /api/parent/browsing/stats
- GET /api/parent/browsing/searches
- GET /api/parent/browsing/visits
- GET /api/parent/browsing/analysis

## Backlog
### P0 (Critical)
- Top up Emergent LLM key balance for continued AI responses

### P1 (Next)
- Extension distribution (Chrome Web Store packaging)
- Real-time WebSocket notifications for parent alerts
- Multiple child profiles with individual tracking

### P2
- Weekly safety digest email reports
- Adjustable safety sensitivity levels
- Time-based usage limits
- Domain whitelisting/blacklisting in extension

### P3
- Voice input/output for younger children
- Achievement/reward system
- Multi-language support
