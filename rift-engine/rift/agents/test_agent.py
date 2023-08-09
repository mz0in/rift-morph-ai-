"""
This module provides a minimal implementation of the Agent API defined in rift.agents.abstract.
"""
import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any, ClassVar, Optional

import rift.llm.openai_types as openai
from rift.agents.abstract import Agent, AgentParams, AgentState, RequestChatRequest
from rift.lsp.types import TextDocumentIdentifier

logger = logging.getLogger(__name__)


@dataclass
class TestAgentParams(AgentParams):
    textDocument: TextDocumentIdentifier
    instructionPrompt: Optional[str] = None


@dataclass
class TestAgentState(AgentState):
    params: TestAgentParams
    messages: list[openai.Message]


"""uncomment this to register the agent and access it from the Rift extension"""
# @agent(
#     agent_description="Test agent for testing purposes",
#     display_name="Test Agent"
# )


@dataclass
class TestAgent(Agent):
    """
    TestAgent is a minimal implementation of the Agent API.
    It is used for testing purposes.
    """

    state: Optional[TestAgentState] = None
    agent_type: str = "test_agent"
    params_cls: ClassVar[Any] = TestAgentParams
    response_lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    _response_buffer: str = ""

    async def run(self):
        # Send an initial update
        await self.send_update("test")

        # Run the chat thread
        await self._run_chat_thread(response_stream)

        # Initialize response_stream
        response_stream = ""

        # Enter a loop to continuously interact with the user
        while True:
            # Request a chat response from the user
            user_response_t = self.add_task(
                "get user response", self.request_chat, [RequestChatRequest(self.state.messages)]
            )

            # Send a progress update
            await self.send_progress()

            # Wait for the user's response
            user_response = await user_response_t.run()

            # Append the user's response to the state's messages
            self.state.messages.append(openai.Message.user(user_response))

            # Append a test response from the assistant to the state's messages
            self.state.messages.append(openai.Message.assistant("test"))

    async def _run_chat_thread(self, response_stream):
        """
        Run the chat thread.
        :param response_stream: The stream of responses from the chat.
        """

        before, after = response_stream.split_once("感")

        try:
            async with self.state.response_lock:
                async for delta in before:
                    self._response_buffer += delta
                    await self.send_progress({"response": self._response_buffer})

            await asyncio.sleep(0.1)

            await self._run_chat_thread(after)

        except Exception as e:
            logger.info(f"[_run_chat_thread] caught exception={e}, exiting")

    @classmethod
    async def create(cls, params: TestAgentParams, server):
        # Convert the parameters to a TestAgentParams object

        # Create the initial state
        state = TestAgentState(
            params=params,
            messages=[openai.Message.assistant("test")],
        )

        # Create the TestAgent object
        obj = cls(
            state=state,
            agent_id=params.agent_id,
            server=server,
        )

        # Return the TestAgent object
        return obj
