# skill-jitsi

An opsdroid skill for quickly sharing Jitsi call URLs.

This skill currently requires the master branch of opsdroid for reacting to a new Jitsi widget on matrix.

This skill provides two commands:

`!jitsi` which optionally takes one argument, which is either the URL to a jitsi call or the name of the conference for the configured domain. It will then post a URL for the conference to the channel, and if the matrix connector is configured add a Jitsi widget to the room. If no arguments are given the room name will be used for the conference id.

`!endjitsi` which removes a jitsi widget from a matrix room.

Also if a Jitsi widget is added to a matrix room the plain URL for that conference will be posted to the channel. (i.e. not through the riot wrapper).

The main objective of this skill is to facilitate the use of jitsi calls across bridges, but might also be useful if you want to add custom call URLs.


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
```
