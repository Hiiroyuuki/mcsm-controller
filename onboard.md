# Onboard

This file is for OpenClaw when a user enables the `mcsm-controller` skill for the first time.

## Goal

Help the user edit `config.json` so OpenClaw can control the user's MCSManager Minecraft server instances safely.

## Required Config Changes

Ask the user for these values and update `config.json`:

- `mcsm.<profile_name>.base_url`: MCSManager panel URL, for example `http://127.0.0.1:23333`
- `mcsm.<profile_name>.apikey`: MCSManager user API key
- `mcsm.<profile_name>.daemon_id`: target MCSManager daemon ID
- `mcsm.<profile_name>.instance_uuid`: target Minecraft instance UUID
- `skill.default_instance`: the profile name OpenClaw should use by default

Common lookup locations:

- `apikey` is usually in the `mcsmanager/web/data/User` folder.
- `daemon_id` is usually in the `mcsmanager/web/data/RemoteServiceConfig` folder.
- `instance_uuid` is usually in `mcsmanager/daemon/data/InstanceData`; in most cases it is the instance folder name.

Rename example profiles such as `instance_name1` and `instance_name2` to meaningful names, such as `survival`, `creative`, or `modded`.

Remove any unused example profile, or make sure every remaining profile has valid non-placeholder values.

## Optional Config Changes

Discuss these options with the user:

- `mcsm.<profile_name>.timeout`: HTTP timeout in seconds
- `mcsm.<profile_name>.chat_control_enabled`: whether chat control should auto-start when this instance is started through the skill
- `skill.allow_instance_override`: whether runtime `daemon_id` / `instance_uuid` overrides are allowed
- `skill.allowed_actions`: actions the skill may perform; leave empty to allow all supported actions

## Chat Control Setup

Only configure chat control if the user wants in-game chat to call OpenClaw.

Update these fields:

- `chat_control.config_instance`: the default profile for manually running `chat_control.py`
- `chat_control.trigger_word`: wake word, for example `@openclaw`
- `chat_control.openclaw_command`: normally `["openclaw", "agent", "--local"]`
- `chat_control.openclaw_session_args`: required if OpenClaw needs a session selector, for example `["--agent", "chatcontrol"]`
- `chat_control.openclaw_message_arg`: normally `-m`
- `chat_control.response_mode`: `msg`, `say`, or `none`
- `chat_control.log_mode`: `none`, `console`, `file`, or `both`
- `chat_control.log_file`: log file path when file logging is enabled
- `chat_control.debug_errors_to_chat`: set `true` only while debugging

If `openclaw_session_args` uses `--agent`, verify the agent exists with:

```bash
openclaw agents list
```

## Validation

After editing `config.json`, run:

```bash
python -m json.tool config.json
python -m py_compile mcsm_control.py mcsm_skill.py chat_control.py
```

Then test the selected default instance:

```bash
python mcsm_skill.py --action status
```

If chat control is enabled, start or restart `chat_control.py` only after the config is valid.

## Completion Message

After the onboard is complete, OpenClaw must start its next response with:

`Finished onboard`

Then briefly summarize the configured default instance and whether chat control is enabled.
