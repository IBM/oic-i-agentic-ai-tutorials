"""
Utility for calling tools from the command line.

Call command using pants and point to the config file.

```bash
pants run agent_ready_tools/utils/call_tools/call_tool.py \
  -- agent_ready_tools/utils/call_tools/call_tool_config.yaml
```

Config: contains the tool name and args to pass to the tool.

Example config:

```yaml
tool_name: get_user_successfactors_ids
tool_args:
 email: Saurabh.Singh36@ibm.com
 ```

Example output:

Running get_user_successfactors_ids with args {'email': 'Saurabh.Singh36@ibm.com'}...
Result: UserSuccessFactorsIDs(person_id_external='100173', user_id='100173',
username='ywilliams', name='Yvette Williams', message=None)
"""

import json
from pathlib import Path
from typing import Any, Dict

from import_utils.utils.tools_data_mapper import ToolsDataMap
from pydantic import BaseModel
import typer
import yaml

app = typer.Typer(help="CLI that loads a config and executes a function with arguments.")


class ToolCallConfig(BaseModel):
    """Config file for call_tool."""

    tool_name: str
    tool_args: dict


def load_config(path: Path) -> ToolCallConfig:
    """Load JSON or YAML config file into a dictionary."""
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")
    if path.suffix.lower() in [".yml", ".yaml"]:
        with path.open("r") as f:
            return ToolCallConfig(**yaml.safe_load(f))
    elif path.suffix.lower() == ".json":
        with path.open("r") as f:
            return ToolCallConfig(**json.load(f))
    else:
        raise ValueError("Unsupported config file format. Use .yaml, .yml, or .json")


@app.command()
def run(config: Path = typer.Argument(..., help="Path to config file")) -> None:
    """Run a function described in a config file and print result or error."""
    try:
        cfg = load_config(config)

        tool_name = cfg.tool_name

        tool = ToolsDataMap().get_tool_by_name(tool_name)
        if not tool:
            typer.echo(f"Tool '{tool_name}' not found.")
            raise typer.Exit(code=1)

        args: Dict[str, Any] = cfg.tool_args

        typer.echo(f"Running {tool_name} with args {args}...")

        result = tool.object.fn(**args)
        typer.echo(f"Result: {result}")

    except Exception as e:
        typer.echo(f"Error: {e}")
        raise typer.Exit(code=1)


if __name__ == "__main__":
    app()
