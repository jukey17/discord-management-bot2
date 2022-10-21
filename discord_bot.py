import logging
import traceback

import discord
from discord.ext import commands


class DiscordBot(commands.Bot):
    def __init__(self, extensions: list[str]):
        intents = discord.Intents.default()
        intents.members = True
        intents.messages = True
        intents.reactions = True
        intents.emojis = True
        intents.message_content = True
        intents.voice_states = True
        super().__init__(command_prefix="/", intents=intents)
        self._extensions = extensions
        self._logger = logging.getLogger(__name__)

    async def setup_hook(self) -> None:
        for cog in self._extensions:
            await self.load_extension(cog)
            self._logger.debug(f"load extension: {cog}")

    async def on_ready(self):
        for guild in self.guilds:
            guild_obj = discord.Object(guild.id)
            self.tree.copy_global_to(guild=guild_obj)
            app_commands = await self.tree.sync(guild=guild_obj)
            self._logger.debug(f"sync guild={guild}, app_commands={app_commands}")
        guilds = ",".join(
            [f"(name={guild.name},id={guild.id})" for guild in self.guilds]
        )
        self._logger.debug(f"bot={self.user}, guilds=[{guilds}]")

    async def on_command_error(self, context, exception):
        orig_error = getattr(exception, "original", exception)
        error_msg = "".join(
            traceback.TracebackException.from_exception(orig_error).format()
        )
        self._logger.error(error_msg)

