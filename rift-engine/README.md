# ️🤖⚙️ Rift Code Engine

An AI-first language server for powering your personal, on-device AI software engineer. Built and maintained by [Morph](https://morph.so).

## Installation

For development:

```bash
# from this directory
pip install -e .
```

From PyPI:

```bash
pip install pyrift
```

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

## Contributing
[Fork](https://docs.github.com/en/get-started/quickstart/contributing-to-projects) this repository and make a pull request.


``
