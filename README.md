# D&D Scheduler Bot

A Discord bot for scheduling D&D sessions across multiple campaigns with multi-timezone support, RSVP tracking, and automated reminders.

## Features

- **Multi-Campaign Support**: Manage multiple campaigns within a single server using unique slugs.
- **Flexible Scheduling**: Propose multiple times for a session and let players RSVP.
- **Timezone Awareness**: Users can set their own timezones; inputs are parsed and displayed correctly using Discord timestamps.
- **Automated Reminders**: Configurable reminders (e.g., "24h, 1h" before session) sent to the channel.
- **Roles & Permissions**: Restrict campaign management to DMs or Admins.
- **Persistent Data**: Powered by PostgreSQL.

## Discord Setup

1.  Go to the [Discord Developer Portal](https://discord.com/developers/applications).
2.  Click **New Application** and give it a name.
3.  Go to the **Bot** tab and click **Add Bot**.
4.  Click **Reset Token** to generate a new token. Copy it immediately (you won't see it again!). This goes into your `.env` file as `DISCORD_TOKEN`.
5.  Enable **Message Content Intent** and **Server Members Intent** under the "Privileged Gateway Intents" section.
6.  Go to the **OAuth2** -> **URL Generator** tab.
7.  Select **bot** and **applications.commands** in the "Scopes" section.
8.  Scroll down to the "Bot Permissions" section and select permissions: `Send Messages`, `Embed Links`, `Attach Files`, `Manage Messages` (for pinning/deleting), `Read Message History`.
9.  Scroll to the very bottom of the page. You will see a field labeled **Generated URL**. Copy this URL and paste it into your browser to invite the bot.

## Deployment with Docker

1.  **Clone the repository**:
    ```bash
    git clone <repository_url>
    cd dnd-scheduler-bot
    ```

2.  **Configure Environment**:
    Create a `.env` file (see `.env.example` if available, or use the provided template):
    ```env
    DISCORD_TOKEN=your_discord_bot_token
    DATABASE_URL=postgresql+asyncpg://dndbot:dndbotpassword@postgres:5432/dndscheduler
    POSTGRES_USER=dndbot
    POSTGRES_PASSWORD=dndbotpassword
    POSTGRES_DB=dndscheduler
    LOG_LEVEL=INFO
    ```

3.  **Start Services**:
    ```bash
    docker-compose up -d --build
    ```
    This will start the PostgreSQL database and the Bot container. The bot will automatically run database migrations on startup.

## Development Setup

1.  **Install Dependencies**:
    Requires Python 3.11+.
    ```bash
    pip install -e .
    ```

2.  **Run Database**:
    You need a PostgreSQL database running. You can use Docker for just the DB:
    ```bash
    docker-compose up -d postgres
    ```

3.  **Run Migrations**:
    ```bash
    alembic upgrade head
    ```

4.  **Start Bot**:
    ```bash
    python -m src.bot
    ```

## Commands

### Campaign
- `/campaign create [name] [slug] [description] [role]`: Create a new campaign.
- `/campaign list`: List all campaigns.
- `/campaign config [slug] [role] [default_reminders]`: Configure settings.

### Session
- `/session propose [campaign] [title] [times] [timezone] ...`: Propose a session.
  - `times`: Comma-separated list of times (e.g. `2023-10-31 19:00, 2023-11-01 20:00`).
  - `reminders`: Optional override (e.g. `12h, 30m`).
- `/session status [campaign]`: Show latest session status.
- `/session lock [campaign] [session_id] [option_index]`: Lock a session to a specific proposed time.
- `/session cancel [campaign] [session_id]`: Cancel a session.
- `/session close [campaign] [session_id]`: Archive/close a session.

### Timezone
- `/tz set [timezone]`: Set your preferred IANA timezone (e.g. `America/New_York`).
- `/tz show`: Show your current setting.

## Architecture
- **Language**: Python 3.11
- **Library**: discord.py 2.x
- **Database**: PostgreSQL + SQLAlchemy (Async)
- **Migrations**: Alembic
- **Containerization**: Docker
