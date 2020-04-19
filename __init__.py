import logging

import random_word
from opsdroid.matchers import match_event, match_regex
from opsdroid.skill import Skill


_LOGGER = logging.getLogger(__name__)


class JitsiSkill(Skill):
    """
    This skill can generate a Jitsi call URL and post it to the room.

    If the matrix connector is configured and the message comes in on the
    matrix connector, as well as generating the URL it will also post a v2
    Jitsi call widget for Riot support.

    By default the URL for the call will be the room name, this is only
    supported for slack and matrix, otherwise a random name will be used.

    There is also a "bridged" mode for use in a room which is listening on both
    slack and matrix. In this mode the skill only listens for commands from the
    matrix connector, and only sends messages to slack (to enable pinned
    messages), but also sends widgets to matrix.
    """

    def __init__(self, opsdroid, config):
        self.bridged_mode = config.get("bridged_mode", False)
        self.base_jitsi_url = config.get("base_jitsi_url", "https://meet.jit.si")
        self.conference_prefix = config.get("conference_prefix", "")
        self.prefix_room_name = config.get("prefix_room_name", False)
        self.use_room_name = config.get("use_room_name", True)
        self.matrix_connector = None
        self.slack_connector = None

    @match_event(OpsdroidStarted)
    def configure(self, started):
        """
        Inspect the configured connectors and work out what mode we are in.
        """
        self.matrix_connector = self.opsdroid._connector_names.get("matrix", None)
        self.slack_connector = self.opsdroid._connector_names.get("slack", None)

        if self.bridged_mode and (self.matrix_connector is None or self.slack_connector is None):
            raise ValueError("Jitsi skill is misconfigured. Bridged mode requires both a slack and matrix connector to be configured.")

    def process_message(self, message):
        """
        Logic to determine if we process a message.

        If bridged mode is true we only process messages from matrix.
        """
        if self.bridged_mode and message.connector is not self.matrix_connector:
            _LOGGER.debug(f"Skipping message from {message.connector} as we are in bridge mode and only listening to matrix messages.")
            return False
        else:
            return True

    def send_and_pin_message(self):
        """
        Logic to decide what connector we send the message on, and then to pin it.
        """

    @staticmethod
    def get_random_slug():
        r = random_word.RandomWords()
        return "".join(r.get_random_words(limit=3)).replace("-", "")

    async def get_call_name(self, message):
        """
        Based on config generate a name for this call.

        This can be based on the room name for a slack or matrix room, or just
        a random set of words.
        """
        slug = ""
        used_room_name = False

        if self.use_room_name and self.message.connector is self.matrix_connector:
            used_room_name = True
            room_id = self.matrix_connector.lookup_target(message.target)
            name = await self.matrix_api.get_room_name(room_id)

        if self.use_room_name and self.message.connector is self.slack_connector:
            response = await self.slack_connector.slack.channels_info(channel=message.target)
            slug = response.data['channel']['name']
            used_room_name = True

        slug = name.replace(" ", "").replace("-", "").replace("_", "")

        if not slug:
            slug = self.get_random_slug()

        if self.conference_prefix and ((used_room_name and self.prefix_room_name) or not used_room_name):
            slug = f"{self.conference_prefix}_{slug}"

        return slug

    @match_regex()
    async def start_jitsi_call(self, message):
        """
        Respond to a command to start a jitsi call.
        """
        if not self.process_message(message):
            return

        conference_id = await self.get_call_name(message)

    @match_regex()
    async def end_jitsi_call(self):
        """
        Unpin message and remove widget.
        """

    @match_event(UnknownMatrixEvent)
    async def handle_jitsi_widget(self):
        """
        Parse a new jitsi widget and send the details to the room.
        """
