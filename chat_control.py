import argparse
import json
import logging
import re
import shlex
import subprocess
import time
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Deque, Dict, List, Optional, Sequence, Tuple

from mcsm_skill import MCSM, MCSMSkillError, build_controller, load_config


BASE_DIR = Path(__file__).resolve().parent
DEFAULT_CONFIG_PATH = BASE_DIR / "config.json"
DEFAULT_SYSTEM_PROMPT = (
    "You are OpenClaw, a Minecraft server assistant. "
    "The following content is a player request captured from in-game chat. "
    "Understand the request and handle it."
)
DEFAULT_OPENCLAW_COMMAND = ["openclaw", "agent", "--local"]
DEFAULT_OPENCLAW_MESSAGE_ARG = "-m"
REPLY_START_MARKER = "OPENCLAW_CHAT_REPLY_START"
REPLY_END_MARKER = "OPENCLAW_CHAT_REPLY_END"
ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")
LOGGER = logging.getLogger("chat_control")


@dataclass
class ChatControlConfig:
    trigger_word: str
    poll_interval: float
    output_size: int
    openclaw_command: List[str]
    openclaw_session_args: List[str]
    openclaw_message_arg: str
    openclaw_timeout: int
    response_mode: str
    response_prefix: str
    ack_message: str
    error_message: str
    debug_errors_to_chat: bool
    log_mode: str
    log_file: str
    max_reply_length: int
    system_prompt: str
    config_instances: List[str]


@dataclass
class ChatListenerState:
    config_instance: str
    controller: Any
    previous_lines: List[str]
    seen_lines: Deque[str]


def _skill_for_config(config: Dict) -> MCSM:
    skill = MCSM.__new__(MCSM)
    skill.config_path = None
    skill.payload = {}
    skill.config = config
    return skill


def _bool_config(value, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "on", "enable", "enabled"}:
            return True
        if normalized in {"0", "false", "no", "off", "disable", "disabled"}:
            return False
    return bool(value)


def _resolve_log_file(value: str) -> str:
    if not value:
        return ""

    path = Path(value)
    if not path.is_absolute():
        path = BASE_DIR / path
    return str(path)


def list_config_instance_names(config: Dict) -> List[str]:
    return _skill_for_config(config).list_config_instance_names()


def _normalize_instance_list(value, field_name: str) -> List[str]:
    if value is None:
        return []
    if isinstance(value, str):
        names = [value]
    elif isinstance(value, list) and all(isinstance(item, str) for item in value):
        names = value
    else:
        raise MCSMSkillError(f"{field_name} must be a string or a list of strings")

    normalized = []
    for name in names:
        stripped = name.strip()
        if stripped and stripped not in normalized:
            normalized.append(stripped)
    return normalized


