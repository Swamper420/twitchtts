import asyncio
import re
import logging
from typing import Optional
import websockets
from app.config import settings
from app.queue.manager import TTSQueueManager

logger = logging.getLogger("twitchtts.twitch")


class TwitchChatListener:
    """
    Twitch IRC Chat Listener.
    Listens to live Twitch chat messages and automatically queues them for multi-voice TTS readback!
    """

    TWITCH_WS_URI = "wss://irc-ws.chat.twitch.tv:443"
    PRIVMSG_REGEX = re.compile(
        r"^:(?P<user>[^!]+)![^@]+@[^\s]+\s+PRIVMSG\s+#(?P<channel>[^\s]+)\s+:(?P<message>.*)$"
    )

    def __init__(self, queue_manager: TTSQueueManager):
        self.queue_manager = queue_manager
        self.running = False
        self.connected = False
        self.channel = settings.TWITCH_CHANNEL
        self.nick = settings.TWITCH_BOT_NICK
        self.oauth = settings.TWITCH_OAUTH_TOKEN
        self._task: Optional[asyncio.Task] = None

    def start(self):
        """Start Twitch chat listener background task."""
        if not self.running:
            self.running = True
            self._task = asyncio.create_task(self._listen_loop())
            logger.info("Twitch Chat Listener task initiated.")

    def stop(self):
        """Stop Twitch chat listener."""
        self.running = False
        if self._task:
            self._task.cancel()

    async def _listen_loop(self):
        """Continuous reconnection loop for Twitch IRC WebSocket."""
        while self.running:
            try:
                channel_to_join = settings.TWITCH_CHANNEL.lower().strip()
                if not channel_to_join:
                    logger.info("No TWITCH_CHANNEL set. Listener running in idle mode.")
                    await asyncio.sleep(5)
                    continue

                logger.info(f"Connecting to Twitch chat for channel: #{channel_to_join}...")
                async with websockets.connect(self.TWITCH_WS_URI) as ws:
                    self.connected = True
                    # Authenticate (anonymous or with OAuth token)
                    auth_pass = (
                        self.oauth
                        if self.oauth.startswith("oauth:")
                        else f"oauth:{self.oauth}"
                        if self.oauth
                        else "SCHMOOPIIE"
                    )
                    await ws.send(f"PASS {auth_pass}\r\n")
                    await ws.send(f"NICK {self.nick}\r\n")
                    await ws.send(f"JOIN #{channel_to_join}\r\n")

                    logger.info(f"Successfully joined Twitch channel: #{channel_to_join}")

                    while self.running:
                        raw_data = await ws.recv()
                        lines = raw_data.split("\r\n")

                        for line in lines:
                            if not line:
                                continue

                            # Handle PING/PONG keepalive
                            if line.startswith("PING"):
                                await ws.send(f"PONG {line.split()[1]}\r\n")
                                continue

                            # Parse PRIVMSG chat messages
                            match = self.PRIVMSG_REGEX.match(line)
                            if match:
                                user = match.group("user")
                                message = match.group("message").strip()

                                # Ignore system/bot messages if prefixed with ! (unless configured)
                                if message.startswith("!") and not settings.TWITCH_READ_ALL_CHAT:
                                    continue

                                logger.info(f"[Twitch Chat] {user}: {message}")
                                await self.queue_manager.add_message(
                                    user=user,
                                    raw_text=message,
                                    source="twitch",
                                )
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.connected = False
                logger.error(f"Twitch Chat connection error: {e}. Reconnecting in 5s...")
                await asyncio.sleep(5)

        self.connected = False
