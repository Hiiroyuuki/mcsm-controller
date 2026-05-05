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

Before using this skill, make sure `config.json` is filled with valid values.

`mcsm` is a map of named connection profiles. Each profile points to one MCSManager target instance:

```json
{
  "mcsm": {
    "instance_name1": {
      "base_url": "http://127.0.0.1:23333",
      "apikey": "replace_with_your_apikey",
      "daemon_id": "replace_with_your_daemon_id",
      "instance_uuid": "replace_with_your_instance_uuid",
      "timeout": 10,
      "chat_control_enabled": false
    },
    "instance_name2": {
      "base_url": "http://127.0.0.1:23333",
      "apikey": "replace_with_your_apikey",
      "daemon_id": "replace_with_your_daemon_id",
      "instance_uuid": "replace_with_your_instance_uuid",
      "timeout": 10,
      "chat_control_enabled": false
    }
  },
  "skill": {
    "default_instance": "instance_name1",
    "allow_instance_override": true,
    "allowed_actions": []
  }
}
```

Required fields for each `mcsm.<profile_name>` entry:

- `base_url`
- `apikey`
- `daemon_id`
- `instance_uuid`

Optional field for each `mcsm.<profile_name>` entry:

- `timeout`
- `chat_control_enabled`

Optional policy settings in `config.json`:

- `skill.default_instance`
- `skill.allow_instance_override`
- `skill.allowed_actions`

Optional `chat_control` settings in `config.json`:

- `chat_control.config_instance`
- `chat_control.config_instances`
- `chat_control.listen_all_instances`
- `chat_control.trigger_word`
- `chat_control.poll_interval`
- `chat_control.output_size`
- `chat_control.openclaw_command`
- `chat_control.openclaw_session_args`
- `chat_control.openclaw_message_arg`
- `chat_control.openclaw_timeout`
- `chat_control.response_mode`
- `chat_control.response_prefix`
- `chat_control.ack_message`
- `chat_control.error_message`
- `chat_control.log_mode`
- `chat_control.log_file`
- `chat_control.debug_errors_to_chat`
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

- `config_instance`
- `daemon_id`
- `instance_uuid`
- `base_url`
- `apikey`
- `timeout`

`config_instance` selects one named profile under `mcsm`. If it is omitted, the skill uses `skill.default_instance`. If `skill.default_instance` is omitted too, the first configured `mcsm` profile is used.

`daemon_id` and `instance_uuid` override the target instance inside the selected profile when `skill.allow_instance_override` is `true`. `base_url`, `apikey`, and `timeout` override only the connection settings for the current invocation.

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

Example with a named config instance:

```bash
python mcsm_skill.py <<'EOF'
{
  "action": "status",
  "config_instance": "instance_name2"
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

Example for starting chat listener with a named config instance:

```bash
python chat_control.py --config-instance instance_name2
```

Example for starting chat listener with multiple named config instances:

```bash
python chat_control.py --config-instance instance_name1 --config-instance instance_name2
```

Example for starting chat listener on every configured instance:

```bash
python chat_control.py --all-instances
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
  "action": "status",
  "config_instance": "instance_name1"
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

By default, the listener uses `chat_control.config_instances`, then `chat_control.config_instance`, then `skill.default_instance`, and finally the first configured `mcsm` profile. To monitor more than one server, set `chat_control.config_instances` to a list of profile names, pass `--config-instance` more than once, or use `--all-instances` / `chat_control.listen_all_instances`.

Typical trigger examples:

- `openclaw help me set the weather to clear`
- `openclaw: teleport Steve to spawn`
- `@openclaw give me the correct gamerule command`

When triggered, `chat_control.py`:

1. extracts the player name and request text
2. includes the source `config_instance` in the OpenClaw prompt
3. sends the request to OpenClaw through the configured message argument
4. sends the OpenClaw reply back to the player on the same source instance with `msg` or to all players with `say`

Required runtime expectation:

