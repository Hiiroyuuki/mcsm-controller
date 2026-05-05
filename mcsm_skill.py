import argparse
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, Optional

from mcsm_control import MCSMController


BASE_DIR = Path(__file__).resolve().parent
DEFAULT_CONFIG_PATH = BASE_DIR / "config.json"
CONNECTION_KEYS = {"base_url", "apikey", "daemon_id", "instance_uuid", "timeout"}
PLACEHOLDER_PREFIX = "replace_with_"
CHAT_CONTROL_SCRIPT = BASE_DIR / "chat_control.py"
RUNTIME_DIR = BASE_DIR / ".runtime"


class MCSMSkillError(Exception):
    """Raised when the skill input or configuration is invalid."""


def _bool_config(value: Any, default: bool = False) -> bool:
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


def _safe_runtime_name(value: str) -> str:
    return "".join(char if char.isalnum() or char in {"-", "_", "."} else "_" for char in value)


class MCSM:
    def __init__(
        self,
        config_path: Optional[str] = None,
        payload: Optional[Dict[str, Any]] = None,
    ):
        self.config_path = config_path
        self.payload = payload or {}
        self.config = self.load_config()

    def load_config(self) -> Dict[str, Any]:
        """
        Purpose
        ======
        Load the local MCSM skill configuration file.

        Return
        ======
        - dict: Parsed configuration dictionary
        """
        resolved_path = Path(self.config_path).resolve() if self.config_path else DEFAULT_CONFIG_PATH
        if not resolved_path.exists():
            raise MCSMSkillError(f"Config file not found: {resolved_path}")

        with resolved_path.open("r", encoding="utf-8") as f:
            config = json.load(f)

        if not isinstance(config, dict):
            raise MCSMSkillError("Config file must contain a JSON object")
        return config

    def _skill_config(self) -> Dict[str, Any]:
        skill_config = self.config.get("skill", {})
        if not isinstance(skill_config, dict):
            raise MCSMSkillError("config.skill must be a JSON object")
        return skill_config

    def _raw_mcsm_config(self) -> Dict[str, Any]:
        mcsm_config = self.config.get("mcsm", {})
        if not isinstance(mcsm_config, dict):
            raise MCSMSkillError("config.mcsm must be a JSON object")
        return mcsm_config

    def _is_connection_config(self, value: Any) -> bool:
        return isinstance(value, dict) and bool(CONNECTION_KEYS.intersection(value.keys()))

    def _validate_connection_config(self, name: str, value: Any) -> Dict[str, Any]:
        if not isinstance(value, dict):
            raise MCSMSkillError(f"{name} must be a JSON object")

        required_keys = ("base_url", "apikey", "daemon_id", "instance_uuid")
        missing_keys = [key for key in required_keys if not value.get(key)]
        if missing_keys:
            raise MCSMSkillError(f"{name} is missing required fields: {', '.join(missing_keys)}")

        placeholder_keys = []
        for key in required_keys:
            field_value = value.get(key)
            if isinstance(field_value, str) and field_value.strip().lower().startswith(PLACEHOLDER_PREFIX):
                placeholder_keys.append(key)

        if placeholder_keys:
            raise MCSMSkillError(
                f"{name} still contains template placeholder values: {', '.join(placeholder_keys)}"
            )

        return value

    def _config_instance_map(self) -> Dict[str, Dict[str, Any]]:
        mcsm_config = self._raw_mcsm_config()
        if self._is_connection_config(mcsm_config):
            return {"default": mcsm_config}

        return mcsm_config

    def list_config_instance_names(self):
        return list(self._config_instance_map().keys())

    def list_instances_from_config(self) -> Dict[str, Dict[str, Any]]:
        """
        Purpose
        ======
        List configured MCSM connection profiles.

        Return
        ======
        - dict: Mapping of config instance name to connection settings
        """
        raw_mcsm_config = self._raw_mcsm_config()
        if self._is_connection_config(raw_mcsm_config):
            return {"default": self._validate_connection_config("config.mcsm", raw_mcsm_config)}

        mcsm_config = self._config_instance_map()

        for name, instance_config in mcsm_config.items():
            mcsm_config[name] = self._validate_connection_config(f"config.mcsm.{name}", instance_config)
        return mcsm_config

    def _resolve_config_instance_name(self) -> str:
        instances = self._config_instance_map()
        if not instances:
            raise MCSMSkillError("config.mcsm is empty")

        requested_name = self.payload.get("config_instance")
        default_name = self._skill_config().get("default_instance")

        if requested_name:
            if requested_name not in instances:
                raise MCSMSkillError(f"Unknown config_instance: {requested_name}")
            return requested_name

        if default_name:
            if default_name not in instances:
                raise MCSMSkillError(f"skill.default_instance not found in config.mcsm: {default_name}")
            return default_name

        return next(iter(instances))

    def _resolve_controller_config(self) -> Dict[str, Any]:
        mcsm_config = self._raw_mcsm_config()
        if self._is_connection_config(mcsm_config):
            return self._validate_connection_config("config.mcsm", mcsm_config)

        instance_name = self._resolve_config_instance_name()
        return self._validate_connection_config(
            f"config.mcsm.{instance_name}",
            self._config_instance_map()[instance_name],
        )

    def build_controller(self, overrides: Optional[Dict[str, Any]] = None) -> MCSMController:
        """
        Purpose
        ======
        Build an MCSMController instance from config and optional runtime overrides.

        Return
        ======
        - MCSMController: Configured controller instance
        """
        overrides = overrides or {}
        controller_config = self._resolve_controller_config()

        base_url = overrides.get("base_url") or controller_config.get("base_url")
        apikey = overrides.get("apikey") or controller_config.get("apikey")
        timeout = overrides.get("timeout", controller_config.get("timeout", 10))

        if not base_url:
            raise MCSMSkillError("MCSM base_url is required")
        if not apikey:
            raise MCSMSkillError("MCSM apikey is required")

        return MCSMController(
            base_url=base_url,
            apikey=apikey,
            daemon_id=controller_config.get("daemon_id"),
            instance_uuid=controller_config.get("instance_uuid"),
            timeout=timeout,
        )

    def _config_bool(self, key: str, default: bool) -> bool:
        value = self._skill_config().get(key, default)
        return _bool_config(value, default=default)

    def _allowed_actions(self):
        actions = self._skill_config().get("allowed_actions", [])
        if not isinstance(actions, list):
            raise MCSMSkillError("config.skill.allowed_actions must be a list")
        return set(actions)

    def _resolved_config_path(self) -> Path:
        return Path(self.config_path).resolve() if self.config_path else DEFAULT_CONFIG_PATH

    def _selected_instance_config(self) -> Dict[str, Any]:
        mcsm_config = self._raw_mcsm_config()
        if self._is_connection_config(mcsm_config):
            return mcsm_config

        instance_name = self._resolve_config_instance_name()
        return self._config_instance_map()[instance_name]

    def _chat_control_pid_path(self, config_instance: str) -> Path:
        return RUNTIME_DIR / f"chat_control_{_safe_runtime_name(config_instance)}.pid.json"

    def _chat_control_log_path(self, config_instance: str) -> Path:
        return RUNTIME_DIR / f"chat_control_{_safe_runtime_name(config_instance)}.log"

    def _chat_control_enabled(self) -> bool:
        instance_config = self._selected_instance_config()
        return _bool_config(instance_config.get("chat_control_enabled"), default=False)

    def _read_chat_control_pid(self, config_instance: str) -> Optional[int]:
        pid_path = self._chat_control_pid_path(config_instance)
        if not pid_path.exists():
            return None

        try:
            with pid_path.open("r", encoding="utf-8") as f:
                payload = json.load(f)
        except Exception:
            return None

        pid = payload.get("pid") if isinstance(payload, dict) else None
        try:
            return int(pid) if pid else None
        except (TypeError, ValueError):
            return None

    def _process_is_running(self, pid: Optional[int]) -> bool:
        if not pid or pid <= 0:
            return False

        try:
            os.kill(pid, 0)
        except OSError:
            return False
        return True

    def _chat_control_status(self, config_instance: str) -> Dict[str, Any]:
        pid = self._read_chat_control_pid(config_instance)
        running = self._process_is_running(pid)
        return {
            "enabled": self._chat_control_enabled(),
            "running": running,
            "pid": pid if running else None,
            "pid_file": str(self._chat_control_pid_path(config_instance)),
        }

    def _start_chat_control(self, config_instance: str, instance_args: Dict[str, Any]) -> Dict[str, Any]:
        if instance_args.get("daemon_id") or instance_args.get("instance_uuid"):
            return {
                "enabled": False,
                "started": False,
                "running": False,
                "reason": "runtime daemon_id/instance_uuid override is not backed by a named config instance",
            }

        if not self._chat_control_enabled():
            return {
                "enabled": False,
                "started": False,
                "running": False,
                "reason": "mcsm config profile has chat_control_enabled=false",
            }

        existing_pid = self._read_chat_control_pid(config_instance)
        if self._process_is_running(existing_pid):
            return {
                "enabled": True,
                "started": False,
                "running": True,
                "pid": existing_pid,
                "reason": "chat_control is already running",
            }

        RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
        pid_path = self._chat_control_pid_path(config_instance)
        log_path = self._chat_control_log_path(config_instance)
        command = [
            sys.executable,
            str(CHAT_CONTROL_SCRIPT),
            "--config",
            str(self._resolved_config_path()),
            "--config-instance",
            config_instance,
        ]

        creationflags = 0
        if os.name == "nt":
            creationflags |= getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
            creationflags |= getattr(subprocess, "CREATE_NO_WINDOW", 0)

        with log_path.open("a", encoding="utf-8") as log_file:
            process = subprocess.Popen(
                command,
                cwd=str(BASE_DIR),
                stdin=subprocess.DEVNULL,
                stdout=log_file,
                stderr=subprocess.STDOUT,
                creationflags=creationflags,
            )

        time.sleep(0.2)
        if process.poll() is not None:
            pid_path.unlink(missing_ok=True)
            return {
                "enabled": True,
                "started": False,
                "running": False,
                "exit_code": process.returncode,
                "log_file": str(log_path),
                "error": "chat_control exited during startup",
            }

        with pid_path.open("w", encoding="utf-8") as f:
            json.dump(
                {
                    "pid": process.pid,
                    "config_instance": config_instance,
                    "command": command,
                    "started_at": time.time(),
                    "log_file": str(log_path),
                },
                f,
                ensure_ascii=False,
                indent=2,
            )

        return {
            "enabled": True,
            "started": True,
            "running": True,
            "pid": process.pid,
            "pid_file": str(pid_path),
            "log_file": str(log_path),
        }

    def _stop_chat_control(self, config_instance: str, instance_args: Dict[str, Any]) -> Dict[str, Any]:
        if instance_args.get("daemon_id") or instance_args.get("instance_uuid"):
            return {
                "stopped": False,
                "running": False,
                "reason": "runtime daemon_id/instance_uuid override is not backed by a named config instance",
            }

        pid_path = self._chat_control_pid_path(config_instance)
        pid = self._read_chat_control_pid(config_instance)
        if not pid:
            return {
                "stopped": False,
                "running": False,
                "reason": "no chat_control pid file",
            }

        if not self._process_is_running(pid):
            pid_path.unlink(missing_ok=True)
            return {
                "stopped": False,
                "running": False,
                "pid": pid,
                "reason": "stale chat_control pid file removed",
            }

        try:
            if os.name == "nt":
                subprocess.run(
                    ["taskkill", "/PID", str(pid), "/T", "/F"],
                    capture_output=True,
                    text=True,
                    timeout=10,
                    check=False,
                )
            else:
                os.kill(pid, signal.SIGTERM)
                deadline = time.monotonic() + 5
                while time.monotonic() < deadline and self._process_is_running(pid):
                    time.sleep(0.1)
                if self._process_is_running(pid):
                    os.kill(pid, signal.SIGKILL)
        except Exception as exc:
            return {
                "stopped": False,
                "running": self._process_is_running(pid),
                "pid": pid,
                "error": str(exc),
            }

        pid_path.unlink(missing_ok=True)
        return {
            "stopped": True,
            "running": False,
            "pid": pid,
            "pid_file": str(pid_path),
        }

    def _resolve_instance_args(self) -> Dict[str, Any]:
        allow_instance_override = self._config_bool("allow_instance_override", True)

        runtime_daemon_id = self.payload.get("daemon_id")
        runtime_instance_uuid = self.payload.get("instance_uuid")
        if (runtime_daemon_id or runtime_instance_uuid) and not allow_instance_override:
            raise MCSMSkillError("Instance override is disabled by config")

        return {
            "daemon_id": runtime_daemon_id,
            "instance_uuid": runtime_instance_uuid,
        }

    def dispatch_action(self, controller: MCSMController, action: str) -> Dict[str, Any]:
        """
        Purpose
        ======
        Dispatch one skill action to the underlying MCSM controller.

        Return
        ======
        - dict: Standardized action result
        """
        allowed_actions = self._allowed_actions()
        if allowed_actions and action not in allowed_actions:
            raise MCSMSkillError(f"Action is not allowed by config: {action}")

        instance_args = self._resolve_instance_args()
        config_instance = self._resolve_config_instance_name()
        result: Dict[str, Any]

        if action == "status":
            result = controller.status(**instance_args)
            if result.get("ok") and not (instance_args.get("daemon_id") or instance_args.get("instance_uuid")):
                result["chat_control"] = self._chat_control_status(config_instance)
        elif action == "start":
            result = controller.start(**instance_args)
            if result.get("ok"):
                result["chat_control"] = self._start_chat_control(config_instance, instance_args)
        elif action == "stop":
            result = controller.stop(**instance_args)
            if result.get("ok"):
                result["chat_control"] = self._stop_chat_control(config_instance, instance_args)
        elif action == "restart":
            result = controller.restart(**instance_args)
            if result.get("ok"):
                if self._chat_control_enabled():
                    result["chat_control"] = self._start_chat_control(config_instance, instance_args)
                else:
                    result["chat_control"] = self._stop_chat_control(config_instance, instance_args)
        elif action == "kill":
            result = controller.kill(**instance_args)
            if result.get("ok"):
                result["chat_control"] = self._stop_chat_control(config_instance, instance_args)
        elif action == "update_task":
            result = controller.update_task(**instance_args)
        elif action == "send_command":
            command = self.payload.get("command")
            if not command:
                raise MCSMSkillError("command is required for send_command")
            result = controller.send_command(command=command, **instance_args)
        elif action == "get_output":
            size = self.payload.get("size", 64)
            result = controller.get_output(size=size, **instance_args)
        elif action == "get_messages":
            result = controller.get_messages(
                size=self.payload.get("size", 64),
                limit=self.payload.get("limit", 100),
                since_id=self.payload.get("since_id"),
                **instance_args,
            )
        elif action == "list_instances":
            allow_instance_override = self._config_bool("allow_instance_override", True)
            list_daemon_id = self.payload.get("daemon_id") or controller.daemon_id
            if self.payload.get("daemon_id") and not allow_instance_override:
                raise MCSMSkillError("Instance override is disabled by config")
            result = controller.list_instances(
                daemon_id=list_daemon_id,
                page=self.payload.get("page", 1),
                page_size=self.payload.get("page_size", 20),
                instance_name=self.payload.get("instance_name"),
                status=self.payload.get("status"),
            )
        elif action == "get_instance":
            result = controller.get_instance(**instance_args)
        elif action == "reinstall":
            target_url = self.payload.get("target_url")
            title = self.payload.get("title")
            if not target_url or not title:
                raise MCSMSkillError("target_url and title are required for reinstall")
            result = controller.reinstall(
                target_url=target_url,
                title=title,
                description=self.payload.get("description", ""),
                **instance_args,
            )
        else:
            raise MCSMSkillError(f"Unsupported action: {action}")

        result["action"] = action
        result["config_instance"] = config_instance
        return result

    def invoke(self, action: str) -> Dict[str, Any]:
        """
        Purpose
        ======
        Public skill entrypoint used by OpenClaw or local scripts.

        Return
        ======
        - dict: Skill execution result
        """
        try:
            controller = self.build_controller(overrides=self.payload)
            result = self.dispatch_action(controller, action)
        except Exception as exc:
            error_result = {
                "ok": False,
                "action": action,
                "error": str(exc),
            }
            try:
                controller_config = self._resolve_controller_config()
                error_result["config_instance"] = self._resolve_config_instance_name()
                error_result["base_url"] = self.payload.get("base_url") or controller_config.get("base_url")
                error_result["daemon_id"] = self.payload.get("daemon_id") or controller_config.get("daemon_id")
                error_result["instance_uuid"] = self.payload.get("instance_uuid") or controller_config.get("instance_uuid")
            except Exception:
                pass
            return error_result

        return result

    def invoke_from_payload(self) -> Dict[str, Any]:
        """
        Purpose
        ======
        Execute one skill request from a full JSON payload object.

        Return
        ======
        - dict: Skill execution result
        """
        if not isinstance(self.payload, dict):
            raise MCSMSkillError("payload must be a JSON object")

        action = self.payload.get("action")
        if not action:
            raise MCSMSkillError("payload.action is required")

        return self.invoke(action=action)

    @staticmethod
    def _read_payload_from_stdin() -> Dict[str, Any]:
        raw = sys.stdin.read().strip()
        if not raw:
            return {}
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise MCSMSkillError(f"Invalid JSON from stdin: {exc}") from exc
        if not isinstance(payload, dict):
            raise MCSMSkillError("stdin payload must be a JSON object")
        return payload


