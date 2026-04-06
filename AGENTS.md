# Antigravity Agent Rules & Interaction Protocol

## 🚨 CRITICAL INTERACTION PROTOCOL (Must Follow)

The Antigravity Agent must strictly adhere to the following procedure before writing any code:

1.  **Stop & Review**: When the user initiates a step (e.g., "Step X를 시작해"), **DO NOT** write code immediately. First, analyze the **[Requirements]** and **[Technical Issues]** for that specific step.
2.  **Ask Decisions & Credentials**: After analysis, list any **"Decisions required by the user"** or **"Information needing input (API Keys, etc.)"** and ask the user for them first.
3.  **Wait for Confirmation**: Do not write code until the user provides answers or approval.
4.  **Code & Verify**: Once approved, write the code and report the [Checklist] verification results.

## Project Context
- **Project Name**: MarketPulse-Reg (Pilot)
- **Goal**: Collect press releases from 5 major agencies (FSC, FSS, MOEF, BOK, MAFRA) every 10 minutes, analyze banking sector impact using Gemini, and deliver via Telegram/Web.
- **Pilot Constraint**: 10-minute execution interval.

## Tech Stack
- **Core**: Python 3.10+, Next.js 14, Supabase
- **AI**: Gemini 1.5 Pro / 2.0 Flash
- **Infra**: Oracle Cloud Free Tier, Docker
- **Messaging**: Telegram Bot API
- **Scheduler**: APScheduler
