import asyncio
import discord
from discord.ext import commands
import logging
import logging.config
import os
from .config import settings
from .database import engine, Base

# Setup logging
logging.basicConfig(level=settings.LOG_LEVEL)
logger = logging.getLogger("src.bot")

class DnDSchedulerBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True # Needed for some interactions
        intents.members = True # Useful for role checks/mentions
        
        super().__init__(
            command_prefix=commands.when_mentioned,
            intents=intents,
            help_command=None, # We'll use app commands mostly
            description="D&D Scheduling Bot"
        )
        
        # We will load cogs in setup_hook
        self.initial_extensions = [
            "src.cogs.campaign",
            "src.cogs.session",
            "src.cogs.timezone",
            #"src.cogs.reminders" # Will implement later
        ]

    async def setup_hook(self):
        # Initialize DB engine? (It's global but good to check connection)
        # In production, we might want to run Alembic upgrades here programmatically
        # or via the Docker CMD.
        
        # Load extensions
        for ext in self.initial_extensions:
            try:
                await self.load_extension(ext)
                logger.info(f"Loaded extension {ext}")
            except Exception as e:
                logger.error(f"Failed to load extension {ext}: {e}", exc_info=True)
                
        # Register persistent views
        from src.ui.views import SessionRSVPView
        self.add_view(SessionRSVPView())
        
        # Sync app commands
        if settings.TEST_GUILD_ID:
            guild = discord.Object(id=settings.TEST_GUILD_ID)
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)
            logger.info(f"Synced commands to guild {settings.TEST_GUILD_ID}")
        else:
            # Sync global commands (can take up to an hour to propagate)
            # await self.tree.sync() 
            # Note: Do not sync globally on every startup in dev
            pass

    async def on_ready(self):
        logger.info(f"Logged in as {self.user} (ID: {self.user.id})")
        logger.info(f"Connected to db: {settings.DATABASE_URL}")

    async def close(self):
        await super().close()
        await engine.dispose()
        logger.info("Bot shutdown complete.")

async def main():
    async with DnDSchedulerBot() as bot:
        await bot.start(settings.DISCORD_TOKEN.get_secret_value())

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        # Handle Ctrl+C gracefully
        pass
