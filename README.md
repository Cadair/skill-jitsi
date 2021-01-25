# skill-jitsi

An opsdroid skill for quickly sharing Jitsi call URLs.

This skill currently requires the master branch of opsdroid for reacting to a new Jitsi widget on matrix.

This skill provides the following commands:

`!jitsi` which optionally takes one argument, which is either the URL to a jitsi call or the name of the conference for the configured domain. It will then post a URL for the conference to the channel, and if the matrix connector is configured add a Jitsi widget to the room. If no arguments are given the room name will be used for the conference id.

`!endjitsi` which removes a jitsi widget from a matrix room.

`!setjitsiurl` Set a custom jitsi url for this room.

`!unsetjitsiurl` Unset a custom jitsi url for this room.

Also if a Jitsi widget is added to a matrix room the plain URL for that conference will be posted to the channel. (i.e. not through the riot wrapper).

The main objective of this skill is to facilitate the use of jitsi calls across bridges, but might also be useful if you want to add custom call URLs.


## Quickstart

To use this bot first [install opsdroid](https://docs.opsdroid.dev/en/stable/installation.html) then write a `configuration.yaml` file with the following content, adjusting as needed.

```
## Parsers
parsers:
  regex:
    enabled: true

connectors:
  matrix:
    mxid: "@account:server.com"
    password: "mypassword"
    homeserver: "https://matrix.org"
    rooms:
      "main": "#room:server.com"
    nick: Jitsi Bot

database:
  matrix:
    single_state_key: false

skills:
  jitsi:
    repo: https://github.com/Cadair/skill-jitsi.git
```

then run `opsdroid start` in the same directory as the `configuration.yaml` file.

You should also be able to use the message features of this bot with any connector, not just matrix.


## Configuration

The minimal config to use this skill is:

```
skills:
  jitsi:
    repo: https://github.com/Cadair/skill-jitsi.git
```

The available options are (shown with defaults):
```
skills:
  jitsi:
    repo: https://github.com/Cadair/skill-jitsi.git

    # The jitsi instance to use for the `!jitsi` command.
    base_jitsi_domain: "meet.jit.si"
    # A prefix to add to the conference ID
    conference_prefix: ""
    # If the prefix should be added to the url if the room name is used
    prefix_room_name: false
    # If the room name should be used to generate the call URL
    use_room_name: true
    # Only respond to commands on the matrix connector.
    # (Useful if you are bridging and your opsdroid is connected to both sides of the bridge)
    listen_matrix_only: false
    # Join rooms when invited
    join_when_invited: false
    # Alternatively the following only accepts invites from the listed homeservers
    join_when_invited:
      - matrix.org
```
