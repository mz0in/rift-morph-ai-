import asyncio
from dataclasses import dataclass, field
import inspect
import logging
from pathlib import Path
import sys
from types import ModuleType
from typing import ClassVar, Literal, Optional, List
from miniscutil.lsp import LspServer as BaseLspServer, rpc_method
from miniscutil.lsp.document import setdoc
from miniscutil.rpc import AsyncStreamTransport, create_pipe_streams, invalid_request
import miniscutil.lsp.types as lsp
import importlib
import importlib.util
import urllib.parse
from rift.llm import OpenAIClient, Message
from rift.llm.abstract import (
    AbstractCodeCompletionProvider,
    AbstractChatCompletionProvider,
)
from rift.llm.create import ClientConfig
from rift.server.helper import *
from rift.server.selection import RangeSet
from rift.util.TextStream import TextStream
import rift.util.asyncgen as asg
from rift.llm.abstract import ChatMessage

logger = logging.getLogger(__name__)


@dataclass
class RunChatParams:
    message: str
    messages: List[ChatMessage]
    textDocument: lsp.TextDocumentIdentifier


ChatHelperLogs = HelperLogs


@dataclass
class HelperProgress:
    id: int
    textDocument: lsp.TextDocumentIdentifier
    status: Literal["running", "done", "error"]
    log: Optional[HelperLogs] = field(default=None)
    ranges: Optional[RangeSet] = field(default=None)
    cursor: Optional[lsp.Position] = field(default=None)


class ChatHelper:
    count: ClassVar[int] = 0
    id: int
    cfg: RunChatParams
    running: bool
    server: "LspServer"
    change_futures: dict[str, asyncio.Future[None]]
    cursor: lsp.Position
    task: Optional[asyncio.Task]
    """ The position of the cursor (where text will be inserted next). This position is changed if other edits occur above the cursor. """

    @property
    def uri(self):
        return self.cfg.textDocument.uri

    def __init__(self, cfg: RunChatParams, server: "LspServer"):
        ChatHelper.count += 1
        self.id = Helper.count
        self.cfg = cfg
        self.server = server
        self.running = False
        self.change_futures = {}
        # self.cursor = cfg.position
        self.document = server.documents[self.cfg.textDocument.uri]
        self.task = None
        self.subtasks = set()

    def cancel(self, msg):
        logger.info(f"cancel run: {msg}")
        if self.task is not None:
            self.task.cancel(msg)

    async def run(self):
        self.task = asyncio.create_task(self.worker())
        self.running = True
        try:
            return await self.task
        except asyncio.CancelledError as e:
            logger.info("run task got cancelled")
            return f"I stopped! {e}"
        finally:
            self.running = False

    async def send_progress(
        self,
        response: str = "",
        logs: Optional[ChatHelperLogs] = None,
        done: bool = False,
    ):
        await self.server.send_chat_helper_progress(
            self.id,
            response=response,
            log=logs,
            done=done,
            # textDocument=to_text_document_id(self.document),
            # cursor=self.cursor,
            # status="running" if self.running else "done",
        )

    async def worker(self):
        response = ""
        from asyncio import Lock

        response_lock = Lock()
        assert self.running
        async with response_lock:
            await self.send_progress(response)
        doc_text = self.document.text

        stream = await self.server.chat_client.run_chat(
            doc_text, self.cfg.messages, self.cfg.message
        )

        async for delta in stream.text:
            response += delta
            async with response_lock:
                await self.send_progress(response)
        logger.info("finished streaming response.")

        self.running = False
        async with response_lock:
            await self.send_progress(response, done=True)


@dataclass
class ChatHelperProgress:
    id: int
    response: str = ""
    log: Optional[HelperLogs] = field(default=None)
    done: bool = False


@dataclass
class RunHelperResult:
    id: int


@dataclass
class RunHelperSyncResult:
    id: int
    text: str


