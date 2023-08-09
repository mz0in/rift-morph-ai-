import asyncio
import dataclasses
import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any, AsyncIterable, ClassVar, Dict, List, Literal, Optional, Type

import rift.util.file_diff as file_diff

logger = logging.getLogger(__name__)
from rift.agents.cli.agent import Agent, ClientParams, launcher
from rift.agents.cli.util import ainput

try:
    import aider.main as aider
except ImportError:
    raise Exception(
        "`aider` not found. Try `pip install -e rift-engine[aider]` from the Rift root directory."
    )


@dataclass
class AiderAgentParams(ClientParams):
    args: List[str] = field(default_factory=list)
    debug: bool = False


@dataclass
class AiderAgent(Agent):
    name: ClassVar[str] = "aider"
    run_params: Type[AiderAgentParams] = AiderAgentParams
    splash: Optional[
        str
    ] = """
   __    ____  ____  ____  ____
  /__\  (_  _)(  _ \( ___)(  _ \\
 /(__)\  _)(_  )(_) ))__)  )   /
(__)(__)(____)(____/(____)(_)\_)

"""

    async def run(self) -> AsyncIterable[List[file_diff.FileChange]]:
        """
        Example use:
            python -m rift.agents.cli.aider --port 7797 --debug False --args '["--model", "gpt-3.5-turbo", "rift/agents/aider.py"]'
        """
        params = self.run_params

        logger.info(f"Aider: args: {params.args}")

        await ainput("\n> Press any key to continue.\n")

        logger.info("Running aider")

        file_changes: List[file_diff.FileChange] = []
        event = asyncio.Event()
        event2 = asyncio.Event()

        # This is called every time aider writes a file
        # Instead of writing, this stores the file change in a list
        def on_write(filename: str, new_content: str):
            file_changes.append(file_diff.get_file_change(path=filename, new_content=new_content))

        # This is called when aider wants to commit after writing all the files
        # This is where the user should accept/reject the changes
        loop = asyncio.get_running_loop()

        def on_commit():
            loop.call_soon_threadsafe(lambda: event.set())
            while True:
                if not event2.is_set():
                    time.sleep(0.25)
                    continue
                break
            input("> Press any key to continue.\n")

        from concurrent import futures

        with futures.ThreadPoolExecutor(1) as pool:
            aider_fut = asyncio.get_running_loop().run_in_executor(
                pool, aider.main, params.args, on_write, on_commit
            )

            while True:
                await event.wait()
                yield file_changes
                file_changes = []
                event2.set()
                event.clear()
            await aider_fut


if __name__ == "__main__":
    launcher(AiderAgent, AiderAgentParams)
