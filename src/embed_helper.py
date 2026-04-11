import discord
from src.models import Session, SessionOption, SessionRSVP, RSVPStatus, SessionStatus
from src.utils import format_timestamp, parse_datetime
from typing import List

def create_session_embed(session: Session, options: List[SessionOption], rsvps: List[SessionRSVP], dm_member: discord.Member = None):
    color = discord.Color.blue()
    if session.status == SessionStatus.SCHEDULED:
        color = discord.Color.green()
    elif session.status == SessionStatus.CANCELLED:
        color = discord.Color.red()
    elif session.status == SessionStatus.CLOSED:
        color = discord.Color.dark_grey()

    embed = discord.Embed(
        title=session.title,
        description=session.description or "No description provided.",
        color=color
    )
    
    if dm_member:
        embed.set_author(name=f"DM: {dm_member.display_name}", icon_url=dm_member.display_avatar.url)
    
    # Status field
    status_text = session.status.value
    if session.status == SessionStatus.PROPOSED:
        status_text = "📅 Proposed"
    elif session.status == SessionStatus.SCHEDULED:
        status_text = "✅ Scheduled"
    
    embed.add_field(name="Status", value=status_text, inline=True)
    embed.add_field(name="Quorum", value=str(session.quorum), inline=True)

    # Time info & RSVPs
    if session.selected_time:
        ts = format_timestamp(session.selected_time, "F")
        rel = format_timestamp(session.selected_time, "R")
        embed.add_field(name="Time", value=f"{ts} ({rel})", inline=False)
        
        # Display RSVPs for selected time
        yes_rsvps = [r for r in rsvps if r.status == RSVPStatus.YES]
        maybe_rsvps = [r for r in rsvps if r.status == RSVPStatus.MAYBE]
        no_rsvps = [r for r in rsvps if r.status == RSVPStatus.NO]

        def format_list(rsvps_list):
            if not rsvps_list:
                return "None"
            names = [f"<@{r.user_id}>" for r in rsvps_list]
            return ", ".join(names)

        embed.add_field(name=f"✅ Yes ({len(yes_rsvps)})", value=format_list(yes_rsvps), inline=False)
        if maybe_rsvps:
            embed.add_field(name=f"🤷 Maybe ({len(maybe_rsvps)})", value=format_list(maybe_rsvps), inline=False)
        if no_rsvps:
            embed.add_field(name=f"❌ No ({len(no_rsvps)})", value=format_list(no_rsvps), inline=False)

    elif options:
        for i, opt in enumerate(options, 1):
            ts = format_timestamp(opt.start_time, "F")
            rel = format_timestamp(opt.start_time, "R")
            
            # RSVPs for this option
            opt_rsvps = [r for r in rsvps if r.option_id == opt.id or r.option_id is None]
            yes_votes = [r for r in opt_rsvps if r.status == RSVPStatus.YES]
            maybe_votes = [r for r in opt_rsvps if r.status == RSVPStatus.MAYBE]
            no_votes = [r for r in opt_rsvps if r.status == RSVPStatus.NO]
            
            yes_votes.sort(key=lambda x: x.priority if x.priority is not None else 999)
            
            lines = []
            for y in yes_votes:
                prefix = f"**{y.priority}**" if y.priority else "✅"
                lines.append(f"{prefix}: <@{y.user_id}>")
            for m in maybe_votes:
                lines.append(f"🤷: <@{m.user_id}>")
            for n in no_votes:
                lines.append(f"❌: <@{n.user_id}>")
                
            val = "\n".join(lines) if lines else "*No votes yet*"
            embed.add_field(name=f"Option {i}: {ts} ({rel})", value=val, inline=True)
            
            if i % 2 == 0:
                 # Add empty field for formatting if we want 2 per row
                 pass
    else:
        embed.add_field(name="Time", value="TBD", inline=False)

    embed.set_footer(text=f"Session ID: {session.id}")
    return embed