- `chat_control.openclaw_command` should normally be `["openclaw", "agent", "--local"]`
- `chat_control.openclaw_session_args` can hold session selectors such as `["--agent", "<name>"]`, `["--session-id", "<id>"]`, or `["--to", "<E.164>"]`
- `chat_control.py` runs `openclaw_command + openclaw_session_args + [openclaw_message_arg, prompt]` for each player request
- `chat_control.log_mode` can be `none`, `console`, `file`, or `both`
- `chat_control.log_file` is used when `log_mode` is `file` or `both`
- `chat_control.debug_errors_to_chat` appends the real exception message to the in-game error reply for debugging

## Chat Control Lifecycle

Each configured `mcsm.<profile_name>` can opt in to automatic chat listener management:

```json
{
  "mcsm": {
    "survival": {
      "base_url": "http://127.0.0.1:23333",
      "apikey": "...",
      "daemon_id": "...",
      "instance_uuid": "...",
      "chat_control_enabled": true
    }
  }
}
```

When `chat_control_enabled` is `true`, successful `start` calls launch `chat_control.py --config-instance <profile_name>`, and successful `stop` / `kill` calls stop that listener. `restart` ensures the listener matches the configured enabled state. Runtime `daemon_id` / `instance_uuid` overrides do not auto-manage chat control because they are not backed by a named config profile.

## Chat Control Rules For OpenClaw

- If the user explicitly asks to enable chat listening, start `chat_control.py`.
- If the user explicitly asks to disable chat listening, stop the running `chat_control.py` listener process.
- Do not assume chat listening should always be on. Treat it as a user-controlled background feature.
- If the user wants chat listening to follow server lifecycle actions, set `mcsm.<profile_name>.chat_control_enabled` for that named profile.
- Before starting the listener, make sure `config.json` has a valid selected `mcsm.<profile_name>` entry and valid `chat_control.*` values.
- If the user asks what the listener does, explain that it watches in-game chat for the trigger word and forwards matching requests to OpenClaw.
- If the user asks to change the wake word, update `chat_control.trigger_word`.
- If the user asks to change reply style, update `chat_control.response_mode`, `chat_control.response_prefix`, and related reply fields.
- When a player calls `openclaw` and asks for an operation that targets a player, resolve the target from the in-game caller context first.
- If the request subject is the caller themself, such as "give me", "teleport me", "clear my inventory", or equivalent self-reference, use the calling player as the operation target.
- If the request does not specify which player should be targeted, use `mcsm_skill.py` action `send_command` to send the Minecraft `list` command, read the online player list from the server output, then ask the caller which player should be operated on.
- After asking for the missing player target, wait for the player's follow-up reply before choosing the final operation target or issuing the actual command.

## Usage Rules

- If the user asks about onboard, onboarding, initialization, first-time setup, or setting up this skill, read `onboard.md` first and help the user complete the onboard steps described there.
- Prefer `skill.default_instance` from `config.json` unless the task clearly requires another configured profile.
- Use `config_instance` when the request should target a different named `mcsm` profile.
- Do not use actions outside `skill.allowed_actions`.
- Do not call `send_command` without a concrete command string.
- Do not call `reinstall` unless the user explicitly asks for reinstall behavior.
- If `allow_instance_override` is `false`, do not try to override `daemon_id` or `instance_uuid` inside the selected profile.
- Do not start `chat_control.py` manually unless the user asks for chat-based OpenClaw listening or the selected profile has `chat_control_enabled=true` and a lifecycle action started it.
- If a `chat_control.py` listener is already running, avoid starting a duplicate listener.

## Recommended Invocation Strategy

1. Use `status` first when you need to understand current state.
2. Use `start`, `stop`, or `restart` only after identifying the target instance.
3. Use `send_command` for in-instance console commands.
4. Use `get_output` or `get_messages` after command execution when terminal feedback is needed.
5. Use `chat_control.py` only when the user wants OpenClaw to react to player chat continuously.
