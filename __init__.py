import logging
import re
from urllib.parse import urlparse

import random_word
from opsdroid.database.matrix import memory_in_event_room, DatabaseMatrix
from opsdroid.connector.matrix.connector import (ConnectorMatrix,
                                                 MatrixException)
from opsdroid.connector.matrix.events import MatrixStateEvent
from opsdroid.connector.slack import ConnectorSlack
from opsdroid.events import (JoinRoom, Message, PinMessage, UnpinMessage,
                             UserInvite)
from opsdroid.matchers import match_event, match_regex, match_parse
from opsdroid.skill import Skill

_LOGGER = logging.getLogger(__name__)

"""
post-pyastro TODO:

* Use room state to get the default jitsi URL
* Use previous state to ensure the right conf gets removed (support multiple widgets)
* Allow non-matrix mode
"""


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
        super().__init__(opsdroid, config)
        self.base_jitsi_domain = config.get("base_jitsi_domain", "meet.jit.si")
        self.conference_prefix = config.get("conference_prefix", "")
        self.prefix_room_name = config.get("prefix_room_name", False)
        self.use_room_name = config.get("use_room_name", True)
        self.matrix_only = config.get("listen_matrix_only", False)
        self.join_when_invited = config.get("join_when_invited", False)

    @staticmethod
    async def send_and_pin_message(message, message_content):
        """
        Logic to decide what connector we send the message on, and then to pin it.
        """
        message_id = await message.respond(Message(message_content))
        message_id = message_id.event_id
        try:
            await message.respond(PinMessage(linked_event=message_id))
        except Exception:
            _LOGGER.exception("Failed to pin the message.")

    @staticmethod
    def get_random_slug():
        r = random_word.RandomWords()
        return "".join(r.get_random_words(limit=3)).replace("-", "")

    def process_message(self, message):
        if self.matrix_only and not isinstance(message.connector, ConnectorMatrix):
            return False
        return True

    async def get_call_name(self, message):
        """
        Based on config generate a name for this call.

        This can be based on the room name for a slack or matrix room, or just
        a random set of words.
        """
        slug = ""
        used_room_name = False

        try:
            if self.use_room_name and isinstance(message.connector, ConnectorMatrix):
                used_room_name = True
                room_id = message.connector.lookup_target(message.target)
                slug = await message.connector.connection.room_get_state_event(room_id, "m.room.name")
                slug = slug.content
                slug = slug.get("name", "")

            if self.use_room_name and isinstance(message.connector, ConnectorSlack):
                response = await message.connector.slack.channels_info(
                    channel=message.target
                )
                slug = response.data["channel"]["name"]
                used_room_name = True
        except Exception:
            _LOGGER.info("Could not room name for conference.")

        slug = slug.replace(" ", "_")
        slug = re.sub("[^a-zA-Z0-9_-]", "", slug)

        if not slug:
            slug = self.get_random_slug()

        if self.conference_prefix and (
            (used_room_name and self.prefix_room_name) or not used_room_name
        ):
            slug = f"{self.conference_prefix}_{slug}"

        return slug

    async def send_message_about_conference(self, message, conference_id, domain):
        message_content = f"This room's Jitsi URL is: https://{domain}/{conference_id}"

        return await self.send_and_pin_message(message, message_content)

    @match_regex("!unsetjitsiurl")
    @memory_in_event_room
    async def unset_jitsi_url(self, message):
        """
        Store the desired URL in memory.
        """
        if not self.process_message(message):
            return

        await self.opsdroid.memory.delete("jitsi_url")

    @match_parse(r"!setjitsiurl {jitsiurl}")
    @memory_in_event_room
    async def set_jitsi_url(self, message):
        """
        Store the desired URL in memory.
        """
        if not self.process_message(message):
            return

        if isinstance(message.connector, ConnectorMatrix):
            jitsi_url = message.entities["jitsiurl"]["value"]
            await message.respond(Message(f"Storing {jitsi_url} for this room."))
            await self.opsdroid.memory.put("jitsi_url", jitsi_url)

    @match_regex(r"!jitsi( (?P<callid>[^\s]+))?")
    @memory_in_event_room
    async def start_jitsi_call(self, message):
        """
        Respond to a command to start a jitsi call.
        """
        if not self.process_message(message):
            return

        domain = self.base_jitsi_domain
        callid = message.regex["callid"]
        conference_id = None

        if isinstance(message.connector, ConnectorMatrix):
            jitsi_url = await self.opsdroid.memory.get("jitsi_url")
            _LOGGER.debug(jitsi_url)
            if jitsi_url is not None:
                parsed_url = urlparse(jitsi_url)
                domain = parsed_url.netloc
                conference_id = parsed_url.path

            widget = await self.get_active_jitsi_widget(
                message.target, message.connector
            )
            if widget:
                data = widget["content"]["data"]
                await self.send_message_about_conference(
                    message, data["conferenceId"], data["domain"]
                )
                return

        if callid:
            # Strip out the stupid slack link syntax the bridge leaves in.
            if callid.startswith("<"):
                callid = callid[1:-1].split("|")[0]

            conference_id = callid
            call_url = urlparse(callid)
            if call_url.scheme:
                domain = call_url.netloc
                conference_id = call_url.path.replace("/", "")
            elif self.conference_prefix:
                conference_id = f"{self.conference_prefix}_{callid}"
        elif conference_id is None:
            conference_id = await self.get_call_name(message)

        await self.send_message_about_conference(message, conference_id, domain)

        if isinstance(message.connector, ConnectorMatrix):
            state_event = await self.create_jitsi_widget(conference_id, domain)
            try:
                await message.respond(state_event)
            except MatrixException as e:
                if "M_FORBIDDEN" in e.nio_error.status_code:
                    await message.respond(
                        Message(
                            "I am sorry, I don't have permission to add widgets to this room."
                        )
                    )
                    return
                _LOGGER.exception("Failed to add Jitsi widget to room {message.target}")

    @match_regex(r"!endjitsi")
    async def end_jitsi_call(self, message):
        """
        Unpin message and remove widget.
        """
        if not self.process_message(message):
            return
        if not isinstance(message.connector, ConnectorMatrix):
            await message.respond("Can only remove jitsi calls when using matrix.")
            return

        active_call = await self.get_active_jitsi_widget(
            message.target, message.connector
        )

        if active_call:
            state_key = active_call["state_key"]

            try:
                await message.respond(
                    MatrixStateEvent(
                        "im.vector.modular.widgets", content={}, state_key=state_key
                    )
                )
            except MatrixException as e:
                if "M_FORBIDDEN" in e.nio_error.status_code:
                    await message.respond(
                        Message(
                            "I am sorry, I don't have permission to remove widgets from this room."
                        )
                    )
                    return
                _LOGGER.exception(
                    "Failed to remove Jitsi widget from room {message.target}"
                )

    @match_event(MatrixStateEvent)
    async def handle_jitsi_widget(self, event):
        """
        Parse a new jitsi widget and send the details to the room.
        """
        if (
            event.event_type != "im.vector.modular.widgets"
            or event.content.get("type") != "jitsi"
            or not event.state_key.startswith("jitsi")
        ):
            return

        data = event.content["data"]
        await self.send_message_about_conference(
            event, data["conferenceId"], data["domain"]
        )

    @match_event(MatrixStateEvent)
    async def handle_remove_jitsi_widget(self, event):
        """
        Parse a new jitsi widget and send the details to the room.
        """
        if (
            event.event_type != "im.vector.modular.widgets"
            or not event.state_key.startswith("jitsi")
            or event.content
        ):
            return

        return await self.end_jitsi_call(event)

    @match_event(UserInvite)
    async def on_invite_to_room(self, invite):
        """
        Join all rooms on invite.
        """
        _LOGGER.info(f"Got room invite for {invite.target}.")
        if isinstance(self.join_when_invited, list):
            if invite.user_id.split(":")[1] not in self.join_when_invited:
                _LOGGER.debug(f"Not joining room as user not in domain allow list.")
                return
        _LOGGER.debug(f"Joining room from invite.")
        await invite.respond(JoinRoom())

    async def create_jitsi_widget(self, conference_id, domain=None):
        domain = domain or self.base_jitsi_domain
        content = {
            "type": "jitsi",
            "name": "Jitsi",
            "data": {
                "conferenceId": conference_id,
                "isAudioOnly": False,
                "domain": domain,
            },
            "url": f"https://app.element.io/jitsi.html?confId={conference_id}#conferenceDomain=$domain&conferenceId=$conferenceId&isAudioOnly=$isAudioOnly&displayName=$matrix_display_name&avatarUrl=$matrix_avatar_url&userId=$matrix_user_id",
        }

        return MatrixStateEvent(
            "im.vector.modular.widgets",
            content=content,
            state_key=f"jitsi_{conference_id}",
        )

    @staticmethod
    async def get_active_jitsi_widget(room_id, connector):
        all_state = await connector.connection.room_get_state(room_id)
        jitsi_widgets = list(
            filter(
                lambda x: x["type"] == "im.vector.modular.widgets"
                and x["content"]
                and x["content"].get("type", "") == "jitsi",
                all_state.events,
            )
        )

        if not jitsi_widgets:
            return

        if len(jitsi_widgets) > 1:
            raise Exception("Oh god I don't know what to do now.")

        return jitsi_widgets[0]
