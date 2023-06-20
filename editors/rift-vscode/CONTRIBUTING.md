# Rift VSCode Extension
VSCode extension for the [Rift Code Engine](../../rift-engine)

## Development
- For first-time setup, ensure that both this `node` project and the `rift` Python package have been installed.

```bash
npm i
pip install -e ../../rift-engine

# open this in VSCode
code .
# spin up the development server
python ../../rift-engine/rift/server/core.py --port 7797
```

- Start running an extension development host from inside VSCode by pressing `Ctrl + F5`.

- Once the extension window is running, open some code file. Access the chat interface by clicking on the sidebar icon. Trigger code completions in the editor window by running the `Rift: Code completion` command (`Ctrl + Shift + P`  +  type "Rift").

- Rift currently defaults to using the Replit `code-v1-3b` model through the `gpt4all` toolchain for code completions. The models used in the Rift Code Engine for handling extension requests are configurable through VSCode's settings user interface. Press `Ctrl + ,` and search for `Rift`.