class LspServer(BaseLspServer):
    active_helpers: dict[int, Helper]
    active_chat_helpers: dict[int, asyncio.Task]
    client: Optional[AbstractCodeCompletionProvider] = None
    chat_client: Optional[AbstractChatCompletionProvider] = None

    def __init__(self, transport):
        super().__init__(transport)
        self.client_config = ClientConfig.default()
        self.chat_client_config = ClientConfig.default_chat()
        self.capabilities.textDocumentSync = lsp.TextDocumentSyncOptions(
            openClose=True,
            change=lsp.TextDocumentSyncKind.incremental,
        )
        self.active_helpers = {}
        self.active_chat_helpers = {}
        self._loading_task = None
        self._chat_loading_task = None        

    @rpc_method("morph/set_chat_client_config")
    async def on_set_chat_client_config(self, config: ClientConfig):
        """This is called whenever the user changes the model config settings.

        It should also be called immediately after initialisation."""
        if self._chat_loading_task is not None:
            idx = getattr(self, "_loading_idx", 0) + 1
            logger.debug(f"Queue of set_chat_client_config tasks: {idx}")
            self._loading_idx = idx
            self._chat_loading_task.cancel()
            # give user typing in config some time to settle down
            await asyncio.sleep(1)
            try:
                await self._chat_loading_task
            except (asyncio.CancelledError, TypeError):
                pass
            if self._loading_idx != idx:
                logger.debug(
                    f"loading task {idx} was cancelled, but a new one was started"
                )
                return
            # only the most recent request will make it here.
        if self.chat_client and self.chat_client_config == config:
            return
        self.chat_client_config = config
        logger.info("new chat client config, cancelling all helpers and reloading")
        for k, h in self.active_helpers.items():
            h.cancel("config changed")
        self.chat_client = config.create()
        self._chat_loading_task = asyncio.create_task(self.chat_client.load())
        try:
            await self._chat_loading_task
        except (asyncio.CancelledError, TypeError):
            logger.debug("loading cancelled")
        else:
            logger.info("finished loading")
        finally:
            self._chat_loading_task = None

    @rpc_method("morph/set_client_config")
    async def on_set_client_config(self, config: ClientConfig):
        """This is called whenever the user changes the model config settings.

        It should also be called immediately after initialisation."""
        if self._loading_task is not None:
            idx = getattr(self, "_loading_idx", 0) + 1
            logger.debug(f"Queue of set_client_config tasks: {idx}")
            self._loading_idx = idx
            self._loading_task.cancel()
            # give user typing in config some time to settle down
            await asyncio.sleep(1)
            try:
                await self._loading_task
            except (asyncio.CancelledError, TypeError):
                pass
            if self._loading_idx != idx:
                logger.debug(
                    f"loading task {idx} was cancelled, but a new one was started"
                )
                return
            # only the most recent request will make it here.
        if self.client and self.client_config == config:
            return
        self.client_config = config
        logger.info("new client config, cancelling all helpers and reloading")
        for k, h in self.active_helpers.items():
            h.cancel("config changed")
        self.client = config.create()
        self._loading_task = asyncio.create_task(self.client.load())
        try:
            await self._loading_task
        except asyncio.CancelledError:
            logger.debug("loading cancelled")
        else:
            logger.info("finished loading")
        finally:
            self._loading_task = None

    async def send_helper_progress(
        self,
        id: int,
        textDocument: lsp.TextDocumentIdentifier,
        log: Optional[HelperLogs] = None,
        cursor: Optional[lsp.Position] = None,
        ranges: Optional[RangeSet] = None,
        status: Literal["running", "done", "error"] = "running",
    ):
        progress = HelperProgress(
            id=id,
            textDocument=textDocument,
            log=log,
            cursor=cursor,
            status=status,
            ranges=ranges,
        )
        await self.notify("morph/progress", progress)

    async def send_chat_helper_progress(
        self,
        id: int,
        response: str,
        log: Optional[ChatHelperLogs] = None,
        done: bool = False,
        # textDocument: lsp.TextDocumentIdentifier,
        # log: Optional[HelperLogs] = None,
        # cursor: Optional[lsp.Position] = None,
        # status: Literal["running", "done", "error"] = "running",
    ):
        progress = ChatHelperProgress(
            # id=id, textDocument=textDocument, log=log, cursor=cursor, status=status
            id=id,
            response=response,
            log=log,
            done=done,
        )
        await self.notify("morph/chat_progress", progress)

    async def ensure_client(self):
        if self.client is None:
            logger.error(
                'morph/run_helper was called before "morph/set_client_config". Using the defualt model.'
            )
            await self.on_set_client_config(ClientConfig.default())
        assert self.client is not None
        return self.client

    async def ensure_chat_client(self):
        if self.chat_client is None:
            logger.error(
                'morph/run_helper was called before "morph/set_chat_client_config". Using the defualt model.'
            )
            await self.on_set_chat_client_config(ClientConfig.default_chat())
        assert self.chat_client is not None
        return self.chat_client

    @rpc_method("morph/run_helper")
    async def on_run_helper(self, params: RunHelperParams):
        client = await self.ensure_client()
        try:
            helper = Helper(params, client=client, server=self)
        except LookupError:
            # [hack] wait a bit for textDocumentChanged notification to come in
            logger.debug(
                "request too early: waiting for textDocumentChanged notification"
            )
            await asyncio.sleep(3)
            helper = Helper(params, client=client, server=self)
        logger.debug(f"starting helper {helper.id}")
        # helper holds a reference to worker task
        helper.start()
        self.active_helpers[helper.id] = helper
        return RunHelperResult(id=helper.id)

    @rpc_method("morph/run_helper_sync")
    async def on_run_helper_sync(self, params: RunHelperParams):
        print("running helper sync")
        if self.client is None:
            logger.error(
                'morph/run_helper_sync was called before "morph/set_client_config". Using the defualt model.'
            )
            await self.on_set_client_config(ClientConfig.default())
        try:
            assert self.client is not None
            helper = Helper(params, client=self.client, server=self)
        except LookupError:
            # [hack] wait a bit for textDocumentChanged notification to come in
            logger.debug(
                "request too early: waiting for textDocumentChanged notification"
            )
            await asyncio.sleep(3)
            assert self.client is not None
            helper = Helper(params, client=self.client, server=self)
        logger.debug(f"starting helper {helper.id}")
        # helper holds a reference to worker task
        # event = asyncio.Event()
        waiter_task = helper.start(blocking=True)
        # text = await helper.run_inline_completion()
        self.active_helpers[helper.id] = helper
        text = await waiter_task
        return RunHelperSyncResult(id=helper.id, text=text)

    @rpc_method("morph/run_chat")
    async def on_run_chat(self, params: RunChatParams):
        await self.ensure_chat_client()
        chat_helper = ChatHelper(params, server=self)
        logger.debug(f"starting chat helper {chat_helper.id}")
        task = asyncio.create_task(chat_helper.run())
        self.active_chat_helpers[chat_helper.id] = task

    @rpc_method("morph/cancel")
    async def on_cancel(self, params: HelperIdParams):
        helper = self.active_helpers.get(params.id)
        if helper is not None:
            helper.cancel()

    @rpc_method("morph/accept")
    async def on_accept(self, params: HelperIdParams):
        helper = self.active_helpers.get(params.id)
        if helper is not None:
            await helper.accept()
            self.active_helpers.pop(params.id, None)

    @rpc_method("morph/reject")
    async def on_reject(self, params: HelperIdParams):
        helper = self.active_helpers.get(params.id)
        if helper is not None:
            await helper.reject()
            self.active_helpers.pop(params.id, None)
        else:
            logger.error(f"no helper with id {params.id}")

    @rpc_method("hello_world")
    def on_hello(self, params):
        logger.debug("hello world")
        return "hello world"
