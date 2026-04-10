import discord
from discord import app_commands
from discord.ext import commands
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from src.database import get_db, AsyncSessionLocal
from src.models import Campaign, GuildConfig
from src.utils import EmbedBuilder

class CampaignCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    campaign_group = app_commands.Group(name="campaign", description="Manage D&D campaigns")

    async def get_guild_config(self, session, guild_id: int):
        result = await session.execute(select(GuildConfig).where(GuildConfig.guild_id == guild_id))
        return result.scalar_one_or_none()

    @campaign_group.command(name="create", description="Create a new campaign")
    @app_commands.describe(
        name="Name of the campaign",
        slug="Unique identifier (slug) for the campaign",
        description="Brief description (optional)",
        role="Role associated with the campaign (optional)"
    )
    async def create_campaign(
        self, 
        interaction: discord.Interaction, 
        name: str, 
        slug: str, 
        description: str = None, 
        role: discord.Role = None
    ):
        await interaction.response.defer(ephemeral=True)
        
        async with AsyncSessionLocal() as session:
            # Check if slug exists in guild
            stmt = select(Campaign).where(Campaign.guild_id == interaction.guild_id, Campaign.slug == slug)
            result = await session.execute(stmt)
            if result.scalar_one_or_none():
                await interaction.followup.send(embed=EmbedBuilder.error("Error", f"Campaign with slug `{slug}` already exists."))
                return

            new_campaign = Campaign(
                guild_id=interaction.guild_id,
                name=name,
                slug=slug,
                description=description,
                dm_id=interaction.user.id,
                role_id=role.id if role else None
            )
            session.add(new_campaign)
            await session.commit()
            
            await interaction.followup.send(embed=EmbedBuilder.success("Campaign Created", f"Campaign **{name}** (`{slug}`) created successfully."))

    @campaign_group.command(name="list", description="List all campaigns in this server")
    async def list_campaigns(self, interaction: discord.Interaction):
        await interaction.response.defer()
        
        async with AsyncSessionLocal() as session:
            stmt = select(Campaign).where(Campaign.guild_id == interaction.guild_id)
            result = await session.execute(stmt)
            campaigns = result.scalars().all()
            
            if not campaigns:
                await interaction.followup.send(embed=EmbedBuilder.info("Campaigns", "No campaigns found in this server."))
                return

            embed = discord.Embed(title="Active Campaigns", color=discord.Color.gold())
            for c in campaigns:
                dm = interaction.guild.get_member(c.dm_id)
                dm_name = dm.display_name if dm else f"Unknown ({c.dm_id})"
                role_mention = f"<@&{c.role_id}>" if c.role_id else "None"
                embed.add_field(
                    name=f"{c.name} (`{c.slug}`)",
                    value=f"DM: {dm_name}\nRole: {role_mention}\n{c.description or ''}",
                    inline=False
                )
            
            await interaction.followup.send(embed=embed)

    @campaign_group.command(name="config", description="Configure campaign settings")
    @app_commands.describe(
        slug="Campaign slug",
        role="New role to associate",
        default_reminders="Default reminders (e.g. '24h, 1h')"
    )
    async def config_campaign(
        self, 
        interaction: discord.Interaction, 
        slug: str, 
        role: discord.Role = None,
        default_reminders: str = None
    ):
        # MVP: setting role and reminders
        await interaction.response.defer(ephemeral=True)
        
        async with AsyncSessionLocal() as session:
            stmt = select(Campaign).where(Campaign.guild_id == interaction.guild_id, Campaign.slug == slug)
            result = await session.execute(stmt)
            campaign = result.scalar_one_or_none()
            
            if not campaign:
                await interaction.followup.send(embed=EmbedBuilder.error("Error", "Campaign not found."))
                return
            
            # Check permissions (DM or Admin)
            if campaign.dm_id != interaction.user.id and not interaction.user.guild_permissions.administrator:
                await interaction.followup.send(embed=EmbedBuilder.error("Permission Denied", "Only the DM or an admin can configure this campaign."))
                return

            if role:
                campaign.role_id = role.id
            
            if default_reminders:
                campaign.default_reminders = default_reminders
            
            await session.commit()
            
            msg = f"Campaign `{slug}` updated."
            if role:
                msg += f"\nRole: {role.mention}"
            if default_reminders:
                msg += f"\nReminders: {default_reminders}"
                
            await interaction.followup.send(embed=EmbedBuilder.success("Updated", msg))

async def setup(bot: commands.Bot):
    await bot.add_cog(CampaignCog(bot))
