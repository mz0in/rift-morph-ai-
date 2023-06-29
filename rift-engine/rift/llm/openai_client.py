from typing import List
import asyncio
from contextvars import ContextVar
from dataclasses import dataclass
from functools import cached_property, cache
import json
from typing import (
    Any,
    AsyncGenerator,
    Awaitable,
    Coroutine,
    Literal,
    Optional,
    Type,
    TypeVar,
    overload,
)
from urllib.parse import parse_qs, urlparse
import aiohttp
from pydantic import BaseModel, BaseSettings, SecretStr
from rift.llm.abstract import (
    AbstractCodeCompletionProvider,
    AbstractChatCompletionProvider,
    InsertCodeResult,
    ChatResult,
)

from rift.util.TextStream import TextStream
from rift.llm.abstract import ChatMessage
from rift.llm.openai_types import (
    ChatCompletionChunk,
    ChatCompletionRequest,
    ChatCompletionResponse,
    Message,
)
import rift.util.asyncgen as asg
import logging
from threading import Lock

logger = logging.getLogger(__name__)

I = TypeVar("I", bound=BaseModel)
O = TypeVar("O", bound=BaseModel)

from tiktoken import get_encoding

ENCODER = get_encoding("cl100k_base")
ENCODER_LOCK = Lock()

# Maximum size of the context to truncate around the cursor
MAX_CONTEXT_SIZE = 1000

@dataclass
class OpenAIError(Exception):
    """Error raised by calling the OpenAI API"""

    message: str
    status: int

    def __str__(self):
        return self.message


@cache
def get_num_tokens(content: str):
    return len(ENCODER.encode(content))


def message_length(msg: Message):
    with ENCODER_LOCK:
        return get_num_tokens(msg.content)


def truncate_messages(messages: List[Message]):
    tail_messages = []
    running_length = 0
    for msg in reversed(messages[1:]):
        running_length += message_length(msg)
        if running_length > 3584:
            break
        tail_messages.insert(0, msg)
    return [messages[0]] + tail_messages

def truncate_document(document: str, cursor: int, context_size: int) -> str:
    """
    Truncates the document around the cursor position to a specified context size.

    Args:
        document (str): The original document text.
        cursor (int): The position of the cursor within the document.
        context_size (int): The size of the context to truncate around the cursor.

    Returns:
        str: The truncated document text.

    """
    start = max(0, cursor - context_size)
    end = min(len(document), cursor + context_size)
    if start > 0 or end < len(document):
        logger.info(f"Truncating document from {len(document)} to {end - start}")
    return document[start:end]



