import datetime
import logging
import os
from pathlib import Path
from typing import Union

import discord
import pydantic
import pytz

from discord.ext import commands, tasks

import models
import utils

MemberUser = Union[discord.Member, discord.User]

logger = logging.getLogger(__name__)


class _Constant(utils.Constant):
    DIRECTORY_PATH = Path(os.environ["LOGGING_MESSAGES_PATH"])
    MANAGE_LOGS_LIFETIME_INTERVAL = (
        utils.Constant.JST.localize(
            datetime.datetime.strptime(
                os.environ["MANAGE_LOGS_INTERVAL"], "%H:%M"
            ).replace(year=2000)  # pytzの仕様で1887年移行を指定しないと+09:19になってしまうための対策
        )
        .astimezone(tz=utils.Constant.UTC)
        .time()
    )
    LOGS_LIFETIME = datetime.timedelta(days=float(os.environ["LOGS_LIFETIME"]))


class _MessageLogRecord(pydantic.BaseModel):
    datetime: datetime.datetime
    message_id: int
    user_id: int
    channel_id: int
    guild_id: int


class LoggingMessages(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self._bot = bot
        self._model = models.LoggingModel[_MessageLogRecord](
            _Constant.DIRECTORY_PATH, _Constant.LOGS_LIFETIME
        )

    def cog_load(self):
        self.manage_logs_lifetime.start()

    def cog_unload(self) -> None:
        self.manage_logs_lifetime.cancel()

    @tasks.loop(time=_Constant.MANAGE_LOGS_LIFETIME_INTERVAL)
    async def manage_logs_lifetime(self):
        logger.debug("begin")
        now_jst = datetime.datetime.now(_Constant.JST)
        remove_list = self._model.delete_json_if_needed(now_jst.date())
        for remove_path in remove_list:
            logger.debug(f"remove {remove_path}")
        logger.debug("end")

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            logger.debug(
                f"bot is not logging. message={message.id}, author={message.author.id}"
            )
            return
        logger.debug("begin")

        now_jst = datetime.datetime.now(pytz.timezone("Asia/Tokyo"))
        record = _MessageLogRecord(
            datetime=now_jst,
            message_id=message.id,
            user_id=message.author.id,
            channel_id=message.channel.id,
            guild_id=message.guild.id,
        )
        file_path = self._model.append_record_to_json(
            record, now_jst, str(record.guild_id), str(record.channel_id)
        )
        logger.debug(f"file={file_path}, record={record}")

        logger.debug("end")


async def setup(bot: commands.Bot):
    await bot.add_cog(LoggingMessages(bot))
