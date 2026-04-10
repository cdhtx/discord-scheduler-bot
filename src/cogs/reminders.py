import discord
from discord.ext import commands, tasks
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from src.database import AsyncSessionLocal
from src.models import ReminderJob, ReminderStatus, Session
from src.utils import get_aware_now
import logging
import asyncio

logger = logging.getLogger(__name__)

class ReminderCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.check_reminders.start()

    def cog_unload(self):
        self.check_reminders.cancel()

    @tasks.loop(seconds=30)
    async def check_reminders(self):
        try:
            async with AsyncSessionLocal() as session:
                now = get_aware_now()
                # Find pending reminders due now, or failed ones with < 3 retries
                stmt = select(ReminderJob).options(selectinload(ReminderJob.session).selectinload(Session.campaign))\
                    .where(
                        (ReminderJob.remind_at <= now) & 
                        ((ReminderJob.status == ReminderStatus.PENDING) | 
                         ((ReminderJob.status == ReminderStatus.FAILED) & (ReminderJob.retry_count < 3)))
                    )
                
                result = await session.execute(stmt)
                jobs = result.scalars().all()

                for job in jobs:
                    try:
                        # Fetch channel
                        sess = job.session
                        if not sess or not sess.campaign:
                            logger.warning(f"Reminder job {job.id} validation failed: Missing session or campaign.")
                            job.status = ReminderStatus.FAILED
                            continue

                        channel_id = sess.channel_id
                        if not channel_id:
                            channel_id = sess.campaign.channel_id
                        
                        if not channel_id:
                             logger.warning(f"Reminder job {job.id}: No channel ID found.")
                             job.status = ReminderStatus.FAILED
                             continue

                        channel = self.bot.get_channel(channel_id)
                        if not channel:
                            try:
                                channel = await self.bot.fetch_channel(channel_id)
                            except:
                                logger.error(f"Could not fetch channel {channel_id} for reminder {job.id}")
                                job.status = ReminderStatus.FAILED
                                job.retry_count += 1
                                continue
                        
                        # Send reminder
                        await channel.send(content=job.message)
                        job.status = ReminderStatus.SENT
                        logger.info(f"Sent reminder {job.id} to channel {channel_id}")

                    except Exception as e:
                        logger.error(f"Error processing reminder {job.id}: {e}")
                        job.status = ReminderStatus.FAILED
                        job.retry_count += 1
                
                await session.commit()
                
        except Exception as e:
            logger.error(f"Error in reminder loop: {e}", exc_info=True)

    @check_reminders.before_loop
    async def before_check_reminders(self):
        await self.bot.wait_until_ready()

async def setup(bot: commands.Bot):
    await bot.add_cog(ReminderCog(bot))
