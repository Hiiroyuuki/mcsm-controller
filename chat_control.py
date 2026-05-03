import argparse
import json
import queue
import re
import shlex
import subprocess
import threading
import time
import uuid
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Deque, Dict, List, Optional, Sequence, TextIO, Tuple

from mcsm_skill import MCSMSkillError, build_controller, load_config


BASE_DIR = Path(__file__).resolve().parent
DEFAULT_CONFIG_PATH = BASE_DIR / "config.json"
DEFAULT_SYSTEM_PROMPT = (
    "You are OpenClaw, a Minecraft server assistant. "
    "The following content is a player request captured from in-game chat. "
    "Understand the request and handle it."
)
DEFAULT_OPENCLAW_COMMAND = ["openclaw", "agent", "--local"]
ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")


@dataclass
class ChatControlConfig:
    trigger_word: str
    poll_interval: float
    output_size: int
    openclaw_command: List[str]
    openclaw_timeout: int
    openclaw_reply_idle_timeout: float
    response_mode: str
    response_prefix: str
    ack_message: str
    error_message: str
    max_reply_length: int
    system_prompt: str


def load_chat_config(config_path: Optional[str] = None) -> Tuple[Dict, ChatControlConfig]:
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

    runtime = ChatControlConfig(
        trigger_word=str(chat_config.get("trigger_word", "openclaw")).strip() or "openclaw",
        poll_interval=float(chat_config.get("poll_interval", 2.0)),
        output_size=int(chat_config.get("output_size", 128)),
        openclaw_command=openclaw_command,
        openclaw_timeout=int(chat_config.get("openclaw_timeout", 120)),
        openclaw_reply_idle_timeout=float(chat_config.get("openclaw_reply_idle_timeout", 2.0)),
        response_mode=str(chat_config.get("response_mode", "msg")).strip().lower(),
        response_prefix=str(chat_config.get("response_prefix", "OpenClaw")).strip() or "OpenClaw",
        ack_message=str(chat_config.get("ack_message", "Received. Processing your request.")).strip(),
        error_message=str(chat_config.get("error_message", "Request failed. Please try again later.")).strip(),
        max_reply_length=max(20, int(chat_config.get("max_reply_length", 180))),
        system_prompt=str(chat_config.get("system_prompt", DEFAULT_SYSTEM_PROMPT)).strip() or DEFAULT_SYSTEM_PROMPT,
    )

    if runtime.poll_interval <= 0:
        raise MCSMSkillError("chat_control.poll_interval must be greater than 0")
    if runtime.output_size <= 0:
        raise MCSMSkillError("chat_control.output_size must be greater than 0")
    if runtime.openclaw_timeout <= 0:
        raise MCSMSkillError("chat_control.openclaw_timeout must be greater than 0")
    if runtime.openclaw_reply_idle_timeout <= 0:
        raise MCSMSkillError("chat_control.openclaw_reply_idle_timeout must be greater than 0")
    if runtime.response_mode not in {"none", "msg", "say"}:
        raise MCSMSkillError("chat_control.response_mode must be one of: none, msg, say")

    return config, runtime


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


