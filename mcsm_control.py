import json
from datetime import datetime
from typing import Any, Dict, Iterable, Optional
from urllib import error, parse, request


class MCSMApiError(Exception):
    """Raised when the MCSManager API returns an error."""


class MCSMController:
    """
    Lightweight MCSManager instance API client.

    The controller follows the official MCSManager instance API:
    https://docs.mcsmanager.com/zh_cn/apis/api_instance.html
    """

    def __init__(
        self,
        base_url: str,
        apikey: str,
        daemon_id: Optional[str] = None,
        instance_uuid: Optional[str] = None,
        timeout: int = 10,
    ):
        """
        Purpose
        ======
        Initialize the MCSManager controller with the panel address, API key,
        and optional default daemon / instance identifiers.

        Input
        ======
        - base_url: MCSManager panel URL, for example "http://127.0.0.1:23333"
        - apikey: MCSManager user API key
        - daemon_id: Default daemon ID, optional
        - instance_uuid: Default instance UUID, optional
        - timeout: HTTP request timeout in seconds

        Return
        ======
        - None
        """
        self.base_url = base_url.rstrip("/")
        self.apikey = apikey
        self.daemon_id = daemon_id
        self.instance_uuid = instance_uuid
        self.timeout = timeout

    def bind_instance(self, daemon_id: str, instance_uuid: str) -> None:
        """
        Purpose
        ======
        Bind a default daemon ID and instance UUID so instance-level methods
        can be called without repeating them each time.

        Input
        ======
        - daemon_id: Daemon ID
        - instance_uuid: Instance UUID

        Return
        ======
        - None
        """
        self.daemon_id = daemon_id
        self.instance_uuid = instance_uuid

    def _resolve_instance(self, daemon_id=None, instance_uuid=None):
        """
        Purpose
        ======
        Merge the daemon / instance identifiers provided by the caller with
        the controller defaults and return the effective pair.

        Input
        ======
        - daemon_id: Daemon ID provided by the caller, optional
        - instance_uuid: Instance UUID provided by the caller, optional

        Return
        ======
        - (resolved_daemon_id, resolved_instance_uuid): Effective daemon ID and instance UUID
        """
        resolved_daemon_id = daemon_id or self.daemon_id
        resolved_instance_uuid = instance_uuid or self.instance_uuid

        if not resolved_daemon_id:
            raise ValueError("daemon_id is required")
        if not resolved_instance_uuid:
            raise ValueError("instance_uuid is required")

        return resolved_daemon_id, resolved_instance_uuid

    def _build_url(self, path: str, query: Optional[Dict[str, Any]] = None) -> str:
        """
        Purpose
        ======
        Build a full request URL with the API key and query parameters.

        Input
        ======
        - path: API path
        - query: Additional query parameters

        Return
        ======
        - str: Fully qualified request URL
        """
        merged_query = {"apikey": self.apikey}
        if query:
            merged_query.update({k: v for k, v in query.items() if v is not None})

        return f"{self.base_url}{path}?{parse.urlencode(merged_query, doseq=True)}"

    def _parse_response_body(self, payload: bytes):
        """
        Purpose
        ======
        Parse an HTTP response body, preferring JSON and falling back to plain text.

        Input
        ======
        - payload: Raw response bytes

        Return
        ======
        - Parsed response data as dict / list, or a wrapped text response
        """
        text = payload.decode("utf-8", errors="replace")
        if not text:
            return {}

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return {"status": 200, "data": text}

    def _request(
        self,
        method: str,
        path: str,
        query: Optional[Dict[str, Any]] = None,
        body: Optional[Dict[str, Any]] = None,
    ):
        """
        Purpose
        ======
        Send one HTTP request to MCSManager and normalize status / error handling.

        Input
        ======
        - method: HTTP method such as GET / POST / PUT / DELETE
        - path: API path
        - query: Query parameters
        - body: JSON request body

        Return
        ======
        - dict | list: Parsed response content
        """
        payload = None
        if body is not None:
            payload = json.dumps(body, ensure_ascii=False).encode("utf-8")

        req = request.Request(
            self._build_url(path, query),
            data=payload,
            method=method,
            headers={
                "Content-Type": "application/json; charset=utf-8",
                "X-Requested-With": "XMLHttpRequest",
            },
        )

        try:
            with request.urlopen(req, timeout=self.timeout) as resp:
                data = self._parse_response_body(resp.read())
        except error.HTTPError as exc:
            err_data = self._parse_response_body(exc.read())
            message = self._extract_error_message(err_data) or f"HTTP {exc.code}"
            raise MCSMApiError(message) from exc
        except error.URLError as exc:
            raise MCSMApiError(str(exc.reason)) from exc

        if isinstance(data, dict):
            status = data.get("status")
            if status not in (None, 200):
                raise MCSMApiError(self._extract_error_message(data) or f"API status {status}")

        return data

    def _extract_error_message(self, payload):
        """
        Purpose
        ======
        Extract a readable error message from an API response payload when possible.

        Input
        ======
        - payload: API response object

        Return
        ======
        - str | None: Extracted error message
        """
        if not isinstance(payload, dict):
            return str(payload)

        for key in ("data", "message", "msg", "error"):
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return None

    def _ok(self, **kwargs):
        """
        Purpose
        ======
        Wrap a successful result in a consistent return structure.

        Input
        ======
        - kwargs: Extra fields to add to the result

        Return
        ======
        - dict: Result object containing ok=True
        """
        result = {"ok": True}
        result.update(kwargs)
        return result

    def _fail(self, exc: Exception, **kwargs):
        """
        Purpose
        ======
        Wrap a failed result in a consistent return structure.

        Input
        ======
        - exc: Exception object
        - kwargs: Context fields to include in the error result

        Return
        ======
        - dict: Result object containing ok=False and an error message
        """
        result = {"ok": False, "error": str(exc)}
        result.update(kwargs)
        return result

    def _run(self, action, **kwargs):
        """
        Purpose
        ======
        Execute an action callback and convert raised exceptions into the
        standardized result format.

        Input
        ======
        - action: Callable to execute
        - kwargs: Context fields to include if the action fails

        Return
        ======
        - dict: Standardized success or failure result
        """
        try:
            return self._ok(**action())
        except Exception as exc:
            return self._fail(exc, **kwargs)

    def list_instances(
        self,
        daemon_id: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
        instance_name: Optional[str] = None,
        status: Optional[str] = None,
    ):
        """
        Purpose
        ======
        Fetch the instance list under a specific daemon.

        Input
        ======
        - daemon_id: Daemon ID, falling back to the controller default
        - page: Page number
        - page_size: Number of items per page
        - instance_name: Optional fuzzy filter by instance name
        - status: Optional status filter

        Return
        ======
        - dict: Includes ok, daemon_id, data, raw, and related fields
        """
        def action():
            resolved_daemon_id = daemon_id or self.daemon_id
            if not resolved_daemon_id:
                raise ValueError("daemon_id is required")
            data = self._request(
                "GET",
                "/api/service/remote_service_instances",
                query={
                    "daemonId": resolved_daemon_id,
                    "page": page,
                    "page_size": page_size,
                    "instance_name": instance_name,
                    "status": status,
                },
            )
            return {
                "daemon_id": resolved_daemon_id,
                "data": data.get("data", data),
                "raw": data,
            }

        return self._run(action, daemon_id=daemon_id)

    def get_instance(self, daemon_id=None, instance_uuid=None):
        """
        Purpose
        ======
        Fetch detailed information for one instance.

        Input
        ======
        - daemon_id: Daemon ID
        - instance_uuid: Instance UUID

        Return
        ======
        - dict: Includes the instance details and raw response data
        """
        def action():
            resolved_daemon_id, resolved_instance_uuid = self._resolve_instance(daemon_id, instance_uuid)
            data = self._request(
                "GET",
                "/api/instance",
                query={
                    "daemonId": resolved_daemon_id,
                    "uuid": resolved_instance_uuid,
                },
            )
            return {
                "daemon_id": resolved_daemon_id,
                "instance_uuid": resolved_instance_uuid,
                "data": data.get("data", data),
                "raw": data,
            }

        return self._run(action, daemon_id=daemon_id, instance_uuid=instance_uuid)

    def create_instance(self, daemon_id: str, config: Dict[str, Any]):
        """
        Purpose
        ======
        Create an instance on the specified daemon.

        Input
        ======
        - daemon_id: Daemon ID
        - config: Instance configuration dictionary

        Return
        ======
        - dict: Creation result and raw response data
        """
        def action():
            data = self._request(
                "POST",
                "/api/instance",
                query={"daemonId": daemon_id},
                body=config,
            )
            return {
                "daemon_id": daemon_id,
                "data": data.get("data", data),
                "raw": data,
            }

        return self._run(action, daemon_id=daemon_id)

    def update_instance(self, config: Dict[str, Any], daemon_id=None, instance_uuid=None):
        """
        Purpose
        ======
        Update the configuration of the specified instance.

        Input
        ======
        - config: Instance configuration to submit
        - daemon_id: Daemon ID
        - instance_uuid: Instance UUID

        Return
        ======
        - dict: Update result and raw response data
        """
        def action():
            resolved_daemon_id, resolved_instance_uuid = self._resolve_instance(daemon_id, instance_uuid)
            data = self._request(
                "PUT",
                "/api/instance",
                query={
                    "daemonId": resolved_daemon_id,
                    "uuid": resolved_instance_uuid,
                },
                body=config,
            )
            return {
                "daemon_id": resolved_daemon_id,
                "instance_uuid": resolved_instance_uuid,
                "data": data.get("data", data),
                "raw": data,
            }

        return self._run(action, daemon_id=daemon_id, instance_uuid=instance_uuid)

    def delete_instances(self, daemon_id: str, instance_uuids: Iterable[str], delete_file: bool = False):
        """
        Purpose
        ======
        Delete one or more instances.

        Input
        ======
        - daemon_id: Daemon ID
        - instance_uuids: Iterable of instance UUIDs
        - delete_file: Whether to delete instance files together with the instances

        Return
        ======
        - dict: Deletion result and raw response data
        """
        uuids = list(instance_uuids)

        def action():
            data = self._request(
                "DELETE",
                "/api/instance",
                query={"daemonId": daemon_id},
                body={
                    "uuids": uuids,
                    "deleteFile": bool(delete_file),
                },
            )
            return {
                "daemon_id": daemon_id,
                "instance_uuids": uuids,
                "data": data.get("data", data),
                "raw": data,
            }

        return self._run(action, daemon_id=daemon_id, instance_uuids=uuids)

    def _instance_operation(self, path: str, method="GET", body=None, daemon_id=None, instance_uuid=None, extra_query=None):
        """
        Purpose
        ======
        Execute a generic instance-level API operation such as start, stop,
        restart, or send command.

        Input
        ======
        - path: API path
        - method: HTTP method
        - body: JSON request body
        - daemon_id: Daemon ID
        - instance_uuid: Instance UUID
        - extra_query: Additional query parameters

        Return
        ======
        - dict: Instance operation result and raw response data
        """
        resolved_daemon_id, resolved_instance_uuid = self._resolve_instance(daemon_id, instance_uuid)
        query = {
            "daemonId": resolved_daemon_id,
            "uuid": resolved_instance_uuid,
        }
        if extra_query:
            query.update(extra_query)

        data = self._request(
            method,
            path,
            query=query,
            body=body,
        )
        return {
            "daemon_id": resolved_daemon_id,
            "instance_uuid": resolved_instance_uuid,
            "data": data.get("data", data),
            "raw": data,
        }

    def start(self, daemon_id=None, instance_uuid=None):
        """
        Purpose
        ======
        Start the specified instance.

        Input
        ======
        - daemon_id: Daemon ID
        - instance_uuid: Instance UUID

        Return
        ======
        - dict: Start result
        """
        return self._run(
            lambda: self._instance_operation("/api/protected_instance/open", daemon_id=daemon_id, instance_uuid=instance_uuid),
            daemon_id=daemon_id,
            instance_uuid=instance_uuid,
        )

    def stop(self, daemon_id=None, instance_uuid=None):
        """
        Purpose
        ======
        Stop the specified instance.

        Input
        ======
        - daemon_id: Daemon ID
        - instance_uuid: Instance UUID

        Return
        ======
        - dict: Stop result
        """
        return self._run(
            lambda: self._instance_operation("/api/protected_instance/stop", daemon_id=daemon_id, instance_uuid=instance_uuid),
            daemon_id=daemon_id,
            instance_uuid=instance_uuid,
        )

    def restart(self, daemon_id=None, instance_uuid=None):
        """
        Purpose
        ======
        Restart the specified instance.

        Input
        ======
        - daemon_id: Daemon ID
        - instance_uuid: Instance UUID

        Return
        ======
        - dict: Restart result
        """
        return self._run(
            lambda: self._instance_operation("/api/protected_instance/restart", daemon_id=daemon_id, instance_uuid=instance_uuid),
            daemon_id=daemon_id,
            instance_uuid=instance_uuid,
        )

    def kill(self, daemon_id=None, instance_uuid=None):
        """
        Purpose
        ======
        Force kill the specified instance.

        Input
        ======
        - daemon_id: Daemon ID
        - instance_uuid: Instance UUID

        Return
        ======
        - dict: Kill result
        """
        return self._run(
            lambda: self._instance_operation("/api/protected_instance/kill", daemon_id=daemon_id, instance_uuid=instance_uuid),
            daemon_id=daemon_id,
            instance_uuid=instance_uuid,
        )

    def update_task(self, daemon_id=None, instance_uuid=None):
        """
        Purpose
        ======
        Trigger the update task for the specified instance.

        Input
        ======
        - daemon_id: Daemon ID
        - instance_uuid: Instance UUID

        Return
        ======
        - dict: Update task trigger result
        """
        return self._run(
            lambda: self._instance_operation(
                "/api/protected_instance/asynchronous",
                method="POST",
                daemon_id=daemon_id,
                instance_uuid=instance_uuid,
                extra_query={"task_name": "update"},
            ),
            daemon_id=daemon_id,
            instance_uuid=instance_uuid,
        )

    def send_command(self, command: str, daemon_id=None, instance_uuid=None):
        """
        Purpose
        ======
        Send one command to the instance terminal.

        Input
        ======
        - command: Command text to send
        - daemon_id: Daemon ID
        - instance_uuid: Instance UUID

        Return
        ======
        - dict: Send result, including the command field
        """
        return self._run(
            lambda: self._instance_operation(
                "/api/protected_instance/command",
                extra_query={"command": command},
                daemon_id=daemon_id,
                instance_uuid=instance_uuid,
            )
            | {"command": command},
            daemon_id=daemon_id,
            instance_uuid=instance_uuid,
            command=command,
        )

    def get_output(self, size: int = 64, daemon_id=None, instance_uuid=None):
        """
        Purpose
        ======
        Fetch the latest chunk of terminal output for the instance.

        Input
        ======
        - size: Output length or count parameter used by the API
        - daemon_id: Daemon ID
        - instance_uuid: Instance UUID

        Return
        ======
        - dict: Includes output text and raw response data
        """
        def action():
            resolved_daemon_id, resolved_instance_uuid = self._resolve_instance(daemon_id, instance_uuid)
            data = self._request(
                "GET",
                "/api/protected_instance/outputlog",
                query={
                    "daemonId": resolved_daemon_id,
                    "uuid": resolved_instance_uuid,
                    "size": size,
                },
            )
            output_text = data.get("data", "")
            return {
                "daemon_id": resolved_daemon_id,
                "instance_uuid": resolved_instance_uuid,
                "output": output_text,
                "raw": data,
            }

        return self._run(action, daemon_id=daemon_id, instance_uuid=instance_uuid, size=size)

    def get_messages(self, size: int = 64, limit: Optional[int] = 100, since_id: Optional[int] = None, daemon_id=None, instance_uuid=None):
        """
        Purpose
        ======
        Convert instance output into a normalized message list for easier polling.

        Input
        ======
        - size: Underlying output fetch parameter
        - limit: Maximum number of messages to return
        - since_id: Only return messages with IDs greater than this value
        - daemon_id: Daemon ID
        - instance_uuid: Instance UUID

        Return
        ======
        - dict: Includes messages, next_since_id, running, and related fields
        """
        output_result = self.get_output(size=size, daemon_id=daemon_id, instance_uuid=instance_uuid)
        if not output_result.get("ok"):
            return output_result

        lines = [line for line in str(output_result.get("output", "")).splitlines() if line.strip()]
        messages = [
            {
                "id": index + 1,
                "time": datetime.now().isoformat(),
                "message": line,
                "source": "mcsm-output",
            }
            for index, line in enumerate(lines)
        ]

        if since_id is not None:
            messages = [item for item in messages if item["id"] > since_id]

        if limit is not None:
            messages = messages[-limit:]

        next_since_id = messages[-1]["id"] if messages else since_id

        return self._ok(
            daemon_id=output_result.get("daemon_id"),
            instance_uuid=output_result.get("instance_uuid"),
            running=self.status(daemon_id=daemon_id, instance_uuid=instance_uuid).get("running"),
            messages=messages,
            next_since_id=next_since_id,
            cached_count=len(lines),
            mode="mcsm-outputlog-snapshot",
        )

    def reinstall(self, target_url: str, title: str, description: str = "", daemon_id=None, instance_uuid=None):
        """
        Purpose
        ======
        Reinstall the instance from a target package or resource URL.

        Input
        ======
        - target_url: Package or resource URL
        - title: Install task title
        - description: Install task description
        - daemon_id: Daemon ID
        - instance_uuid: Instance UUID

        Return
        ======
        - dict: Reinstall task submission result
        """
        return self._run(
            lambda: self._instance_operation(
                "/api/protected_instance/install_instance",
                method="POST",
                body={
                    "targetUrl": target_url,
                    "title": title,
                    "description": description,
                },
                daemon_id=daemon_id,
                instance_uuid=instance_uuid,
            )
            | {
                "url": target_url,
                "title": title,
            },
            daemon_id=daemon_id,
            instance_uuid=instance_uuid,
        )

    def batch_operation(self, operation: str, instances: Iterable[Dict[str, str]]):
        """
        Purpose
        ======
        Execute a batch operation on multiple instances.

        Input
        ======
        - operation: Batch operation name such as start, stop, or restart
        - instances: Iterable of instance descriptors, usually containing daemonId and uuid

        Return
        ======
        - dict: Batch operation result
        """
        items = list(instances)

        def action():
            data = self._request(
                "POST",
                f"/api/instance/multi_{operation}",
                body=items,
            )
            return {
                "operation": operation,
                "instances": items,
                "data": data.get("data", data),
                "raw": data,
            }

        return self._run(action, operation=operation)

    def status(self, daemon_id=None, instance_uuid=None):
        """
        Purpose
        ======
        Fetch instance status and normalize it into a more convenient structure
        with running state, PID, and process metadata.

        Input
        ======
        - daemon_id: Daemon ID
        - instance_uuid: Instance UUID

        Return
        ======
        - dict: Includes running, status_code, pid, process_info, data, and related fields
        """
        instance_result = self.get_instance(daemon_id=daemon_id, instance_uuid=instance_uuid)
        if not instance_result.get("ok"):
            return instance_result

        data = instance_result.get("data", {})
        process_info = data.get("processInfo") or {}
        status_code = data.get("status")

        running = bool(
            process_info.get("running")
            or process_info.get("pid")
            or status_code == 3
        )

        return self._ok(
            daemon_id=instance_result.get("daemon_id"),
            instance_uuid=instance_result.get("instance_uuid"),
            running=running,
            status_code=status_code,
            pid=process_info.get("pid"),
            process_info=process_info,
            data=data,
        )


if __name__ == "__main__":
    example = MCSMController(
        base_url="http://127.0.0.1:23333",
        apikey="97737e20980b4554803c17d356ee0c92",
        daemon_id="da11c8667bfe447aa38da76af7f70b12",
        instance_uuid="7a8cfdd92f5f48aab58930eca5453dc9",
    )

    example.start()
    example.send_command("say Hello from MCSMController!")
    import time
    time.sleep(30)
    example.stop()
