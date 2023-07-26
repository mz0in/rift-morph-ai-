# Rift Agents API

This directory contains implementations of various agents that can be interacted with through a CLI and which produce code diffs that can be sent to the Rift Code Engine.

https://github.com/morph-labs/rift/assets/122334950/a5fee985-5bba-4cad-84d6-c019e2eff887

## Files Overview

- `cli_agent.py`: This file contains the base class `Agent` for all agents. It also includes the `ClientParams` dataclass which serves as the base class for special parameters for instances of `Agent`.
- `smol.py`: This file contains an example implementation of a `Agent` subclass, `SmolAgent`.

## `cli_agent.py` Methods

- `Agent.run(self, *args, **kwargs) -> AsyncIterable[List[file_diff.FileChange]]`: This is an async generator which emits batches of file changes. It should be overridden by subclasses to provide the specific implementation.

- `get_dataclass_function(cls)`: This function returns a function whose signature is set to be a list of arguments which are precisely the dataclass's attributes.

- `main(agent_cls, params)`: This async function is the main entry point for running an agent. It starts the Rift server, displays the agent's splash screen, and runs the agent's `run` method.

- `launcher(agent_cls: Type[Agent], param_cls: Type[ClientParams])`: This function is used to launch an agent. It uses the Fire library to parse command line arguments into an instance of `param_cls`, and then runs the `main` function with `agent_cls` and the parsed parameters.

## Adding Your Own Agent

To add your own agent, you need to create a new file in this directory and subclass `Agent`. You can use `smol.py` as a reference implementation. Here are the general steps:

1. Define a new dataclass for your agent's parameters, subclassing `ClientParams`.
2. Define your agent class, subclassing `Agent`. Set `run_params` to your parameters dataclass.
3. Implement the `run` method. This method should be an async generator that yields batches of file changes.
4. At the end of your file, call `launcher` with your agent class and parameters dataclass.

## Running Your Own Agent
Use the `launcher` method defined in `cli_agent.py`. See `smol.py` for a reference implementation at the bottom of the file. Make sure the [Rift VSCode extension](../../../editors/rift-vscode/README.md) is installed and activated as well. Ensure that any other Rift server processes have been killed (this will no longer be necessary after we resolve [this issue](https://www.github.com/morph-labs/rift/issues/62).) Once configured, just run this from the VSCode terminal:

```python
# defined in ./my_agent.py
python -m rift.agents.my_agent --port 7797 --debug False # other agent-specific flags here...
```

## Caveats

- Please note that agents can run third-party code, do not use Rift's model abstractions, and are presently not configurable through the Rift extension settings in VSCode. Be careful when running agents with untrusted code.
- Currently each agent spins up its own Rift instance. Once support for [multiple clients](https://www.github.com/morph-labs/rift/issues/62) is added, multiple agents can interact with a single Rift server.

## Supported agents
- `smol-developer`:
```python
python -m rift.agents.smol --port 7797 --debug Faulse --prompt_file $PROMPT_FILE --model gpt-4-0613
```

- `gpt-engineer`:
```python
python -m rift.agents.gpt_eng --port 7797 --debug False --model gpt-4-0613
```

- `aider`:
```python
python -m rift.agents.aider
```

