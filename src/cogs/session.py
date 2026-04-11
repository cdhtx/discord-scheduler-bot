import discord
from discord import app_commands
from discord.ext import commands
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from src.database import AsyncSessionLocal
from src.models import Session, SessionOption, SessionRSVP, Campaign, SessionStatus, Campaign
from src.utils import EmbedBuilder, parse_datetime
from src.embed_helper import create_session_embed
from src.ui.views import SessionRSVPView
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class SessionCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    session_group = app_commands.Group(name="session", description="Manage D&D sessions")

    @session_group.command(name="propose", description="Propose a new session")
    @app_commands.describe(
        campaign="Campaign slug",
        title="Session title",
        times="Proposed times (comma separated, Format: YYYY-MM-DD HH:mm)",
        description="Session description",
        timezone="Timezone for the times (e.g. US/Eastern, UTC)",
        quorum="Number of players needed",
        reminders="Reminders (e.g. '24h, 1h')"
    )
    async def propose_session(
        self, 
        interaction: discord.Interaction, 
        campaign: str, 
        title: str, 
        times: str,
        timezone: str = "UTC",
        description: str = None,
        quorum: int = 3,
        reminders: str = None
    ):
        await interaction.response.defer()
        
        async with AsyncSessionLocal() as session:
            # Find campaign
            stmt = select(Campaign).where(
                Campaign.guild_id == interaction.guild_id, 
                Campaign.slug == campaign
            )
            result = await session.execute(stmt)
            camp = result.scalar_one_or_none()
            
            if not camp:
                await interaction.followup.send(embed=EmbedBuilder.error("Error", f"Campaign `{campaign}` not found."))
                return

            # Parse times
            time_strs = [t.strip() for t in times.split(",")]
            parsed_options = []
            for ts in time_strs:
                dt = parse_datetime(ts, timezone)
                if not dt:
                    await interaction.followup.send(embed=EmbedBuilder.error("Error", f"Could not parse time: `{ts}`. Use YYYY-MM-DD HH:mm."))
                    return
                parsed_options.append(dt)
            
            if not parsed_options:
                await interaction.followup.send(embed=EmbedBuilder.error("Error", "No valid times provided."))
                return

            # Create Session
            new_session = Session(
                campaign_id=camp.id,
                title=title,
                description=description,
                status=SessionStatus.PROPOSED,
                quorum=quorum,
                reminders_config=reminders or camp.default_reminders
            )
            session.add(new_session)
            await session.flush() # Get ID
            
            # Create Options
            for dt in parsed_options:
                opt = SessionOption(session_id=new_session.id, start_time=dt)
                session.add(opt)
            
            # Commit to save DB objects
            await session.commit()
            
            # Now we need to send the message. 
            # We already have them.
            
            # But the 'create_session_embed' expects list of options and rsvps.
            # We just created options, rsvps is empty.
            # We also need DM member for embed.
            dm_member = interaction.guild.get_member(camp.dm_id)
            
            # Re-fetch options just to be safe/clean or use the ones we added (need to refresh attributes?)
            # Since we didn't expire on commit, the objects are still attached? 
            # AsyncSessionLocal has expire_on_commit=False.
            
            # Manually construct list for helper
            opts_list = [SessionOption(start_time=dt) for dt in parsed_options] # This assumes ID check in helper? No.
            
            # Let's re-fetch to be 100% consistent with the View logic
            stmt_opts = select(SessionOption).where(SessionOption.session_id == new_session.id).order_by(SessionOption.start_time)
            res_opts = await session.execute(stmt_opts)
            options_db = res_opts.scalars().all()
            
            embed = create_session_embed(new_session, options_db, [], dm_member)
            view = SessionRSVPView()
            
            # Send message
            target_channel = interaction.guild.get_channel(camp.channel_id) if camp.channel_id else interaction.channel
            if not target_channel:
                 target_channel = interaction.channel

            try:
                message = await target_channel.send(content=f"**New Session Proposal** for {camp.name}", embed=embed, view=view)
            except discord.Forbidden:
                 await interaction.followup.send(embed=EmbedBuilder.error("Error", f"Cannot send message to {target_channel.mention}. Check permissions."))
                 return

            # Update session with message ID
            new_session.message_id = message.id
            new_session.channel_id = target_channel.id
            await session.commit()
            
            if target_channel.id != interaction.channel_id:
                 await interaction.followup.send(f"Session proposed in {target_channel.mention}. **Session ID:** `{new_session.id}`", ephemeral=True)
            else:
                 await interaction.followup.send(f"Session proposed successfully. **Session ID:** `{new_session.id}`", ephemeral=True)

    @session_group.command(name="status", description="Get status of the latest session or specific session")
    async def session_status(self, interaction: discord.Interaction, campaign: str, session_id: int = None):
        await interaction.response.defer(ephemeral=True)
        async with AsyncSessionLocal() as session:
            # Find campaign
            stmt = select(Campaign).where(Campaign.guild_id == interaction.guild_id, Campaign.slug == campaign)
            res_c = await session.execute(stmt)
            camp = res_c.scalar_one_or_none()
            if not camp:
                 await interaction.followup.send(embed=EmbedBuilder.error("Error", "Campaign not found."))
                 return

            stmt_s = select(Session).where(Session.campaign_id == camp.id)
            if session_id:
                stmt_s = stmt_s.where(Session.id == session_id)
            else:
                stmt_s = stmt_s.order_by(Session.created_at.desc()).limit(1)
            
            res_s = await session.execute(stmt_s)
            sess_obj = res_s.scalar_one_or_none()
            
            if not sess_obj:
                await interaction.followup.send(embed=EmbedBuilder.info("Info", "No sessions found."))
                return

            # Fetch options and rsvps for display
            # We use selectinload or separate queries
            stmt_opts = select(SessionOption).where(SessionOption.session_id == sess_obj.id).order_by(SessionOption.start_time)
            res_opts = await session.execute(stmt_opts)
            options = res_opts.scalars().all()
            
            stmt_rsvps = select(SessionRSVP).where(SessionRSVP.session_id == sess_obj.id)
            res_rsvps = await session.execute(stmt_rsvps)
            rsvps = res_rsvps.scalars().all()
            
            dm_member = interaction.guild.get_member(camp.dm_id)
            
            embed = create_session_embed(sess_obj, options, rsvps, dm_member)
            # If we allow RSVP from here, we should attach the view.
            view = SessionRSVPView()
            
            await interaction.followup.send(embed=embed, view=view)

    @session_group.command(name="lock", description="Lock a session to a specific time")
    async def session_lock(
        self, 
        interaction: discord.Interaction, 
        campaign_slug: str, 
        session_id: int, 
        option_index: int
    ):
        # MVP: Lock to an option index (1-based)
        await interaction.response.defer(ephemeral=True)
        async with AsyncSessionLocal() as session:
             # Verify permissions (DM)
             # ... query campaign ...
             stmt = select(Campaign).where(Campaign.guild_id == interaction.guild_id, Campaign.slug == campaign_slug)
             res = await session.execute(stmt)
             camp = res.scalar_one_or_none()
             if not camp:
                  await interaction.followup.send("Campaign not found.")
                  return
                  
             if camp.dm_id != interaction.user.id and not interaction.user.guild_permissions.administrator:
                  await interaction.followup.send("Only the DM can lock sessions.")
                  return

             stmt_sess = select(Session).where(Session.id == session_id, Session.campaign_id == camp.id)
             res_sess = await session.execute(stmt_sess)
             sess_obj = res_sess.scalar_one_or_none()
             
             if not sess_obj:
                  await interaction.followup.send("Session not found.")
                  return
                  
             # Get Options
             stmt_opts = select(SessionOption).where(SessionOption.session_id == sess_obj.id).order_by(SessionOption.start_time)
             res_opts = await session.execute(stmt_opts)
             options = res_opts.scalars().all()
             
             if not 1 <= option_index <= len(options):
                  await interaction.followup.send("Invalid option index.")
                  return
                  
             selected = options[option_index-1]
             
             sess_obj.selected_time = selected.start_time
             sess_obj.status = SessionStatus.SCHEDULED
             
             # Create Reminders
             from src.models import ReminderJob, ReminderStatus
             from src.utils import parse_relative_reminders, format_timestamp
             
             # If using lazy loading for Session.campaign, we might need to load it or it's already in identity map.
             # We fetched camp separately to check DM.
             # Reminder config is on sess_obj now.
             
             config_str = sess_obj.reminders_config or camp.default_reminders
             if config_str:
                 remind_times = parse_relative_reminders(config_str, selected.start_time)
                 for rt in remind_times:
                     if rt > datetime.now(rt.tzinfo): # Only future reminders
                         job = ReminderJob(
                             session_id=sess_obj.id,
                             remind_at=rt,
                             status=ReminderStatus.PENDING,
                             message=f"**Reminder:** Session for **{camp.name}** is coming up at {format_timestamp(selected.start_time, 'F')} ({format_timestamp(selected.start_time, 'R')})!"
                         )
                         session.add(job)
             
             await session.commit()
             
             await interaction.followup.send(f"Session locked to {format_timestamp(selected.start_time)}.")
             
             # Trigger update on original message
             # That would be nice. I'll leave it as a TODO or implement if time permits.
             # Ideally we call view.update_message logic if we can target the message.
             
             if sess_obj.channel_id and sess_obj.message_id:
                 try:
                     chan = interaction.guild.get_channel(sess_obj.channel_id)
                     if chan:
                         msg = await chan.fetch_message(sess_obj.message_id)
                         # Fetch RSVPs for embed rebuild
                         stmt_rsvps = select(SessionRSVP).where(SessionRSVP.session_id == sess_obj.id)
                         res_rsvps = await session.execute(stmt_rsvps)
                         rsvps = res_rsvps.scalars().all()
                         
                         new_embed = create_session_embed(sess_obj, options, rsvps, interaction.user)
                         await msg.edit(embed=new_embed, view=SessionRSVPView())
                 except: 
                     logger.warning(f"Failed to update original message: {e}")

    @session_group.command(name="cancel", description="Cancel a session")
    async def session_cancel(self, interaction: discord.Interaction, campaign_slug: str, session_id: int):
         await interaction.response.defer(ephemeral=True)
         async with AsyncSessionLocal() as session:
             # Permissions check similar to lock
             stmt = select(Campaign).where(Campaign.guild_id == interaction.guild_id, Campaign.slug == campaign_slug)
             res = await session.execute(stmt)
             camp = res.scalar_one_or_none()
             
             if not camp or (camp.dm_id != interaction.user.id):
                  await interaction.followup.send("Permission denied or campaign not found.")
                  return

             stmt_sess = select(Session).where(Session.id == session_id, Session.campaign_id == camp.id)
             res_sess = await session.execute(stmt_sess)
             sess_obj = res_sess.scalar_one_or_none()
             
             if not sess_obj: 
                 await interaction.followup.send("Session not found.")
                 return
                 
             sess_obj.status = SessionStatus.CANCELLED
             await session.commit()
             
             await interaction.followup.send("Session cancelled.")
             
             # Update message
             if sess_obj.channel_id and sess_obj.message_id:
                 try:
                     chan = interaction.guild.get_channel(sess_obj.channel_id)
                     msg = await chan.fetch_message(sess_obj.message_id)
                     # Rebuild embed
                     stmt_opts = select(SessionOption).where(SessionOption.session_id == sess_obj.id)
                     res_opts = await session.execute(stmt_opts)
                     options = res_opts.scalars().all()
                     stmt_rsvps = select(SessionRSVP).where(SessionRSVP.session_id == sess_obj.id)
                     res_rsvps = await session.execute(stmt_rsvps)
                     rsvps = res_rsvps.scalars().all()
                     
                     new_embed = create_session_embed(sess_obj, options, rsvps, interaction.user)
                     await msg.edit(embed=new_embed, view=SessionRSVPView())
                 except: 
                     pass

    @session_group.command(name="close", description="Close a session (archive)")
    async def session_close(self, interaction: discord.Interaction, campaign_slug: str, session_id: int):
         await interaction.response.defer(ephemeral=True)
         async with AsyncSessionLocal() as session:
             stmt = select(Campaign).where(Campaign.guild_id == interaction.guild_id, Campaign.slug == campaign_slug)
             res = await session.execute(stmt)
             camp = res.scalar_one_or_none()
             
             if not camp or (camp.dm_id != interaction.user.id):
                  await interaction.followup.send("Permission denied or campaign not found.")
                  return

             stmt_sess = select(Session).where(Session.id == session_id, Session.campaign_id == camp.id)
             res_sess = await session.execute(stmt_sess)
             sess_obj = res_sess.scalar_one_or_none()
             
             if not sess_obj: 
                 await interaction.followup.send("Session not found.")
                 return
                 
             sess_obj.status = SessionStatus.CLOSED
             await session.commit()
             
             await interaction.followup.send("Session closed.")
             
             if sess_obj.channel_id and sess_obj.message_id:
                 try:
                     chan = interaction.guild.get_channel(sess_obj.channel_id)
                     msg = await chan.fetch_message(sess_obj.message_id)
                     # Rebuild embed
                     stmt_opts = select(SessionOption).where(SessionOption.session_id == sess_obj.id)
                     res_opts = await session.execute(stmt_opts)
                     options = res_opts.scalars().all()
                     stmt_rsvps = select(SessionRSVP).where(SessionRSVP.session_id == sess_obj.id)
                     res_rsvps = await session.execute(stmt_rsvps)
                     rsvps = res_rsvps.scalars().all()
                     
                     new_embed = create_session_embed(sess_obj, options, rsvps, interaction.user)
                     await msg.edit(embed=new_embed, view=None) # Remove view on close
                 except: 
                     pass

async def setup(bot: commands.Bot):
    await bot.add_cog(SessionCog(bot))

