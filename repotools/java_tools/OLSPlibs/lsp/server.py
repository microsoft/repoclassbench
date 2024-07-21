from typing import  Any, Dict, List, Optional, Union
import asyncio
import json
from .types import ErrorCodes
from .lsp_requests import LspRequest, LspNotification

StringDict = Dict[str, Any]
PayloadLike = Union[List[StringDict], StringDict, None]
CONTENT_LENGTH = 'Content-Length: '
ENCODING = "utf-8"


class Error(Exception):
    def __init__(self, code: ErrorCodes, message: str) -> None:
        super().__init__(message)
        self.code = code

    def to_lsp(self) -> StringDict:
        return {"code": self.code, "message": super().__str__()}

    @classmethod
    def from_lsp(cls, d: StringDict) -> 'Error':
        return Error(d["code"], d["message"])

    def __str__(self) -> str:
        return f"{super().__str__()} ({self.code})"


def make_response(request_id: Any, params: PayloadLike) -> StringDict:
    return {"jsonrpc": "2.0", "id": request_id, "result": params}


def make_error_response(request_id: Any, err: Error) -> StringDict:
    return {"jsonrpc": "2.0", "id": request_id, "error": err.to_lsp()}


def make_notification(method: str, params: PayloadLike) -> StringDict:
    return {"jsonrpc": "2.0", "method": method, "params": params}


def make_request(method: str, request_id: Any, params: PayloadLike) -> StringDict:
    return {"jsonrpc": "2.0", "method": method, "id": request_id, "params": params}


class StopLoopException(Exception):
    pass


def create_message(payload: PayloadLike) :
    body = json.dumps(
        payload,
        check_circular=False,
        ensure_ascii=False,
        separators=(",", ":")).encode(ENCODING)
    return (
        f"Content-Length: {len(body)}\r\n".encode(ENCODING),
        "Content-Type: application/vscode-jsonrpc; charset=utf-8\r\n\r\n".encode(ENCODING),
        body
    )


class MessageType:
    error = 1
    warning = 2
    info = 3
    log = 4


class Request():
    def __init__(self) -> None:
        self.cv = asyncio.Condition()
        self.result: Optional[PayloadLike] = None
        self.error: Optional[Error] = None

    async def on_result(self, params: PayloadLike) -> None:
        self.result = params
        async with self.cv:
            self.cv.notify()

    async def on_error(self, err: Error) -> None:
        self.error = err
        async with self.cv:
            self.cv.notify()


def content_length(line: bytes) -> Optional[int]:
    if line.startswith(b'Content-Length: '):
        _, value = line.split(b'Content-Length: ')
        value = value.strip()
        try:
            return int(value)
        except ValueError:
            raise ValueError("Invalid Content-Length header: {}".format(value))
    return None


