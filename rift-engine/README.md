# ️🤖⚙️ Rift Code Engine

The Rift Code Engine is an open-source AI-native [language server](https://microsoft.github.io/language-server-protocol/) for the development environments of the future. It will expose interfaces for code transformations and code understanding in a uniform, model- and language-agnostic way --- e.g. `rift.summarize_callsites` or `rift.launch_ai_swe_async` should work on a Python codebase with [StarCoder](https://huggingface.co/blog/starcoder) as well as it works on a Rust codebase using [CodeGen](https://github.com/salesforce/CodeGen). Within the language server, models will have full programatic access to language-specific tooling like compilers, unit and integration test frameworks, and static analyzers to produce correct code with minimal user intervention. We will develop UX idioms as needed to support this functionality in the Rift IDE extensions.

## Installation

- Set up a Python virtual environment for Python 3.10 or higher.
  - On Mac OSX:
    - Install [homebrew](https://brew.sh).
    - `brew install python@3.10`
    - `mkdir ~/.morph/ && cd ~/.morph/ && python3.10 -m venv env`
    - `source ./env/bin/activate/`
  - On Linux:
    - On Ubuntu:
      - `sudo apt install software-properties-common -y`
      - `sudo add-apt-repository ppa:deadsnakes/ppa`
      - `sudo apt install python3.10 && sudo apt install python3.10-venv`
      - `mkdir ~/.morph/ && cd ~/.morph/ && python3.10 -m venv env`
      - `source ./env/bin/activate/`
    - On Arch:
      - `yay -S python310`
      - `mkdir ~/.morph/ && cd ~/.morph/ && python3.10 -m venv env`
      - `source ./env/bin/activate/`
- Install Rift.
  - Make sure that `which pip` returns a path whose prefix matches the location of a virtual environment, such as the one installed above.
  - Using `pip` and PyPI:
    - `pip install --upgrade pyrift`
  - Using `pip` from GitHub:
    - `pip install "git+https://github.com/morph-labs/rift.git@ea0ee39bd86c331616bdaf3e8c02ed7c913b0933#egg=pyrift&subdirectory=rift-engine"`
  - From source:
    - `cd ~/.morph/ && git clone git@github.com:morph-labs/rift && cd ./rift/rift-engine/ && pip install -e .`

## Development

Use `conda` or `venv` to create and activate a Python virtual environment. Here are the detailed steps:

If you're using `pip install -e .conda`:
```bash
# Create a new conda environment
conda create --name myenv

# Activate the environment
conda activate myenv
```

If you're using `venv`:
```bash
# Create a new venv environment
python3 -m venv myenv

# Activate the environment
# On Windows, use:
myenv\Scripts\activate

# On Unix or MacOS, use:
source myenv/bin/activate
```

After activating the environment, install the package in editable mode:
```bash
pip install -e .
```

## Running

Run the server with `python -m rift.server.core --port 7797`. This will listen for LSP connections on port 7797.

The following command will reload the server every time a source code change is detected.

```bash
# pip install watchdog if not already installed
watchmedo shell-command \
    --patterns="*.py;*.txt" \
    --recursive \
    --command='python -m rift.server.core --port 7797 --debug True'  
```

## Agents

The Rift Agents API is the entry point for third-party contributors who want to contribute workflows that can be accessed through the Rift UI in the [VSCode extension](../editors/rift-vscode). See [here for an overview](./rift/agents/README.md).

## Contributing
[Fork](https://docs.github.com/en/get-started/quickstart/contributing-to-projects) this repository and make a pull request.
