"""
TODO
"""
import asyncio
import logging
import re
import time
from concurrent import futures
from dataclasses import dataclass, field
from typing import ClassVar, Optional, Type

logger = logging.getLogger(__name__)

import mentat.app
from mentat.app import get_user_feedback_on_changes, warn_user_wrong_files
from mentat.code_file_manager import CodeFileManager
from mentat.config_manager import ConfigManager
from mentat.conversation import Conversation
from mentat.llm_api import CostTracker
from mentat.user_input_manager import UserInputManager

import rift.agents.abstract as agent
import rift.llm.openai_types as openai
import rift.lsp.types as lsp
import rift.util.file_diff as file_diff
from rift.util.TextStream import TextStream


@dataclass
class MentatAgentParams(agent.AgentParams):
    ...


@dataclass
class MentatAgentState(agent.AgentState):
    params: MentatAgentParams
    messages: list[openai.Message]
    response_lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    _response_buffer: str = ""


@dataclass
class MentatRunResult(agent.AgentRunResult):
    ...


@agent.agent(agent_description="Request codebase-wide edits through chat", display_name="Mentat")
@dataclass
class Mentat(agent.Agent):
    agent_type: ClassVar[str] = "mentat"
    run_params: Type[MentatAgentParams] = MentatAgentParams
    state: Optional[MentatAgentState] = None

    @classmethod
    async def create(cls, params: MentatAgentParams, server):
        state = MentatAgentState(
            params=params,
            messages=[],
        )
        obj = cls(
            state=state,
            agent_id=params.agent_id,
            server=server,
        )
        return obj

    async def apply_file_changes(self, updates) -> lsp.ApplyWorkspaceEditResponse:
        return await self.server.apply_workspace_edit(
            lsp.ApplyWorkspaceEditParams(
                file_diff.edits_from_file_changes(
                    updates,
                    user_confirmation=True,
                )
            )
        )

    async def _run_chat_thread(self, response_stream):
        """
        Run the chat thread.
        :param response_stream: The stream of responses from the chat.
        """

        before, after = response_stream.split_once("感")
        try:
            async with self.state.response_lock:
                async for delta in before:
                    self.state._response_buffer += delta
                    await self.send_progress({"response": self.state._response_buffer})
            await asyncio.sleep(0.1)
            await self._run_chat_thread(after)
        except Exception as e:
            logger.info(f"[_run_chat_thread] caught exception={e}, exiting")

    async def run(self) -> MentatRunResult:
        response_stream = TextStream()

        run_chat_thread_task = asyncio.create_task(self._run_chat_thread(response_stream))

        loop = asyncio.get_running_loop()

        def send_chat_update_wrapper(prompt: str = "感", end="", eof=False, *args, **kwargs):
            def _worker():
                response_stream.feed_data(prompt)

            loop.call_soon_threadsafe(_worker)

        def request_chat_wrapper(prompt: Optional[str] = None):
            async def request_chat():
                response_stream.feed_data("感")
                await asyncio.sleep(0.1)
                await self.state.response_lock.acquire()
                await self.send_progress(dict(response=self._response_buffer, done_streaming=True))
                self.state.messages.append(openai.Message.assistant(content=self._response_buffer))
                self._response_buffer = ""
                if prompt is not None:
                    self.state.messages.append(openai.Message.assistant(content=prompt))

                resp = await self.request_chat(
                    agent.RequestChatRequest(messages=self.state.messages)
                )

                def refactor_uri_match(resp):
                    pattern = f"\[uri\]\({self.state.params.workspaceFolderPath}/(\S+)\)"
                    replacement = r"`\1`"
                    resp = re.sub(pattern, replacement, resp)
                    return resp

                try:
                    resp = refactor_uri_match(resp)
                except:
                    pass
                self.state.messages.append(openai.Message.user(content=resp))
                self.state.response_lock.release()
                return resp

            t = asyncio.run_coroutine_threadsafe(request_chat(), loop)
            futures.wait([t])
            result = t.result()
            return result

        ### PATCHES

        # in UserInputManager:
        # def collect_user_input(self) -> str:
        #     user_input = self.session.prompt().strip()
        #     logging.debug(f"User input:\n{user_input}")
        #     if user_input.lower() == "q":
        #         raise KeyboardInterrupt("User used 'q' to quit")
        #     return user_input

        # def ask_yes_no(self, default_yes: bool) -> bool:
        #     cprint("(Y/n)" if default_yes else "(y/N)")
        #     while (user_input := self.collect_user_input().lower()) not in [
        #         "y",
        #         "n",
        #         "",
        #     ]:
        #         cprint("(Y/n)" if default_yes else "(y/N)")
        #     return user_input == "y" or (user_input != "n" and default_yes)

        # in mentat.streaming_printer:
        # patch print

        # everywhere: cprint (output streaming)

        mentat.app.cprint = send_chat_update_wrapper

        # grab message history from mentat.conversation

        # code_file_manager.write_changes_to_files

        ###

        # Initialize necessary objects and variables
        config = ConfigManager()
        cost_tracker = CostTracker()
        conv = Conversation(config, cost_tracker)
        user_input_manager = UserInputManager(config)

        def compute_paths(resp):
            pattern = f"\[uri\]\((\S+)\)"
            replacement = r"`\1`"
            matches = re.match(pattern, replacement, matches)
            return matches

        paths = compute_paths()
        code_file_manager = CodeFileManager(paths, user_input_manager, config)

        need_user_request = True
        while True:
            if need_user_request:
                user_response = user_input_manager.collect_user_input()
                conv.add_user_message(user_response)
            explanation, code_changes = conv.get_model_response(code_file_manager, config)
            warn_user_wrong_files(code_file_manager, code_changes)

            if code_changes:
                need_user_request = get_user_feedback_on_changes(
                    config, conv, user_input_manager, code_file_manager, code_changes
                )
            else:
                need_user_request = True