class LanguageServer():
    def __init__(self, cmd: str, logger = None) -> None:
        self.send = LspRequest(self.send_request)
        self.notify = LspNotification(self.send_notification)

        self.cmd = cmd
        self.process = None
        self._received_shutdown = False

        self.request_id = 1
        self._response_handlers: Dict[Any, Request] = {}
        self.on_request_handlers = {}
        self.on_notification_handlers = {}
        self.logger = logger
        self.tasks = {}
        self.task_counter = 0
        self.loop = None

        self.notification_list = []
        self.condn_satisfied = asyncio.Event()
        self.condn = lambda x : True

    async def start(self):
        self.process = await asyncio.create_subprocess_shell(
            self.cmd,
            stdout=asyncio.subprocess.PIPE,
            stdin=asyncio.subprocess.PIPE,
        )
        self.loop = asyncio.get_event_loop()
        # print("Creating run_forever task for communicating with LS")
        # asyncio.run_coroutine_threadsafe(self.run_forever(), self.loop)
        self.tasks[self.task_counter] = self.loop.create_task(self.run_forever()) #asyncio.create_task(self.run_forever())
        self.task_counter += 1
        # print("Created task")
        return

    async def stop(self):
        if self.process:
            print("Send SIGTERM to LS")
            self.process.terminate()
            wait_for_end = self.process.wait()
            try:
                # wait for a task to complete
                print("Wait for LS to exit")
                await asyncio.wait_for(wait_for_end, timeout=60)
                print("LS exited")
            except asyncio.TimeoutError:
                print("Timeout waiting for LS to exit")
                print("Kill LS")
                self.process.kill()
                print("Killed LS")

    async def shutdown(self):
        await self.send.shutdown()
        self._received_shutdown = True
        self.notify.exit()
        if self.process and self.process.stdout:
            self.process.stdout.set_exception(StopLoopException())

    def _log(self, message: str) -> None:
        self.send_notification("window/logMessage",
                     {"type": MessageType.info, "message": message})

    async def run_forever(self) -> bool:
        try:
            while self.process and self.process.stdout and not self.process.stdout.at_eof():
                line = await self.process.stdout.readline()
                # print("body",line.decode())
                if not line:
                    continue
                try:
                    num_bytes = content_length(line)
                except ValueError:
                    continue
                if num_bytes is None:
                    continue
                while line and line.strip():
                    line = await self.process.stdout.readline()
                if not line:
                    continue
                body = await self.process.stdout.readexactly(num_bytes)
                self.tasks[self.task_counter] = asyncio.get_event_loop().create_task(self._handle_body(body))
                self.task_counter += 1
        except(BrokenPipeError, ConnectionResetError, StopLoopException):
            pass
        return self._received_shutdown

    async def _handle_body(self, body: bytes) -> None:
        try:
            await self._receive_payload(json.loads(body))
        except IOError as ex:
            self._log(f"malformed {ENCODING}: {ex}")
        except UnicodeDecodeError as ex:
            self._log(f"malformed {ENCODING}: {ex}")
        except json.JSONDecodeError as ex:
            self._log(f"malformed JSON: {ex}")

    async def _receive_payload(self, payload: StringDict) -> None:
        if self.logger:
            self.notification_list.append(payload)
            # print(payload)
            if self.condn(payload):
                self.condn_satisfied.set()
            self.logger("server", "client", payload)
        try:
            if "method" in payload:
                if "id" in payload:
                    await self._request_handler(payload)
                else:
                    await self._notification_handler(payload)
            elif "id" in payload:
                await self._response_handler(payload)
            else:
                self._log(f"Unknown payload type: {payload}")
        except Exception as err:
            self._log(f"Error handling server payload: {err}")

    def send_notification(self, method: str, params: Optional[dict] = None):
        self._send_payload_sync(
            make_notification(method, params))

    def send_response(self, request_id: Any, params: PayloadLike) -> None:
        self.tasks[self.task_counter] = asyncio.get_event_loop().create_task(self._send_payload(
            make_response(request_id, params)))
        self.task_counter += 1

    def send_error_response(self, request_id: Any, err: Error) -> None:
        self.tasks[self.task_counter] = asyncio.get_event_loop().create_task(self._send_payload(
            make_error_response(request_id, err)))
        self.task_counter += 1

    async def send_request(self, method: str, params: Optional[dict] = None):
        request = Request()
        request_id = self.request_id
        self.request_id += 1
        self._response_handlers[request_id] = request
        async with request.cv:
            await self._send_payload(make_request(method, request_id, params))
            await request.cv.wait()
        if isinstance(request.error, Error):
            print(request.error)
            raise request.error
        return request.result

    def _send_payload_sync(self, payload: StringDict) -> None:
        if not self.process or not self.process.stdin:
            return
        msg = create_message(payload)
        if self.logger:
            self.logger("client", "server", payload)
        self.process.stdin.writelines(msg)

    async def _send_payload(self, payload: StringDict) -> None:
        if not self.process or not self.process.stdin:
            return
        msg = create_message(payload)
        if self.logger:
            self.logger("client", "server", payload)
        self.process.stdin.writelines(msg)
        await self.process.stdin.drain()

    def on_request(self, method: str, cb):
        self.on_request_handlers[method] = cb

    def on_notification(self, method: str, cb):
        self.on_notification_handlers[method] = cb

    async def _response_handler(self, response: StringDict) -> None:
        request = self._response_handlers.pop(response["id"])
        if "result" in response and "error" not in response:
            await request.on_result(response["result"])
        elif "result" not in response and "error" in response:
            await request.on_error(Error.from_lsp(response["error"]))
        else:
            await request.on_error(Error(ErrorCodes.InvalidRequest, ''))

    async def _request_handler(self, response: StringDict) -> None:
        method = response.get("method", "")
        params = response.get("params")
        request_id = response.get("id")
        handler = self.on_request_handlers.get(method)
        if not handler:
            self.send_error_response(request_id, Error(
                    ErrorCodes.MethodNotFound, "method '{}' not handled on client.".format(method)))
            return
        try:
            self.send_response(request_id, await handler(params))
        except Error as ex:
            self.send_error_response(request_id, ex)
        except Exception as ex:
            self.send_error_response(request_id, Error(ErrorCodes.InternalError, str(ex)))

    async def _notification_handler(self, response: StringDict) -> None:
        method = response.get("method", "")
        params = response.get("params")
        handler = self.on_notification_handlers.get(method)
        if not handler:
            self._log(f"unhandled {method}")
            return
        try:
            await handler(params)
        except asyncio.CancelledError:
            return
        except Exception as ex:
            if not self._received_shutdown:
                self.send_notification("window/logMessage", {"type": MessageType.error, "message": str(ex), "method": method, "params": params})

