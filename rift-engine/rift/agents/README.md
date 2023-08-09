# Rift Agents

An *agent* is a stateful and asynchronous workflow that can *plan*, *request input*, *report progress*, *return results*, and *converse* with the user.

The Rift Code Engine exposes interfaces for code understanding, code transformations, and interactions with your coding agents through your IDE in a uniform, model- and language-agnostic way. The high-level interface is defined in [abstract.py](./abstract.py). This file contains the abstract base classes and data structures for defining and managing agents. It includes the `Agent` class which is the base class for all agents, `AgentParams` for agent parameters, `AgentState` for agent state, `AgentTask` for agent tasks, and `AgentRegistry` for managing all agents. It also provides the `agent` decorator for registering agents.

Rift ships with two basic agents: chat and code editing.

- `rift_chat.py`: This file defines the `RiftChatAgent` which is responsible for handling chat interactions with the user. It includes dataclasses for representing the result, progress, parameters, and state of the chat agent. The `RiftChatAgent` class includes methods for creating the agent, running the agent, getting user responses, generating responses, and sending progress updates.
- `code_edit.py`: This file defines the `CodeEditAgent` which is responsible for generating code edits for the currently selected region. It includes dataclasses for representing the result, progress, parameters, and state of the code completion agent. The `CodeEditAgent` class includes methods for creating the agent, running the agent, handling changes, sending results, accepting and rejecting edits.

Since agents can run arbitrary Python code, we have also integrated the following third-party open-source coding agents. These use mostly separate codepaths from Rift, but use the LSP interface exposed by the Rift Code Engine to interact with the users through the Rift VSCode extension.

- `smol.py`: This file defines the `SmolAgent` which is responsible for generating a workspace with smol_dev. It includes dataclasses for representing the result, progress, parameters, and state of the Smol agent. The `SmolAgent` class includes methods for creating the agent, running the agent, and sending progress updates.
- `engineer.py`: This file defines the `EngineerAgent` which is responsible for generating code based on user's instructions. It uses the GPT-3 model to understand the instructions and generate the corresponding code. The `EngineerAgent` class includes methods for creating the agent, running the agent, handling chat interactions, and sending progress updates.
- `aider_agent.py`: This file defines the `AiderAgent` which is responsible for generating codebase-wide edits through chat. It includes dataclasses for representing the result, progress, parameters, and state of the Aider agent. The `AiderAgent` class includes methods for creating the agent, running the agent, applying file changes, running the chat thread, and sending progress updates. It also includes several patches to the `aider` library to handle chat interactions and file changes.

Finally, we provide a toy / minimal implementation of an agent which just runs curl commands and renders the results in a loop.

- `curl_agent.py`: This file contains a reference toy implementation of the Agents API as defined in `abstract.py`. It defines the `CurlAgent` which asks the user for a URL and prints the output of CURLing that url. It includes dataclasses for representing the parameters and state of the Curl agent. The `CurlAgent` class includes methods for creating the agent, running the agent, and interacting with the user.
