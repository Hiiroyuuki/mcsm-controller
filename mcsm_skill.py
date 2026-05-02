import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, Optional
from mcsm_control import MCSMController


BASE_DIR = Path(__file__).resolve().parent
DEFAULT_CONFIG_PATH = BASE_DIR / "config.json"


class MCSMSkillError(Exception):
    """Raised when the skill input or configuration is invalid."""


def load_config(config_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Purpose
    ======
    Load the local MCSM skill configuration file.

    Input
    ======
    - config_path: Optional explicit config file path

    Return
    ======
    - dict: Parsed configuration dictionary
    """
    resolved_path = Path(config_path).resolve() if config_path else DEFAULT_CONFIG_PATH
    if not resolved_path.exists():
        raise MCSMSkillError(f"Config file not found: {resolved_path}")

    with resolved_path.open("r", encoding="utf-8") as f:
        config = json.load(f)

    if not isinstance(config, dict):
        raise MCSMSkillError("Config file must contain a JSON object")
    return config


def build_controller(config: Dict[str, Any], overrides: Optional[Dict[str, Any]] = None) -> MCSMController:
    """
    Purpose
    ======
    Build an MCSMController instance from config and optional runtime overrides.

    Input
    ======
    - config: Skill configuration dictionary
    - overrides: Optional runtime override values

    Return
    ======
    - MCSMController: Configured controller instance
    """
    overrides = overrides or {}
    controller_config = config.get("mcsm", {})
    if not isinstance(controller_config, dict):
        raise MCSMSkillError("config.mcsm must be a JSON object")

    base_url = overrides.get("base_url") or controller_config.get("base_url")
    apikey = overrides.get("apikey") or controller_config.get("apikey")
    daemon_id = overrides.get("daemon_id") or controller_config.get("daemon_id")
    instance_uuid = overrides.get("instance_uuid") or controller_config.get("instance_uuid")
    timeout = overrides.get("timeout", controller_config.get("timeout", 10))

    if not base_url:
        raise MCSMSkillError("MCSM base_url is required")
    if not apikey:
        raise MCSMSkillError("MCSM apikey is required")

    return MCSMController(
        base_url=base_url,
        apikey=apikey,
        daemon_id=daemon_id,
        instance_uuid=instance_uuid,
        timeout=timeout,
    )


def _config_bool(config: Dict[str, Any], key: str, default: bool) -> bool:
    value = config.get("skill", {}).get(key, default)
    return bool(value)


def _allowed_actions(config: Dict[str, Any]):
    actions = config.get("skill", {}).get("allowed_actions", [])
    if not isinstance(actions, list):
        raise MCSMSkillError("config.skill.allowed_actions must be a list")
    return set(actions)


def _resolve_instance_args(config: Dict[str, Any], payload: Dict[str, Any]) -> Dict[str, Any]:
    allow_instance_override = _config_bool(config, "allow_instance_override", True)

    runtime_daemon_id = payload.get("daemon_id")
    runtime_instance_uuid = payload.get("instance_uuid")
    if (runtime_daemon_id or runtime_instance_uuid) and not allow_instance_override:
        raise MCSMSkillError("Instance override is disabled by config")

    return {
        "daemon_id": runtime_daemon_id,
        "instance_uuid": runtime_instance_uuid,
    }


def dispatch_action(controller: MCSMController, config: Dict[str, Any], action: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Purpose
    ======
    Dispatch one skill action to the underlying MCSM controller.

    Input
    ======
    - controller: Initialized MCSM controller
    - config: Skill configuration dictionary
    - action: Action name to execute
    - payload: Runtime payload dictionary

    Return
    ======
    - dict: Standardized action result
    """
    allowed_actions = _allowed_actions(config)
    if allowed_actions and action not in allowed_actions:
        raise MCSMSkillError(f"Action is not allowed by config: {action}")

    instance_args = _resolve_instance_args(config, payload)
    result: Dict[str, Any]

    if action == "status":
        result = controller.status(**instance_args)
    elif action == "start":
        result = controller.start(**instance_args)
    elif action == "stop":
        result = controller.stop(**instance_args)
    elif action == "restart":
        result = controller.restart(**instance_args)
    elif action == "kill":
        result = controller.kill(**instance_args)
    elif action == "update_task":
        result = controller.update_task(**instance_args)
    elif action == "send_command":
        command = payload.get("command")
        if not command:
            raise MCSMSkillError("command is required for send_command")
        result = controller.send_command(command=command, **instance_args)
    elif action == "get_output":
        size = payload.get("size", 64)
        result = controller.get_output(size=size, **instance_args)
    elif action == "get_messages":
        result = controller.get_messages(
            size=payload.get("size", 64),
            limit=payload.get("limit", 100),
            since_id=payload.get("since_id"),
            **instance_args,
        )
    elif action == "list_instances":
        list_daemon_id = payload.get("daemon_id") or controller.daemon_id
        result = controller.list_instances(
            daemon_id=list_daemon_id,
            page=payload.get("page", 1),
            page_size=payload.get("page_size", 20),
            instance_name=payload.get("instance_name"),
            status=payload.get("status"),
        )
    elif action == "get_instance":
        result = controller.get_instance(**instance_args)
    elif action == "reinstall":
        target_url = payload.get("target_url")
        title = payload.get("title")
        if not target_url or not title:
            raise MCSMSkillError("target_url and title are required for reinstall")
        result = controller.reinstall(
            target_url=target_url,
            title=title,
            description=payload.get("description", ""),
            **instance_args,
        )
    else:
        raise MCSMSkillError(f"Unsupported action: {action}")

    result["action"] = action
    return result


def invoke(action: str, payload: Optional[Dict[str, Any]] = None, config_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Purpose
    ======
    Public skill entrypoint used by OpenClaw or local scripts.

    Input
    ======
    - action: Action name to execute
    - payload: Optional runtime payload
    - config_path: Optional explicit config file path

    Return
    ======
    - dict: Skill execution result
    """
    payload = payload or {}
    config = load_config(config_path=config_path)
    controller = build_controller(config, overrides=payload)

    try:
        result = dispatch_action(controller, config, action, payload)
    except Exception as exc:
        return {
            "ok": False,
            "action": action,
            "error": str(exc),
        }

    return result


def invoke_from_payload(payload: Dict[str, Any], config_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Purpose
    ======
    Execute one skill request from a full JSON payload object.

    Input
    ======
    - payload: Full request payload, must include an action field
    - config_path: Optional explicit config file path

    Return
    ======
    - dict: Skill execution result
    """
    if not isinstance(payload, dict):
        raise MCSMSkillError("payload must be a JSON object")

    action = payload.get("action")
    if not action:
        raise MCSMSkillError("payload.action is required")

    return invoke(action=action, payload=payload, config_path=config_path)


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


def main():
    """
    Purpose
    ======
    Command-line entrypoint for local testing or script-based integration.

    Input
    ======
    - CLI arguments and optional JSON payload from stdin

    Return
    ======
    - None
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
            payload = _read_payload_from_stdin()

        if args.action:
            payload["action"] = args.action

        result = invoke_from_payload(payload, config_path=args.config)
    except Exception as exc:
        result = {
            "ok": False,
            "error": str(exc),
        }

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
