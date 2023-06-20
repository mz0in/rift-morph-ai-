import functools
import weakref
from pydantic import BaseModel, SecretStr
from typing import Literal, Optional

from rift.llm.abstract import AbstractCodeCompletionProvider


class ClientConfig(BaseModel):
    type: Literal["openai", "hf", "gpt4all"]
    name: Optional[str] = None
    path: Optional[str] = None
    """ For gpt4all models, the path to the model. """
    openai_api_key: Optional[SecretStr] = None

    def __hash__(self):
        return hash((self.type, self.name, self.path, str(self.openai_api_key)))

    def __eq__(self, other):
        return hash(self) == hash(other)

    def create(self) -> AbstractCodeCompletionProvider:
        return create_client(self)

    @classmethod
    def default(cls):
        return ClientConfig(type="gpt4all", name="ggml-replit-code-v1-3b")

    @classmethod
    def default_chat(cls):
        return ClientConfig(type="gpt4all", name="ggml-gpt4all-j-v1.3-groovy")


CLIENTS = weakref.WeakValueDictionary()


def create_client(config: ClientConfig) -> AbstractCodeCompletionProvider:
    """Create a client for the given config. If the client has already been created, then it will return a cached one.

    Note that it uses a WeakValueDictionary, so if the client is no longer referenced, it will be garbage collected.
    This is useful because it means you can call create_client multiple times without allocating the same model, but
    if you need to dispose a model this won't keep a reference that prevents it from being garbage collected.
    """
    global CLIENTS

    if config in CLIENTS:
        return CLIENTS[config]
    else:
        client = create_client_core(config)
        CLIENTS[config] = client
        return client


def create_client_core(config: ClientConfig) -> AbstractCodeCompletionProvider:
    if config.type == "hf":
        from rift.llm.hf_client import HuggingFaceClient

        return HuggingFaceClient(config.name)
    elif config.type == "openai":
        from rift.llm.openai_client import OpenAIClient

        kwargs = {}
        if config.name:
            kwargs["default_model"] = config.name
        if config.openai_api_key:
            kwargs["api_key"] = config.openai_api_key
        return OpenAIClient.parse_obj(kwargs)

    elif config.type == "gpt4all":
        from rift.llm.gpt4all_model import Gpt4AllSettings, Gpt4AllModel

        kwargs = {}
        if config.name:
            kwargs["model_name"] = config.name
        settings = Gpt4AllSettings.parse_obj(kwargs)
        return Gpt4AllModel(settings)

    else:
        raise ValueError(f"Unknown model type: {config.type}")