def load_config(config_path: Optional[str] = None) -> Dict[str, Any]:
    return MCSM(config_path=config_path).config


def build_controller(config: Dict[str, Any], overrides: Optional[Dict[str, Any]] = None) -> MCSMController:
    if not isinstance(config, dict):
        raise MCSMSkillError("config must be a JSON object")

    skill = MCSM.__new__(MCSM)
    skill.config_path = None
    skill.payload = overrides or {}
    skill.config = config
    return skill.build_controller(overrides=overrides)


def invoke(action: str, payload: Optional[Dict[str, Any]] = None, config_path: Optional[str] = None) -> Dict[str, Any]:
    return MCSM(config_path=config_path, payload=payload).invoke(action=action)


def invoke_from_payload(payload: Dict[str, Any], config_path: Optional[str] = None) -> Dict[str, Any]:
    return MCSM(config_path=config_path, payload=payload).invoke_from_payload()


def main():
    """
    Purpose
    ======
    Command-line entrypoint for local testing or script-based integration.
    """
    parser = argparse.ArgumentParser(description="OpenClaw self-use MCSM skill entrypoint")
    parser.add_argument("--action", help="Action name to execute")
    parser.add_argument("--payload", help="Inline JSON payload")
    parser.add_argument("--config", help="Optional config file path")
    args = parser.parse_args()

    try:
        if args.payload:
            payload = json.loads(args.payload)
            if not isinstance(payload, dict):
                raise MCSMSkillError("--payload must be a JSON object")
        else:
            payload = MCSM._read_payload_from_stdin()

        if args.action:
            payload["action"] = args.action

        result = MCSM(config_path=args.config, payload=payload).invoke_from_payload()
    except Exception as exc:
        result = {
            "ok": False,
            "error": str(exc),
        }

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
