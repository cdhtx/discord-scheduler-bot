import discord
from discord import app_commands
from discord.ext import commands
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from src.database import AsyncSessionLocal
from src.models import UserConfig
from src.utils import EmbedBuilder
import pytz

class TimezoneCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    tz_group = app_commands.Group(name="tz", description="Manage your timezone settings")

    @tz_group.command(name="set", description="Set your timezone (e.g. US/Eastern, UTC)")
    @app_commands.describe(timezone="Your IANA timezone (e.g. America/New_York)")
    async def set_timezone(self, interaction: discord.Interaction, timezone: str):
        # Validate timezone flexibly (case-insensitive)
        matched_tz = next((tz for tz in pytz.all_timezones if tz.lower() == timezone.lower()), None)
        if not matched_tz:
             await interaction.response.send_message(embed=EmbedBuilder.error("Invalid Timezone", "Please provide a valid IANA timezone name (e.g. `America/New_York`, `UTC`, `Europe/London`)."), ephemeral=True)
             return
             
        timezone = matched_tz # Use the correctly capitalized version
        async with AsyncSessionLocal() as session:
            # Upsert
            stmt = insert(UserConfig).values(user_id=interaction.user.id, timezone=timezone)
            stmt = stmt.on_conflict_do_update(
                index_elements=[UserConfig.user_id],
                set_={"timezone": timezone}
            )
            await session.execute(stmt)
            await session.commit()
            
            await interaction.response.send_message(embed=EmbedBuilder.success("Timezone Set", f"Your timezone has been set to `{timezone}`."), ephemeral=True)

    @tz_group.command(name="show", description="Show your current timezone")
    async def show_timezone(self, interaction: discord.Interaction):
        async with AsyncSessionLocal() as session:
            result = await session.execute(select(UserConfig).where(UserConfig.user_id == interaction.user.id))
            config = result.scalar_one_or_none()
            
            if config:
                await interaction.response.send_message(embed=EmbedBuilder.info("Your Timezone", f"Current setting: `{config.timezone}`"), ephemeral=True)
            else:
                await interaction.response.send_message(embed=EmbedBuilder.info("Your Timezone", "You have not set a timezone yet. Defaulting to UTC."), ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(TimezoneCog(bot))
