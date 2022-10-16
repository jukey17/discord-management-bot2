from __future__ import annotations

import datetime
import enum
import logging
import os
from pathlib import Path
from typing import Optional, Union

import discord
import pydantic

from discord.ext import commands, tasks

import models
import utils

VoiceStateChannel = Optional[Union[discord.VoiceChannel, discord.StageChannel]]

logger = logging.getLogger(__name__)


class _Constant(utils.Constant):
    DIRECTORY_PATH = Path(os.environ["LOGGING_VOICE_STATES_PATH"])
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


class _UserAction(str, enum.Enum):
    UNKNOWN = ("unknown",)
    JOIN = ("join",)
    LEAVE = ("leave",)
    MOVE = ("move",)
    STAY = ("stay",)

    @classmethod
    def parse(cls, before: VoiceStateChannel, after: VoiceStateChannel) -> _UserAction:
        if before is None and after is not None:
            return _UserAction.JOIN
        if before is not None and after is None:
            return _UserAction.LEAVE
        if before is not None and after is not None:
            if before.id == after.id:
                return _UserAction.STAY
            else:
                return _UserAction.MOVE
        return _UserAction.UNKNOWN


class _FeatureState(str, enum.Enum):
    OFF = ("off",)
    TRIGGER = ("trigger",)
    ON = ("on",)
    RELEASE = ("release",)

    @classmethod
    def parse(cls, before: bool, after: bool) -> _FeatureState:
        if not before and after:
            return _FeatureState.TRIGGER
        if before and not after:
            return _FeatureState.RELEASE
        if before and after:
            return _FeatureState.ON
        return _FeatureState.OFF


class _VoiceStateLogRecord(pydantic.BaseModel):
    datetime: datetime.datetime
    user_id: int
    action: _UserAction
    mute: _FeatureState
    deaf: _FeatureState
    stream: _FeatureState
    video: _FeatureState
    afk: _FeatureState
    guild_id: int
    channel_id: int


class LoggingVoiceStatesCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self._bot = bot
        self._model = models.LoggingModel[_VoiceStateLogRecord](
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
    async def on_voice_state_update(
        self,
        member: discord.Member,
        before: discord.VoiceState,
        after: discord.VoiceState,
    ):
        logger.debug("begin")
        now_jst = datetime.datetime.now(_Constant.JST)
        record = _VoiceStateLogRecord(
            datetime=now_jst,
            user_id=member.id,
            action=_UserAction.parse(before.channel, after.channel),
            mute=_FeatureState.parse(before.self_mute, after.self_mute),
            deaf=_FeatureState.parse(before.self_deaf, after.self_deaf),
            stream=_FeatureState.parse(before.self_stream, after.self_stream),
            video=_FeatureState.parse(before.self_video, after.self_video),
            afk=_FeatureState.parse(before.afk, after.afk),
            guild_id=member.guild.id,
            channel_id=_get_channel_id(before.channel, after.channel),
        )

        file_path = self._model.append_record_to_json(
            record, now_jst, str(record.guild_id), str(record.channel_id)
        )
        logger.debug(f"file={file_path}, record={record}")

        logger.debug("end")


def _get_channel_id(before: VoiceStateChannel, after: VoiceStateChannel) -> int:
    if before is None and after is not None:
        return after.id
    if before is not None and after is None:
        return before.id
    if before is not None and after is not None:
        return after.id
    return -1


async def setup(bot: commands.Bot):
    await bot.add_cog(LoggingVoiceStatesCog(bot))
