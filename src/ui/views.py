import discord
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from src.database import AsyncSessionLocal
from src.models import Session, SessionRSVP, RSVPStatus, SessionOption
from src.utils import EmbedBuilder, format_timestamp

class RSVPButton(discord.ui.Button):
    def __init__(self, status: RSVPStatus, label: str, style: discord.ButtonStyle):
        super().__init__(style=style, label=label, custom_id=f"rsvp_{status.value}")
        self.status = status

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer() # Acknowledge immediately
        view: SessionRSVPView = self.view
        await view.handle_rsvp(interaction, self.status)

class SessionRSVPView(discord.ui.View):
    def __init__(self, session_id: int):
        super().__init__(timeout=None) # Persistent view
        self.session_id = session_id
        self.add_item(RSVPButton(RSVPStatus.YES, "Yes", discord.ButtonStyle.success))
        self.add_item(RSVPButton(RSVPStatus.MAYBE, "Maybe", discord.ButtonStyle.secondary))
        self.add_item(RSVPButton(RSVPStatus.NO, "No", discord.ButtonStyle.danger))

    async def handle_rsvp(self, interaction: discord.Interaction, status: RSVPStatus):
        async with AsyncSessionLocal() as db_session:
            # check if session is still open
            stmt = select(Session).options(selectinload(Session.campaign)).where(Session.id == self.session_id)
            result = await db_session.execute(stmt)
            session_obj = result.scalar_one_or_none()
            
            if not session_obj:
                await interaction.followup.send("Session not found.", ephemeral=True)
                return

            if session_obj.status == "CLOSED" or session_obj.status == "CANCELLED":
                 await interaction.followup.send("This session is closed.", ephemeral=True)
                 return

            # Update or create RSVP
            rsvp_stmt = select(SessionRSVP).where(
                SessionRSVP.session_id == self.session_id,
                SessionRSVP.user_id == interaction.user.id
            )
            rsvp_result = await db_session.execute(rsvp_stmt)
            rsvp = rsvp_result.scalar_one_or_none()
            
            if rsvp:
                rsvp.status = status
            else:
                rsvp = SessionRSVP(
                    session_id=self.session_id,
                    user_id=interaction.user.id,
                    status=status
                )
                db_session.add(rsvp)
            
            await db_session.commit()
            
            # Refresh the message (requires fetching all RSVPs to update counts)
            # We can trigger a refresh method on the cog or re-render here.
            # Ideally we re-use the rendering logic.
            # specific update logic might be complex to duplicate. 
            # For now, let's just send a confirmation ephemeral? 
            # No, requirement says: "Clicking updates DB and edits embed with counts"
            
            # We need to re-generate the embed.
            # I'll define a static method or helper to generate the session embed
            await self.update_message(interaction, db_session, session_obj)

    async def update_message(self, interaction: discord.Interaction, db_session, session_obj):
        # Fetch RSVPs
        rsvps_stmt = select(SessionRSVP).where(SessionRSVP.session_id == self.session_id)
        rsvps_result = await db_session.execute(rsvps_stmt)
        rsvps = rsvps_result.scalars().all()
        
        # Calculate counts
        yes = [r for r in rsvps if r.status == RSVPStatus.YES]
        maybe = [r for r in rsvps if r.status == RSVPStatus.MAYBE]
        no = [r for r in rsvps if r.status == RSVPStatus.NO]
        
        # Re-build Embed (This duplicates logic from the Cog...)
        # Better to have a shared helper.
        from src.cogs.session import SessionCog # Circular import?
        # Avoid circular import by defining the embed builder in utils or passing it in
        
        # Let's import the helper function if we extract it, or implement simple version here
        embed = interaction.message.embeds[0]
        
        # Update fields for RSVPs
        # We need to find the fields corresponding to RSVPs and update them
        # Or just rebuild the whole description if it's there.
        # Let's assume a standard structure:
        # Field: "RSVPs" or separate fields for Yes/Maybe/No
        
        # Creating a new embed based on current state is safer
        new_embed = discord.Embed(
            title=session_obj.title,
            description=session_obj.description,
            color=embed.color
        )
        # Add time info (we might need to fetch options)
        # Verify if we have options loaded? NO.
        # We need to fetch options to fully rebuild.
        # This is getting heavy for the View.
        
        # Alternative: Call a helper in utils that takes the session object and RSVPs
        # I'll move `create_session_embed` to `src.utils` or a new `src.helpers` module later.
        # For now, I will just update the footer or specific fields if possible.
        
        # Let's just update the specific fields for counts.
        fields_to_keep = [f for f in embed.fields if not f.name.startswith("✅") and not f.name.startswith("🤷") and not f.name.startswith("❌") and not f.name == "Status"]

        # Re-construct fields
        new_embed.clear_fields()
        # Copy original fields (like Time, DM, etc)
        # This is tricky without the original data.
        # Just fetching everything again is safer.
        
        # Refresh logic
        # Fetch options to rebuild embed fully
        stmt_options = select(SessionOption).where(SessionOption.session_id == self.session_id).order_by(SessionOption.start_time)
        res_opts = await db_session.execute(stmt_options)
        options = res_opts.scalars().all()
        
        from src.embed_helper import create_session_embed
        
        dm_member = interaction.guild.get_member(session_obj.campaign.dm_id) if session_obj.campaign else None
        # Note: We need to join campaign to get DM ID, or fetch it separately. 
        # session_obj might not have campaign loaded if we didn't eager load.
        # Let's assume for now we just skip DM name if not loaded, or fetch it.
        
        embed = create_session_embed(session_obj, options, rsvps, dm_member)
        await interaction.message.edit(embed=embed, view=self) 
