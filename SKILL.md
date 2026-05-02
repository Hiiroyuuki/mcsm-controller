---
name: mcsm-controller
description: Callable OpenClaw skill for controlling MCSManager instances, including status checks, lifecycle actions, terminal commands, output retrieval, instance lookup, and reinstall operations.
metadata:
  short-description: Control MCSManager instances
---

# MCSM Instance Skill

This skill gives OpenClaw a callable interface for controlling an MCSManager instance.

## Purpose

Use this skill when you need to:

- Check MCSManager instance status
- Start, stop, restart, or kill an instance
- Send terminal commands to an instance
- Fetch terminal output or normalized messages
- Query instance details or list instances under a daemon
- Trigger an update task
- Reinstall an instance from a package URL
- Run `chat_control.py` to listen for in-game chat that calls OpenClaw

## Files

- `mcsm_skill.py`: Skill entrypoint and action dispatcher
- `mcsm_control.py`: Low-level MCSManager API client
- `chat_control.py`: Background listener that watches Minecraft chat and forwards `openclaw` requests
- `config.json`: Local connection settings and skill policy
- `codes.md`: Often-used code snippets for MCSManager interactions

## Configuration

Before using this skill, make sure `config.json` is filled with valid values:

- `mcsm.base_url`
- `mcsm.apikey`
- `mcsm.daemon_id`
- `mcsm.instance_uuid`

Optional policy settings in `config.json`:

- `skill.allow_instance_override`
- `skill.allowed_actions`

Optional `chat_control` settings in `config.json`:

- `chat_control.trigger_word`
- `chat_control.poll_interval`
- `chat_control.output_size`
- `chat_control.openclaw_command`
- `chat_control.openclaw_timeout`
- `chat_control.response_mode`
- `chat_control.response_prefix`
- `chat_control.ack_message`
- `chat_control.error_message`
- `chat_control.max_reply_length`
- `chat_control.system_prompt`

## Supported Actions

The following actions are supported:

- `status`
- `start`
- `stop`
- `restart`
- `kill`
- `update_task`
- `send_command`
- `get_output`
- `get_messages`
- `list_instances`
- `get_instance`
- `reinstall`

## Input Contract

Pass a JSON object to `mcsm_skill.py`.

Required field:

- `action`

Optional common fields:

- `daemon_id`
- `instance_uuid`
- `base_url`
- `apikey`
- `timeout`

Action-specific fields:

- `send_command`: requires `command`
- `get_output`: optional `size`
- `get_messages`: optional `size`, `limit`, `since_id`
- `list_instances`: optional `page`, `page_size`, `instance_name`, `status`
- `reinstall`: requires `target_url` and `title`, optional `description`

`chat_control.py` is not called through the `action` field. It is a separate long-running listener script.

## How To Execute

Run the skill by sending JSON to `mcsm_skill.py`.

Example:

```bash
python mcsm_skill.py <<'EOF'
{
  "action": "status"
}
EOF
```

Example with command execution:

```bash
python mcsm_skill.py <<'EOF'
{
  "action": "send_command",
  "command": "say hello from OpenClaw"
}
EOF
```

Example for starting chat listener:

```bash
python chat_control.py
```

Example with explicit config path:

```bash
python chat_control.py --config ./config.json
```

## Expected Output

The script returns JSON.

Successful result:

```json
{
  "ok": true,
  "action": "status"
}
```

Failed result:

```json
{
  "ok": false,
  "action": "start",
  "error": "..."
}
```

## Chat Control

`chat_control.py` continuously polls the Minecraft server console output through MCSManager, looks for player chat messages, and checks whether the message calls `openclaw`.

Typical trigger examples:

- `openclaw help me set the weather to clear`
- `openclaw: teleport Steve to spawn`
- `@openclaw give me the correct gamerule command`

When triggered, `chat_control.py`:

1. extracts the player name and request text
2. sends the request to the configured `chat_control.openclaw_command`
3. sends the OpenClaw reply back to the player with `msg` or to all players with `say`

Required runtime expectation:

- `chat_control.openclaw_command` must be configured to a valid local OpenClaw command
- if the command contains `{prompt}`, the prompt is injected into that argument
- otherwise the prompt is sent to OpenClaw through stdin

## Chat Control Rules For OpenClaw

- If the user explicitly asks to enable chat listening, start `chat_control.py`.
- If the user explicitly asks to disable chat listening, stop the running `chat_control.py` listener process.
- Do not assume chat listening should always be on. Treat it as a user-controlled background feature.
- Before starting the listener, make sure `config.json` has valid `mcsm.*` and `chat_control.*` values.
- If the user asks what the listener does, explain that it watches in-game chat for the trigger word and forwards matching requests to OpenClaw.
- If the user asks to change the wake word, update `chat_control.trigger_word`.
- If the user asks to change reply style, update `chat_control.response_mode`, `chat_control.response_prefix`, and related reply fields.
- When a player calls `openclaw` and asks for an operation that targets a player, resolve the target from the in-game caller context first.
- If the request subject is the caller themself, such as "give me", "teleport me", "clear my inventory", or equivalent self-reference, use the calling player as the operation target.
- If the request does not specify which player should be targeted, use `mcsm_skill.py` action `send_command` to send the Minecraft `list` command, read the online player list from the server output, then ask the caller which player should be operated on.
- After asking for the missing player target, wait for the player's follow-up reply before choosing the final operation target or issuing the actual command.

## Usage Rules

- Prefer the default `daemon_id` and `instance_uuid` from `config.json` unless the task clearly requires another instance.
- Do not use actions outside `skill.allowed_actions`.
- Do not call `send_command` without a concrete command string.
- Do not call `reinstall` unless the user explicitly asks for reinstall behavior.
- If `allow_instance_override` is `false`, do not try to override `daemon_id` or `instance_uuid`.
- Do not start `chat_control.py` unless the user asks for chat-based OpenClaw listening or the task clearly requires it.
- If a `chat_control.py` listener is already running, avoid starting a duplicate listener.

## Recommended Invocation Strategy

1. Use `status` first when you need to understand current state.
2. Use `start`, `stop`, or `restart` only after identifying the target instance.
3. Use `send_command` for in-instance console commands.
4. Use `get_output` or `get_messages` after command execution when terminal feedback is needed.
5. Use `chat_control.py` only when the user wants OpenClaw to react to player chat continuously.
