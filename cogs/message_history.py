import contextlib
import csv
import datetime
import io
import logging
import traceback
from typing import Dict, List

import discord
from discord import app_commands
from discord.ext import commands

import utils

logger = logging.getLogger(__name__)


class _MessageCounter:
    def __init__(self, member: discord.Member, channel: discord.TextChannel):
        self._member = member
        self._channel = channel
        self._count = 0

    def __str__(self):
        return f"member=[{self._member}], channel=[{self._channel}], count={self._count}"

    def increment(self, value: int = 1):
        self._count += value

    @property
    def member(self) -> discord.Member:
        return self._member

    @property
    def channel(self) -> discord.TextChannel:
        return self._channel

    @property
    def count(self) -> int:
        return self._count


class _MessageCountResult:
    def __init__(self, member: discord.Member):
        self._member = member
        self._result_map: dict[discord.TextChannel, int] = {}

    def __str__(self):
        return f"{self.to_dict()}"

    def add_result(self, channel: discord.TextChannel, count: int):
        self._result_map[channel] = count

    def get_count(self, channel: discord.TextChannel) -> int:
        return self._result_map[channel]

    def to_dict(self):
        output = {"user": self._member.display_name}
        for channel, count in self._result_map.items():
            output[channel.name] = count
        return output


class MessageHistoryGroup(
    app_commands.Group, name="message_history", description="メッセージの履歴に関するコマンド"
):
    pass


class MessageHistoryCog(commands.Cog):
    group = MessageHistoryGroup()

    def __init__(self, bot: commands.Bot):
        self._bot = bot

    @group.command(name="count", description="メッセージの発言回数を取得します")
    @app_commands.describe(
        channel="発言回数を取得したいチャンネルを指定します。",
        channel2="複数のチャンネルを利用する場合に指定します。",
        channel3="複数のチャンネルを利用する場合に指定します。",
        channel4="複数のチャンネルを利用する場合に指定します。",
        before="対象となる期間(after ~ before)を YYYY/MM/DD のフォーマットで指定します。指定しない場合は現在日時が利用されます。",
        after="対象となる期間を(after ~ before) YYYY/MM/DD のフォーマットで指定します。指定しない場合はサーバー開始日時が利用されます。",
    )
    async def count(
            self,
            interaction: discord.Interaction,
            channel: discord.TextChannel,
            channel2: discord.TextChannel = None,
            channel3: discord.TextChannel = None,
            channel4: discord.TextChannel = None,
            before: str = None,
            after: str = None,
    ):
        await interaction.response.defer()

        channels = [channel]
        if channel2 is not None:
            channels.append(channel2)
        if channel3 is not None:
            channels.append(channel3)
        if channel4 is not None:
            channels.append(channel4)

        fmts = ["%Y/%m/%d", "%Y-%m-%d"]
        if before is None:
            before_jst = datetime.datetime.now(utils.Constant.JST)
        else:
            before_jst = utils.Constant.JST.localize(utils.try_strptime(before, *fmts))
        before_utc = before_jst.astimezone(utils.Constant.UTC)

        if after is None:
            after_jst = interaction.guild.created_at.astimezone(utils.Constant.JST)
        else:
            after_jst = utils.Constant.JST.localize(utils.try_strptime(after, *fmts))
        after_utc = after_jst.astimezone(utils.Constant.UTC)

        result_map = {}
        for c in channels:
            logger.debug(f"fetch history, channel={c}")
            message_counters = await self._count_messages(
                interaction.guild, c, before_utc, after_utc
            )
            result_map[c] = message_counters

        results = self._convert_to_message_count_result(result_map)
        sorted_results = sorted(results, key=lambda r: r.get_count(channel), reverse=True)

        filename = f"message_history_count_{after_jst.date()}_{before_jst.date()}.csv".replace("-", "").replace("/", "")
        logger.debug(f"create {filename} buffer")
        with contextlib.closing(io.StringIO()) as buffer:
            fieldnames = ["user"]
            fieldnames.extend([key.name for key in result_map.keys()])

            writer = csv.DictWriter(buffer, fieldnames)
            writer.writeheader()

            for result in sorted_results:
                writer.writerow(result.to_dict())
            buffer.seek(0)

            logger.debug(f"send {filename}")

            title = "/message_history count"
            description = f"集計期間: {after_jst.date()} ~ {before_jst.date()}"
            embed = discord.Embed(title=title, description=description)
            channels_str = ", ".join([c.mention for c in channels])
            embed.add_field(name="対象チャンネル", value=channels_str)
            await interaction.followup.send(
                embed=embed, file=discord.File(buffer, filename)
            )

    async def cog_app_command_error(
        self, interaction: discord.Interaction, error: app_commands.AppCommandError
    ):
        orig_error = getattr(error, "original", error)
        error_msg = "".join(
            traceback.TracebackException.from_exception(orig_error).format()
        )
        logger.error(error_msg)
        await interaction.followup.send("コマンド実行中にエラーが発生しました。")

    @staticmethod
    async def _count_messages(
            guild: discord.Guild,
            channel: discord.TextChannel,
            before: datetime.datetime,
            after: datetime.datetime,
    ):
        message_counters: dict[int, _MessageCounter] = {
            member.id: _MessageCounter(member, channel)
            for member in guild.members
            if not member.bot
        }

        async for message in channel.history(limit=None, before=before, after=after):
            if message.author.bot:
                continue
            if message.author.id not in message_counters:
                continue
            message_counters[message.author.id].increment()

        return list(message_counters.values())

    @staticmethod
    def _convert_to_message_count_result(
            counter_map: Dict[discord.TextChannel, List[_MessageCounter]]
    ) -> list[_MessageCountResult]:
        results = {}
        for channel, message_counters in counter_map.items():
            for counter in message_counters:
                if counter.member.id not in results:
                    results[counter.member.id] = _MessageCountResult(counter.member)
                results[counter.member.id].add_result(channel, counter.count)

        return list(results.values())


async def setup(bot: commands.Bot):
    await bot.add_cog(MessageHistoryCog(bot))