def build_openclaw_prompt(player: str, request_text: str, raw_message: str, config: ChatControlConfig) -> str:
    payload = {
        "system_prompt": config.system_prompt,
        "player": player,
        "raw_message": raw_message,
        "request": request_text,
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


def clean_agent_output(text: str, sentinel: Optional[str] = None) -> str:
    output = ANSI_ESCAPE_RE.sub("", text)
    if sentinel and sentinel in output:
        output = output.split(sentinel, 1)[0]

    lines = []
    for line in output.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if sentinel and stripped == sentinel:
            continue
        lines.append(stripped)

    return "\n".join(lines).strip()


class OpenClawAgentSession:
    def __init__(self, config: ChatControlConfig):
        self.config = config
        self.process: Optional[subprocess.Popen[str]] = None
        self.output_queue: "queue.Queue[Tuple[str, str]]" = queue.Queue()
        self.reader_threads: List[threading.Thread] = []

    def start(self) -> None:
        if self.process and self.process.poll() is None:
            return

        self.process = subprocess.Popen(
            list(self.config.openclaw_command),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=0,
        )
        self.reader_threads = []

        if self.process.stdout:
            self._start_reader("stdout", self.process.stdout)
        if self.process.stderr:
            self._start_reader("stderr", self.process.stderr)

        self._drain_startup_output()

    def _start_reader(self, source: str, stream: TextIO) -> None:
        thread = threading.Thread(target=self._read_stream, args=(source, stream), daemon=True)
        thread.start()
        self.reader_threads.append(thread)

    def _read_stream(self, source: str, stream: TextIO) -> None:
        while True:
            try:
                char = stream.read(1)
            except ValueError:
                return
            if char == "":
                return
            self.output_queue.put((source, char))

    def _drain_startup_output(self) -> None:
        self._drain_output_for(min(1.0, self.config.openclaw_reply_idle_timeout))

    def _drain_output_for(self, duration: float) -> None:
        end_at = time.monotonic() + duration
        while time.monotonic() < end_at:
            try:
                self.output_queue.get(timeout=0.05)
            except queue.Empty:
                pass

    def _ensure_running(self) -> subprocess.Popen[str]:
        self.start()
        if not self.process:
            raise RuntimeError("failed to start openclaw agent")
        if self.process.poll() is not None:
            raise RuntimeError(f"openclaw agent exited with code {self.process.returncode}")
        if not self.process.stdin:
            raise RuntimeError("openclaw agent stdin is not available")
        return self.process

    def submit(self, prompt: str) -> str:
        process = self._ensure_running()
        sentinel = f"OPENCLAW_CHAT_DONE_{uuid.uuid4().hex}"
        agent_input = (
            f"{prompt}\n\n"
            "Reply to the Minecraft player request above. "
            f"When your reply is complete, print {sentinel} on its own line."
        )

        process.stdin.write(agent_input.rstrip() + "\n")
        process.stdin.flush()

        stdout_parts: List[str] = []
        stderr_parts: List[str] = []
        deadline = time.monotonic() + self.config.openclaw_timeout
        last_output_at: Optional[float] = None

        while time.monotonic() < deadline:
            if process.poll() is not None:
                break

            try:
                source, char = self.output_queue.get(timeout=0.1)
            except queue.Empty:
                if last_output_at and time.monotonic() - last_output_at >= self.config.openclaw_reply_idle_timeout:
                    break
                continue

            last_output_at = time.monotonic()
            if source == "stderr":
                stderr_parts.append(char)
            else:
                stdout_parts.append(char)
                if sentinel in "".join(stdout_parts):
                    self._drain_output_for(0.2)
                    break

        stdout = clean_agent_output("".join(stdout_parts), sentinel)
        stderr = clean_agent_output("".join(stderr_parts), sentinel)

        if process.poll() is not None:
            message = stderr or stdout or f"openclaw agent exited with code {process.returncode}"
            raise RuntimeError(message)

        if not stdout and not stderr:
            raise RuntimeError("openclaw agent did not return a response")

        return stdout or stderr

    def close(self) -> None:
        if not self.process or self.process.poll() is not None:
            return

        self.process.terminate()
        try:
            self.process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.wait(timeout=5)


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


def process_chat_line(controller, line: str, config: ChatControlConfig, agent: OpenClawAgentSession) -> bool:
    parsed = extract_chat_message(line)
    if not parsed:
        return False

    player, message = parsed
    request_text = extract_openclaw_request(message, config.trigger_word)
    if not request_text:
        return False

    if config.ack_message and config.response_mode != "none":
        send_reply(controller, player, config.ack_message, config)

    prompt = build_openclaw_prompt(player, request_text, message, config)
    response = agent.submit(prompt)
    send_reply(controller, player, response, config)
    return True


def run_loop(config_path: Optional[str] = None) -> None:
    config, runtime = load_chat_config(config_path=config_path)
    controller = build_controller(config)
    agent = OpenClawAgentSession(runtime)
    previous_lines: List[str] = []
    seen_lines: Deque[str] = deque(maxlen=512)

    print(f"[chat_control] listening for trigger word: {runtime.trigger_word}")
    print(f"[chat_control] starting persistent OpenClaw agent: {' '.join(runtime.openclaw_command)}")
    agent.start()

    try:
        while True:
            result = controller.get_output(size=runtime.output_size)
            if not result.get("ok"):
                print(f"[chat_control] failed to fetch output: {result.get('error')}")
                time.sleep(runtime.poll_interval)
                continue

            current_lines = normalize_output_lines(result.get("output", ""))
            new_lines = diff_new_lines(previous_lines, current_lines)
            previous_lines = current_lines

            for line in new_lines:
                if not remember_line(seen_lines, line):
                    continue

                try:
                    handled = process_chat_line(controller, line, runtime, agent)
                except Exception as exc:
                    print(f"[chat_control] request handling failed: {exc}")
                    parsed = extract_chat_message(line)
                    if parsed and runtime.error_message and runtime.response_mode != "none":
                        try:
                            send_reply(controller, parsed[0], runtime.error_message, runtime)
                        except Exception as send_exc:
                            print(f"[chat_control] failed to send error reply: {send_exc}")
                    continue

                if handled:
                    print(f"[chat_control] handled line: {line}")

            time.sleep(runtime.poll_interval)
    finally:
        agent.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Listen for in-game chat and forward OpenClaw requests")
    parser.add_argument("--config", help="Optional config file path")
    args = parser.parse_args()

    try:
        run_loop(config_path=args.config)
    except KeyboardInterrupt:
        print("[chat_control] stopped by user")
    except Exception as exc:
        raise SystemExit(f"[chat_control] {exc}") from exc


if __name__ == "__main__":
    main()
