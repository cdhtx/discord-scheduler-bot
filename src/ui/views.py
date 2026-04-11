import discord
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from src.database import AsyncSessionLocal
from src.models import Session, SessionRSVP, RSVPStatus, SessionOption, SessionStatus
from src.utils import EmbedBuilder, format_timestamp

class PreferenceSelect(discord.ui.Select):
    def __init__(self, option: SessionOption, option_index: int, total_options: int):
        self.option_id = option.id
        options = []
        for i in range(1, total_options + 1):
            label = f"{i}st Choice" if i == 1 else f"{i}nd Choice" if i == 2 else f"{i}rd Choice" if i == 3 else f"{i}th Choice"
            options.append(discord.SelectOption(label=label, value=f"PRIORITY_{i}"))
        options.append(discord.SelectOption(label="If need be (Maybe)", value="MAYBE"))
        options.append(discord.SelectOption(label="Cannot make it (No)", value="NO"))
        
        # Markdown discord timestamps don't render in dropdown placeholders
        # Use human readable format
        ts = option.start_time.strftime("%b %d, %I:%M %p")
        super().__init__(
            placeholder=f"Option {option_index}: {ts}", 
            options=options, 
            min_values=1, 
            max_values=1,
            custom_id=f"pref_opt_{option.id}"
        )

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()

class VoteFormView(discord.ui.View):
    def __init__(self, session_id: int, options: list[SessionOption], current_rsvps: list[SessionRSVP]):
        super().__init__(timeout=None)
        self.session_id = session_id
        self.options = options
        
        self.selects = []
        for i, opt in enumerate(options[:4], 1):
            select_menu = PreferenceSelect(opt, i, min(len(options), 4))
            pref = next((r for r in current_rsvps if r.option_id == opt.id), None)
            if pref:
                if pref.status == RSVPStatus.YES and pref.priority:
                    select_menu.placeholder += f" | Current: {pref.priority} Choice"
                elif pref.status:
                     select_menu.placeholder += f" | Current: {pref.status.value}"
            
            self.add_item(select_menu)
            self.selects.append(select_menu)
            
        save_btn = discord.ui.Button(label="💾 Save Votes", style=discord.ButtonStyle.success, row=len(self.selects))
        save_btn.callback = self.save_votes
        self.add_item(save_btn)

    async def save_votes(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        
        async with AsyncSessionLocal() as db_session:
            stmt = select(Session).where(Session.id == self.session_id)
            sess_obj = (await db_session.execute(stmt)).scalar_one_or_none()
            if not sess_obj or sess_obj.status in (SessionStatus.CLOSED, SessionStatus.CANCELLED, SessionStatus.SCHEDULED):
                await interaction.followup.send("This session is no longer open for voting.")
                return

            for select_menu in self.selects:
                if not select_menu.values:
                    continue
                    
                val = select_menu.values[0]
                status = RSVPStatus.YES
                priority = None
                
                if val == "MAYBE":
                    status = RSVPStatus.MAYBE
                elif val == "NO":
                    status = RSVPStatus.NO
                elif val.startswith("PRIORITY_"):
                    priority = int(val.split("_")[1])
                else: continue
                
                rsvp_stmt = select(SessionRSVP).where(
                    SessionRSVP.session_id == self.session_id,
                    SessionRSVP.user_id == interaction.user.id,
                    SessionRSVP.option_id == select_menu.option_id
                )
                rsvp = (await db_session.execute(rsvp_stmt)).scalar_one_or_none()
                
                if rsvp:
                    rsvp.status = status
                    rsvp.priority = priority
                else:
                    rsvp = SessionRSVP(
                        session_id=self.session_id,
                        user_id=interaction.user.id,
                        option_id=select_menu.option_id,
                        status=status,
                        priority=priority
                    )
                    db_session.add(rsvp)
            
            await db_session.commit()
            
            try:
                if sess_obj.channel_id and sess_obj.message_id:
                    chan = interaction.guild.get_channel(sess_obj.channel_id)
                    if chan:
                        orig_msg = await chan.fetch_message(sess_obj.message_id)
                        from src.embed_helper import create_session_embed
                        
                        stmt_options = select(SessionOption).where(SessionOption.session_id == self.session_id).order_by(SessionOption.start_time)
                        options = (await db_session.execute(stmt_options)).scalars().all()
                        
                        stmt_rsvps = select(SessionRSVP).where(SessionRSVP.session_id == self.session_id)
                        rsvps = (await db_session.execute(stmt_rsvps)).scalars().all()
                        
                        stmt_camp = select(Session).options(selectinload(Session.campaign)).where(Session.id == self.session_id)
                        c_sess_obj = (await db_session.execute(stmt_camp)).scalar_one_or_none()
                        dm_member = interaction.guild.get_member(c_sess_obj.campaign.dm_id) if c_sess_obj and c_sess_obj.campaign else None
                        
                        embed = create_session_embed(sess_obj, options, rsvps, dm_member)
                        await orig_msg.edit(embed=embed)
                        
            except Exception as e:
                import logging
                logging.getLogger(__name__).warning(f"Could not update original message: {e}")

            await interaction.followup.send("Votes saved successfully!", ephemeral=True)

class SessionRSVPView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        
    @discord.ui.button(label="🗳️ Vote on Times", style=discord.ButtonStyle.primary, custom_id="persistent_vote_btn")
    async def open_vote_form(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        async with AsyncSessionLocal() as db_session:
            # We track the session by the message that the button is attached to!
            stmt = select(Session).where(Session.message_id == interaction.message.id)
            sess_obj = (await db_session.execute(stmt)).scalar_one_or_none()
            if not sess_obj or sess_obj.status in (SessionStatus.CLOSED, SessionStatus.CANCELLED, SessionStatus.SCHEDULED):
                 await interaction.followup.send("This session is no longer open for voting.", ephemeral=True)
                 return
                 
            stmt_options = select(SessionOption).where(SessionOption.session_id == sess_obj.id).order_by(SessionOption.start_time)
            options = (await db_session.execute(stmt_options)).scalars().all()
            
            stmt_rsvps = select(SessionRSVP).where(
                SessionRSVP.session_id == sess_obj.id, 
                SessionRSVP.user_id == interaction.user.id
            )
            rsvps = (await db_session.execute(stmt_rsvps)).scalars().all()
            
            form_view = VoteFormView(sess_obj.id, options, rsvps)
            await interaction.followup.send("Please rank the proposed times by selecting your preference for each.", view=form_view, ephemeral=True)