class OpenAIClient(
    BaseSettings, AbstractCodeCompletionProvider, AbstractChatCompletionProvider
):
    api_key: SecretStr
    api_url: str = "https://api.openai.com/v1"
    default_model: Optional[str] = None

    class Config:
        env_prefix = "OPENAI_"
        env_file = ".env"
        keep_untouched = (cached_property,)

    def __str__(self):
        k = self.api_key.get_secret_value()
        k = f"{k[:3]}...{k[-4:]}"
        return f"{self.__class__.__name__} {self.api_url} {k}"

    @property
    def base_url(self) -> str:
        return (
            urlparse(self.api_url)
            ._replace(path="", query="", params="", fragment="")
            .geturl()
        )

    @property
    def url_path(self) -> str:
        return urlparse(self.api_url).path

    @property
    def url_query(self) -> dict:
        q = urlparse(self.api_url).query
        return parse_qs(q)

    @property
    def headers(self):
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key.get_secret_value()}",
            "User-Agent": __name__,
        }

    @cached_property
    def session(self) -> aiohttp.ClientSession:
        return aiohttp.ClientSession(
            base_url=self.base_url,
            headers=self.headers,
        )

    async def handle_error(self, resp: aiohttp.ClientResponse):
        status_code = resp.status
        message = await self.get_error_message(resp)
        message = f"{status_code} error from {self.base_url}: {message}"
        logging.error(message)
        raise OpenAIError(message=message, status=status_code)

    async def get_error_message(self, resp):
        if resp.content_type == "application/json":
            j = await resp.json()
        else:
            t = await resp.text()
            try:
                j = json.loads(t)
            except json.JSONDecodeError:
                return t
        if isinstance(j, str):
            return j
        for k in ["error", "message", "detail"]:
            if k in j:
                e = j[k]
                if isinstance(e, str):
                    return e
                if "message" in e:
                    m = e["message"]
                    if isinstance(m, str):
                        return m
        raise ValueError(f"Could not parse error message from {j}")

    def _make_path(self, endpoint: str) -> str:
        return self.url_path + endpoint

    async def _post_streaming(
        self,
        endpoint: str,
        params: I,
        input_type: Type[I],
        stream_data_type: Type[O],
    ) -> AsyncGenerator[O, None]:
        if not getattr(params, "stream", True):
            raise ValueError(
                "To not use streaming please use the _post_endpoint method"
            )
        if not isinstance(params, input_type):
            raise TypeError(f"expected {input_type}, got {type(params)}")
        payload = params.dict(exclude_none=True)
        payload["stream"] = True
        path = self._make_path(endpoint)
        async with self.session.post(path, params=self.url_query, json=payload) as resp:
            if not resp.ok:
                await self.handle_error(resp)
            while True:
                line = await resp.content.readline()
                if line == b"":
                    break
                if line == b"\n":
                    continue
                line = line.decode("utf-8")  # [todo] where to get encoding from?
                if line.startswith("data:"):
                    line = line.split("data:")[1]
                    line = line.strip()
                    if line == "[DONE]":
                        break
                    data = stream_data_type.parse_raw(line)
                    yield data
                else:
                    raise ValueError(f"unrecognised stream line: {line}")

    async def _post_endpoint(
        self,
        endpoint: str,
        params: I,
        input_type: Type[I],
        output_type: Type[O],
    ) -> O:
        if not isinstance(params, input_type):
            raise TypeError(f"expected {input_type}, got {type(params)}")
        if getattr(params, "stream", False):
            raise ValueError("To use streaming please use the _post_streaming method")
        payload = params.dict(exclude_none=True)
        path = self._make_path(endpoint)
        async with self.session.post(path, params=self.url_query, json=payload) as resp:
            if not resp.ok:
                await self.handle_error(resp)
            assert resp.content_type == "application/json"
            j = await resp.json()
        r = output_type.parse_obj(j)  # type: ignore
        return r  # type: ignore

    @overload
    def chat_completions(
        self, messages: list[Message], *, stream: Literal[True], **kwargs
    ) -> AsyncGenerator[ChatCompletionChunk, None]:
        ...

    @overload
    def chat_completions(
        self, messages: list[Message], *, stream: Literal[False], **kwargs
    ) -> Coroutine[Any, Any, ChatCompletionResponse]:
        ...

    def chat_completions(
        self, messages: list[Message], *, stream: bool = False, **kwargs
    ) -> Any:
        endpoint = "/chat/completions"
        input_type = ChatCompletionRequest
        # TODO: don't hardcode
        logit_bias = {99750: -100}  # forbid repetition of the cursor sentinel
        params = ChatCompletionRequest(
            messages=messages, stream=stream, logit_bias=logit_bias, **kwargs
        )
        if self.default_model:
            params.model = self.default_model
        output_type = ChatCompletionResponse

        if stream:
            return self._post_streaming(
                endpoint,
                params=params,
                input_type=input_type,
                stream_data_type=ChatCompletionChunk,
            )
        else:
            return self._post_endpoint(
                endpoint, params=params, input_type=input_type, output_type=output_type
            )

    async def run_chat(
        self, document: str, messages: List[Message], message: str, cursor_offset: Optional[int] = None
    ) -> ChatResult:
        chatstream = TextStream()

        if cursor_offset is not None:
            document = truncate_document(document, cursor_offset, MAX_CONTEXT_SIZE)

        messages = (
            [
                Message.system(
                    f"""
You are an expert software engineer and world-class systems architect with deep technical and design knowledge. Answer the user's questions about the code as helpfully as possible, quoting verbatim from the current file to support your claims.

Current file:
```
{document}
```

Answer the user's question."""
                )
            ]
            + [Message.mk(role=msg.role, content=msg.content) for msg in messages]
            + [Message.user(content=message)]
        )

        num_old_messages = len(messages)
        messages = truncate_messages(messages)
        logger.info(
            f"Truncated {num_old_messages - len(messages)} due to context length overflow."
        )

        stream = TextStream.from_aiter(
            asg.map(lambda c: c.text, self.chat_completions(messages, stream=True))
        )

        async def worker():
            try:
                async for delta in stream:
                    chatstream.feed_data(delta)
                chatstream.feed_eof()
            finally:
                chatstream.feed_eof()

        t = asyncio.create_task(worker())
        chatstream._feed_task = t
        logger.info("Created chat stream, awaiting results.")
        return ChatResult(text=chatstream)

    async def insert_code(
        self, document: str, cursor_offset: int, goal=None
    ) -> InsertCodeResult:
        CURSOR_SENTINEL = "感"
        doc_text_with_cursor = (
            document[:cursor_offset] + CURSOR_SENTINEL + document[cursor_offset:]
        )
        if goal is None:
            goal = f"""
            Generate code to be inserted at the cursor location, marked by {CURSOR_SENTINEL}.
            """

        messages = [
            Message.system(
                f"""You are an expert software engineer and world-class systems architect with deep technical and design knowledge.
                When presented with a task, first write a detailed and elegant plan to solve this task and then
                write code to do it surrounded by triple backticks.
                The code will be added verbatim to the cursor location, marked by {CURSOR_SENTINEL}.
                Add comments in the code to explain your reasoning."""
            ),
            Message.user(
                f"Here is the code:\n```\n{doc_text_with_cursor}\n```\n\nYour task is:\n{goal}\nInsert code at the {CURSOR_SENTINEL} which completes the task. The code will be added verbatim to the cursor location, marked by {CURSOR_SENTINEL}. Do not include code that is already there."
            ),
        ]

        stream = TextStream.from_aiter(
            asg.map(lambda c: c.text, self.chat_completions(messages, stream=True))
        )
        thoughts = TextStream()
        codestream = TextStream()

        async def worker():
            try:
                try:
                    prelude = await stream.readuntil("```")
                    logger.debug(f"prelude: {prelude}")
                    lang_tag = await stream.readuntil("\n")
                    if lang_tag:
                        logger.debug(f"lang_tag: {lang_tag}")
                except EOFError:
                    logger.error("never found a code block")
                    return
                before, after = stream.split_once("\n```")
                async for delta in before:
                    codestream.feed_data(delta)
                codestream.feed_eof()
                async for delta in after:
                    thoughts.feed_data("\n")
                    thoughts.feed_data(delta)
            finally:
                thoughts.feed_eof()
                codestream.feed_eof()

        t = asyncio.create_task(worker())
        thoughts._feed_task = t
        codestream._feed_task = t
        return InsertCodeResult(thoughts=thoughts, code=codestream)


async def _main():
    client = OpenAIClient()  # type: ignore
    print(client)
    messages = [
        Message.system("you are a friendly and witty chatbot."),
        Message.user("please tell me a joke involving a lemon and a rubiks cube."),
        Message.assistant("i won't unless if you ask nicely"),
    ]

    stream = await client.run_chat(
        "fee fi fo fum", messages=messages, message="pretty please?"
    )
    async for delta in stream.text:
        print(delta)
    # print("\n\n")
    # async for x in client.chat_completions(messages, stream=True):
    #     text = x.choices[0].delta.content or ""
    #     print(text, end="")

    # print("\n\n")


if __name__ == "__main__":
    asyncio.run(_main())
