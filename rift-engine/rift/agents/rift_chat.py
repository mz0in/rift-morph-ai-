import asyncio
import logging
from asyncio import Lock
from dataclasses import dataclass
from typing import Any, ClassVar, List, Optional

from tqdm import tqdm

import rift.agents.registry as registry
import rift.llm.openai_types as openai
import rift.lsp.types as lsp
from rift.agents.abstract import AgentProgress  # AgentTask,
from rift.agents.abstract import Agent, AgentParams, AgentRunResult, AgentState, RequestChatRequest
from rift.agents.agenttask import AgentTask
from rift.llm.abstract import AbstractChatCompletionProvider
from rift.lsp import LspServer as BaseLspServer
from rift.util.context import resolve_inline_uris

logger = logging.getLogger(__name__)


@dataclass
class ChatRunResult(AgentRunResult):
    ...


@dataclass
class RiftChatAgentParams(AgentParams):
    ...


@dataclass
class ChatProgress(
    AgentProgress
):  # reports what tasks are active and responsible for reporting new tasks
    response: Optional[str] = None
    done_streaming: bool = False


@dataclass
class RiftChatAgentState(AgentState):
    model: AbstractChatCompletionProvider
    messages: list[openai.Message]
    document: lsp.TextDocumentItem
    params: RiftChatAgentParams


@registry.agent(
    agent_description="Ask questions about your code.",
    display_name="Chat",
)
@dataclass
class RiftChatAgent(Agent):
    state: Optional[RiftChatAgentState] = None
    agent_type: ClassVar[str] = "rift_chat"
    params_cls: ClassVar[Any] = RiftChatAgentParams

    @classmethod
    async def create(cls, params: AgentParams, server: BaseLspServer):
        # logger.info(f"RiftChatAgent.create {params=}")
        model = await server.ensure_chat_model()
        if params.textDocument is None:
            document = None
        else:
            document = server.documents[params.textDocument.uri]
        state = RiftChatAgentState(
            model=model,
            messages=[openai.Message.assistant("Hello! How can I help you today?")],
            document=document,
            params=params,
        )
        obj = cls(
            state=state,
            agent_id=params.agent_id,
            server=server,
        )
        return obj

    async def run(self) -> AgentRunResult:
        response_lock = Lock()

        async def get_user_response() -> str:
            # logger.info(f"getting user response for {self.state.messages=}")
            result = await self.request_chat(RequestChatRequest(messages=self.state.messages))
            # logger.info(f"got response {result=}")
            return result

        async def generate_response(user_response: str):
            # logger.info(f"generating response for {user_response=}")
            response = ""
            documents: List[lsp.Document] = resolve_inline_uris(user_response, self.server)
            logger.info(f"resolved document uris {documents=}")

            doc_text = self.state.document.text if self.state.document is not None else ""

            logger.info("running chat")
            stream = await self.state.model.run_chat(
                doc_text,
                self.state.messages,
                user_response,
                cursor_offset=None,
                documents=documents,
            )
            async for delta in stream.text:
                response += delta
                # logger.info(f"{delta=}")
                async with response_lock:
                    await self.send_progress(ChatProgress(response=response))
            await self.send_progress(ChatProgress(response=response, done_streaming=True))
            logger.info(f"{self} finished streaming response.")
            return response

        async def generate_response_dummy():
            return True

        get_user_response_task = AgentTask("Get user response", get_user_response)
        old_generate_response_task = AgentTask("Generate response", generate_response_dummy)
        self.set_tasks([get_user_response_task, old_generate_response_task])
        await old_generate_response_task.run()
        while True:
            get_user_response_task = AgentTask("Get user response", get_user_response)
            # logger.info("created get_user_response_task")
            sentinel_f = asyncio.get_running_loop().create_future()

            async def generate_response_task_args():
                return [await sentinel_f]

            # logger.info("created future")
            generate_response_task = AgentTask(
                "Generate response", generate_response, args=generate_response_task_args
            )
            self.set_tasks([get_user_response_task, old_generate_response_task])
            await self.send_progress()
            user_response_task = asyncio.create_task(get_user_response_task.run())
            user_response_task.add_done_callback(lambda f: sentinel_f.set_result(f.result()))

            user_response = await user_response_task

            async with response_lock:
                self.state.messages.append(openai.Message.user(content=user_response))
            self.set_tasks([get_user_response_task, generate_response_task])
            await self.send_progress()
            assistant_response = await generate_response_task.run()
            await self.send_progress()
            async with response_lock:
                self.state.messages.append(openai.Message.assistant(content=assistant_response))

            old_generate_response_task = generate_response_task
            await self.send_progress()