def _normalize_string_args(value, field_name: str) -> List[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return shlex.split(value)
    if isinstance(value, list) and all(isinstance(item, str) for item in value):
        return list(value)
    raise MCSMSkillError(f"{field_name} must be a string or a list of strings")


def resolve_chat_config_instances(
    config: Dict,
    chat_config: Dict,
    cli_config_instances: Optional[Sequence[str]] = None,
    listen_all_instances: bool = False,
) -> List[str]:
    available_names = list_config_instance_names(config)
    if not available_names:
        raise MCSMSkillError("config.mcsm is empty")

    if listen_all_instances:
        selected_names = available_names
    elif cli_config_instances:
        selected_names = _normalize_instance_list(list(cli_config_instances), "--config-instance")
    elif chat_config.get("listen_all_instances"):
        selected_names = available_names
    else:
        selected_names = _normalize_instance_list(chat_config.get("config_instances"), "chat_control.config_instances")
        if not selected_names:
            selected_names = _normalize_instance_list(chat_config.get("config_instance"), "chat_control.config_instance")

    if not selected_names:
        default_name = config.get("skill", {}).get("default_instance") if isinstance(config.get("skill", {}), dict) else None
        selected_names = _normalize_instance_list(default_name, "skill.default_instance")

    if not selected_names:
        selected_names = [available_names[0]]

    unknown_names = [name for name in selected_names if name not in available_names]
    if unknown_names:
        raise MCSMSkillError(
            "Unknown chat_control config instance(s): "
            f"{', '.join(unknown_names)}. Available: {', '.join(available_names)}"
        )

    return selected_names


def load_chat_config(
    config_path: Optional[str] = None,
    config_instances: Optional[Sequence[str]] = None,
    listen_all_instances: bool = False,
) -> Tuple[Dict, ChatControlConfig]:
    config = load_config(config_path=config_path)
    chat_config = config.get("chat_control", {})
    if not isinstance(chat_config, dict):
        raise MCSMSkillError("config.chat_control must be a JSON object")

    raw_command = chat_config.get("openclaw_command")
    if isinstance(raw_command, str):
        openclaw_command = shlex.split(raw_command)
    elif isinstance(raw_command, list) and all(isinstance(item, str) for item in raw_command):
        openclaw_command = list(raw_command)
    else:
        openclaw_command = list(DEFAULT_OPENCLAW_COMMAND)

    log_mode = str(chat_config.get("log_mode", "console")).strip().lower() or "console"
    log_mode_aliases = {
        "off": "none",
        "false": "none",
        "stdout": "console",
        "print": "console",
        "debug": "both",
    }
    log_mode = log_mode_aliases.get(log_mode, log_mode)
    log_file = _resolve_log_file(str(chat_config.get("log_file", "chat_control.log")).strip())

    runtime = ChatControlConfig(
        trigger_word=str(chat_config.get("trigger_word", "openclaw")).strip() or "openclaw",
        poll_interval=float(chat_config.get("poll_interval", 2.0)),
        output_size=int(chat_config.get("output_size", 128)),
        openclaw_command=openclaw_command,
        openclaw_session_args=_normalize_string_args(
            chat_config.get("openclaw_session_args"),
            "chat_control.openclaw_session_args",
        ),
        openclaw_message_arg=str(chat_config.get("openclaw_message_arg", DEFAULT_OPENCLAW_MESSAGE_ARG)).strip()
        or DEFAULT_OPENCLAW_MESSAGE_ARG,
        openclaw_timeout=int(chat_config.get("openclaw_timeout", 120)),
        response_mode=str(chat_config.get("response_mode", "msg")).strip().lower(),
        response_prefix=str(chat_config.get("response_prefix", "OpenClaw")).strip() or "OpenClaw",
        ack_message=str(chat_config.get("ack_message", "Received. Processing your request.")).strip(),
        error_message=str(chat_config.get("error_message", "Request failed. Please try again later.")).strip(),
        debug_errors_to_chat=_bool_config(chat_config.get("debug_errors_to_chat"), default=False),
        log_mode=log_mode,
        log_file=log_file,
        max_reply_length=max(20, int(chat_config.get("max_reply_length", 180))),
        system_prompt=str(chat_config.get("system_prompt", DEFAULT_SYSTEM_PROMPT)).strip() or DEFAULT_SYSTEM_PROMPT,
        config_instances=resolve_chat_config_instances(
            config,
            chat_config,
            cli_config_instances=config_instances,
            listen_all_instances=listen_all_instances,
        ),
    )

    if runtime.poll_interval <= 0:
        raise MCSMSkillError("chat_control.poll_interval must be greater than 0")
    if runtime.output_size <= 0:
        raise MCSMSkillError("chat_control.output_size must be greater than 0")
    if runtime.openclaw_timeout <= 0:
        raise MCSMSkillError("chat_control.openclaw_timeout must be greater than 0")
    if runtime.response_mode not in {"none", "msg", "say"}:
        raise MCSMSkillError("chat_control.response_mode must be one of: none, msg, say")
    if runtime.log_mode not in {"none", "console", "file", "both"}:
        raise MCSMSkillError("chat_control.log_mode must be one of: none, console, file, both")
    if runtime.log_mode in {"file", "both"} and not runtime.log_file:
        raise MCSMSkillError("chat_control.log_file is required when log_mode is file or both")

    return config, runtime


def setup_logging(config: ChatControlConfig) -> None:
    LOGGER.handlers.clear()
    LOGGER.setLevel(logging.DEBUG)
    LOGGER.propagate = False

    if config.log_mode == "none":
        LOGGER.addHandler(logging.NullHandler())
        return

    class ConfigInstanceFilter(logging.Filter):
        def filter(self, record: logging.LogRecord) -> bool:
            if not hasattr(record, "config_instance"):
                record.config_instance = "-"
            return True

    formatter = logging.Formatter(
        fmt="%(asctime)s %(levelname)s [%(name)s:%(config_instance)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    context_filter = ConfigInstanceFilter()

    if config.log_mode in {"console", "both"}:
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_handler.addFilter(context_filter)
        console_handler.setFormatter(formatter)
        LOGGER.addHandler(console_handler)

    if config.log_mode in {"file", "both"}:
        log_path = Path(config.log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_path, encoding="utf-8")
        file_handler.setLevel(logging.DEBUG)
        file_handler.addFilter(context_filter)
        file_handler.setFormatter(formatter)
        LOGGER.addHandler(file_handler)


def build_error_reply(config: ChatControlConfig, exc: Exception) -> str:
    base_message = config.error_message or "Request failed. Please try again later."
    if not config.debug_errors_to_chat:
        return base_message

    details = str(exc).strip()
    if not details:
        return base_message
    return f"{base_message} Debug: {details}"


def normalize_output_lines(output: str) -> List[str]:
    return [line.strip() for line in str(output).splitlines() if line.strip()]


def diff_new_lines(previous: Sequence[str], current: Sequence[str]) -> List[str]:
    if not previous:
        return list(current)
    if not current:
        return []
    if previous == current:
        return []

    max_overlap = min(len(previous), len(current))
    for overlap in range(max_overlap, 0, -1):
        if list(previous[-overlap:]) == list(current[:overlap]):
            return list(current[overlap:])
    return list(current)


def extract_chat_message(line: str) -> Optional[Tuple[str, str]]:
    marker = "]:"
    content = line.split(marker, 1)[1].strip() if marker in line else line.strip()

    if content.startswith("[Not Secure]"):
        content = content[len("[Not Secure]"):].strip()

    if not content.startswith("<") or ">" not in content:
        return None

    player, message = content[1:].split(">", 1)
    player = player.strip()
    message = message.strip()
    if not player or not message:
        return None

    return player, message


def extract_openclaw_request(message: str, trigger_word: str) -> Optional[str]:
    normalized = message.strip()
    lowered = normalized.lower()
    trigger = trigger_word.lower().strip()

    for prefix in (
        trigger,
        f"@{trigger}",
        f"{trigger}:",
        f"{trigger}\uff1a",
        f"{trigger},",
        f"{trigger}\uff0c",
    ):
        if lowered.startswith(prefix):
            request_text = normalized[len(prefix):].strip(" \t,:\uff0c\uff1a-")
            return request_text or None

    index = lowered.find(trigger)
    if index == -1:
        return None

    request_text = normalized[index + len(trigger):].strip(" \t,:\uff0c\uff1a-")
    return request_text or None


def build_openclaw_prompt(
    player: str,
    request_text: str,
    raw_message: str,
    config: ChatControlConfig,
    config_instance: str,
) -> str:
    payload = {
        "system_prompt": config.system_prompt,
        "mcsm_context": {
            "config_instance": config_instance,
            "instruction": (
                "When using the mcsm-controller skill for this player request, "
                "include this config_instance unless the user explicitly targets another configured instance."
            ),
        },
        "player": player,
        "raw_message": raw_message,
        "request": request_text,
        "reply_format": (
            f"Only put the final Minecraft player-facing reply between {REPLY_START_MARKER} "
            f"and {REPLY_END_MARKER}. Do not put tool logs, plugin logs, memory logs, "
            "prompts, JSON payloads, or diagnostics in the marked reply."
        ),
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


def clean_agent_output(text: str) -> str:
    output = ANSI_ESCAPE_RE.sub("", text)

    lines = []
    for line in output.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        lines.append(stripped)

    return "\n".join(lines).strip()


def extract_marked_reply(text: str) -> Optional[str]:
    if REPLY_START_MARKER not in text:
        return None

    after_start = text.split(REPLY_START_MARKER, 1)[1]
    if REPLY_END_MARKER in after_start:
        after_start = after_start.split(REPLY_END_MARKER, 1)[0]

    cleaned = clean_agent_output(after_start)
    return cleaned or None


def looks_like_openclaw_log(line: str) -> bool:
    lowered = line.lower()
    if line.startswith("[plugins]") or line.startswith("Config warnings:"):
        return True
    if line.startswith("- plugins.") or line.startswith("[OpenClaw]"):
        return True
    if lowered.startswith(("recall query:", "system_prompt:", "provider=", "model=", "db=")):
        return True
    if "graph-memory" in lowered or "registertool" in lowered:
        return True
    if "requestsenderid=" in lowered or "agenthopcountlimit=" in lowered:
        return True
    return False


def looks_like_openclaw_error(text: str) -> bool:
    lowered = text.strip().lower()
    if not lowered:
        return False
    error_prefixes = (
        "error:",
        "runtimeerror:",
        "traceback ",
        "config warnings:",
        "openclaw command exited",
        "openclaw command timed out",
    )
    return lowered.startswith(error_prefixes)


def strip_openclaw_logs(text: str) -> str:
    marked_reply = extract_marked_reply(text)
    if marked_reply:
        return marked_reply

    cleaned = clean_agent_output(text)
    lines = [line for line in cleaned.splitlines() if line.strip()]
    filtered = [line for line in lines if not looks_like_openclaw_log(line.strip())]

    if filtered:
        return "\n".join(filtered).strip()
    return cleaned


class OpenClawAgentClient:
    def __init__(self, config: ChatControlConfig):
        self.config = config

    def submit(self, prompt: str) -> str:
        return self._submit_message(prompt)

    def _message_command(self, prompt: str) -> List[str]:
        command = list(self.config.openclaw_command)
        message_arg_names = {self.config.openclaw_message_arg, "-m", "--message"}

        if command and command[-1] in message_arg_names:
            return command + [prompt]
        return command + list(self.config.openclaw_session_args) + [self.config.openclaw_message_arg, prompt]

    def _submit_message(self, prompt: str) -> str:
        command = self._message_command(prompt)
        LOGGER.info("starting OpenClaw message command: %s <prompt>", " ".join(command[:-1]))

        try:
            completed = subprocess.run(
                command,
                cwd=str(BASE_DIR),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=self.config.openclaw_timeout,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            LOGGER.error("OpenClaw message command timed out after %s seconds", self.config.openclaw_timeout)
            raise RuntimeError(f"openclaw command timed out after {self.config.openclaw_timeout} seconds") from exc

        stdout = clean_agent_output(completed.stdout)
        stderr = clean_agent_output(completed.stderr)

        reply = strip_openclaw_logs(completed.stdout)
        if not reply:
            reply = strip_openclaw_logs(completed.stderr)

        if completed.returncode != 0:
            LOGGER.error(
                "OpenClaw message command exited non-zero. code=%s stdout=%r stderr=%r filtered_reply=%r",
                completed.returncode,
                stdout,
                stderr,
                reply,
            )
            if reply and not looks_like_openclaw_error(reply):
                LOGGER.warning(
                    "OpenClaw returned a usable reply despite non-zero exit code; sending reply to player"
                )
                return reply
            raise RuntimeError(stderr or stdout or f"openclaw command exited with code {completed.returncode}")

        if not reply:
            LOGGER.error("OpenClaw message command returned no output")
            raise RuntimeError("openclaw command did not return a response")

        if reply != stdout:
            LOGGER.debug("filtered OpenClaw stdout to final reply: %r", reply)

        return reply


def remember_line(cache: Deque[str], value: str) -> bool:
    if value in cache:
        return False
    cache.append(value)
    return True


def split_reply(text: str, max_length: int) -> List[str]:
    normalized = " ".join(text.split())
    if not normalized:
        return []

    chunks: List[str] = []
    while len(normalized) > max_length:
        split_at = normalized.rfind(" ", 0, max_length + 1)
        if split_at <= 0:
            split_at = max_length
        chunks.append(normalized[:split_at].strip())
        normalized = normalized[split_at:].strip()
    if normalized:
        chunks.append(normalized)
    return chunks


def send_reply(controller, player: str, text: str, config: ChatControlConfig) -> None:
    if config.response_mode == "none":
        return

    chunks = split_reply(text, config.max_reply_length)
    if not chunks:
        return

    for chunk in chunks:
        if config.response_mode == "say":
            command = f"say [{config.response_prefix}] {chunk}"
        else:
            command = f"msg {player} [{config.response_prefix}] {chunk}"

        result = controller.send_command(command)
        if not result.get("ok"):
            raise RuntimeError(result.get("error", "failed to send response"))


def process_chat_line(
    controller,
    line: str,
    config: ChatControlConfig,
    agent: OpenClawAgentClient,
    config_instance: str,
) -> bool:
    parsed = extract_chat_message(line)
    if not parsed:
        return False

    player, message = parsed
    request_text = extract_openclaw_request(message, config.trigger_word)
    if not request_text:
        return False

    LOGGER.info(
        "trigger matched player=%s request=%r raw=%r",
        player,
        request_text,
        message,
        extra={"config_instance": config_instance},
    )

    if config.ack_message and config.response_mode != "none":
        send_reply(controller, player, config.ack_message, config)

    prompt = build_openclaw_prompt(player, request_text, message, config, config_instance)
    LOGGER.debug("openclaw prompt: %s", prompt, extra={"config_instance": config_instance})
    response = agent.submit(prompt)
    LOGGER.info(
        "openclaw response length=%s",
        len(response),
        extra={"config_instance": config_instance},
    )
    LOGGER.debug("openclaw response: %s", response, extra={"config_instance": config_instance})
    send_reply(controller, player, response, config)
    return True


def build_listener_states(config: Dict, runtime: ChatControlConfig) -> List[ChatListenerState]:
    states = []
    for config_instance in runtime.config_instances:
        controller = build_controller(config, overrides={"config_instance": config_instance})
        states.append(
            ChatListenerState(
                config_instance=config_instance,
                controller=controller,
                previous_lines=[],
                seen_lines=deque(maxlen=512),
            )
        )
    return states


def run_loop(
    config_path: Optional[str] = None,
    config_instances: Optional[Sequence[str]] = None,
    listen_all_instances: bool = False,
) -> None:
    config, runtime = load_chat_config(
        config_path=config_path,
        config_instances=config_instances,
        listen_all_instances=listen_all_instances,
    )
    setup_logging(runtime)
    listener_states = build_listener_states(config, runtime)
    agent = OpenClawAgentClient(runtime)

    LOGGER.info("listening for trigger word: %s", runtime.trigger_word)
    LOGGER.info("listening on config instance(s): %s", ", ".join(runtime.config_instances))
    LOGGER.info("config file: %s", Path(config_path).resolve() if config_path else DEFAULT_CONFIG_PATH)
    LOGGER.info("log mode: %s%s", runtime.log_mode, f", file: {runtime.log_file}" if runtime.log_file else "")
    LOGGER.info("OpenClaw session args: %s", runtime.openclaw_session_args)
    LOGGER.info(
        "OpenClaw command: %s%s %s <prompt>",
        " ".join(runtime.openclaw_command),
        f" {' '.join(runtime.openclaw_session_args)}" if runtime.openclaw_session_args else "",
        runtime.openclaw_message_arg,
    )

    try:
        while True:
            for state in listener_states:
                result = state.controller.get_output(size=runtime.output_size)
                if not result.get("ok"):
                    LOGGER.error(
                        "failed to fetch output: %s",
                        result.get("error"),
                        extra={"config_instance": state.config_instance},
                    )
                    continue

                current_lines = normalize_output_lines(result.get("output", ""))
                new_lines = diff_new_lines(state.previous_lines, current_lines)
                state.previous_lines = current_lines

                for line in new_lines:
                    if not remember_line(state.seen_lines, line):
                        continue

                    try:
                        handled = process_chat_line(
                            state.controller,
                            line,
                            runtime,
                            agent,
                            state.config_instance,
                        )
                    except Exception as exc:
                        LOGGER.exception(
                            "request handling failed for line: %s",
                            line,
                            extra={"config_instance": state.config_instance},
                        )
                        parsed = extract_chat_message(line)
                        if parsed and runtime.error_message and runtime.response_mode != "none":
                            try:
                                send_reply(state.controller, parsed[0], build_error_reply(runtime, exc), runtime)
                            except Exception as send_exc:
                                LOGGER.exception(
                                    "failed to send error reply: %s",
                                    send_exc,
                                    extra={"config_instance": state.config_instance},
                                )
                        continue

                    if handled:
                        LOGGER.info(
                            "handled line: %s",
                            line,
                            extra={"config_instance": state.config_instance},
                        )

            time.sleep(runtime.poll_interval)
    finally:
        LOGGER.info("chat_control stopped")


def main() -> None:
    parser = argparse.ArgumentParser(description="Listen for in-game chat and forward OpenClaw requests")
    parser.add_argument("--config", help="Optional config file path")
    parser.add_argument(
        "--config-instance",
        action="append",
        dest="config_instances",
        help="Named mcsm config profile to listen on. Repeat to listen on multiple profiles.",
    )
    parser.add_argument(
        "--all-instances",
        action="store_true",
        help="Listen on every named mcsm config profile.",
    )
    args = parser.parse_args()

    try:
        run_loop(
            config_path=args.config,
            config_instances=args.config_instances,
            listen_all_instances=args.all_instances,
        )
    except KeyboardInterrupt:
        LOGGER.info("stopped by user")
    except Exception as exc:
        raise SystemExit(f"[chat_control] {exc}") from exc


if __name__ == "__main__":
    main()
