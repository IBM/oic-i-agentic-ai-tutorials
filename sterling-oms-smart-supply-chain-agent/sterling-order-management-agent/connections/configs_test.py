from importlib import resources
from pathlib import Path

from connections import schema
from ibm_watsonx_orchestrate.agent_builder.connections.types import ConnectionEnvironment


def test_configs() -> None:  # noqa: ANN001
    """Tests parsing of defined connection config YAML files."""
    configs_path = resources.files(__name__).joinpath("configs")

    for cfg_dir in configs_path.iterdir():
        if not cfg_dir.is_dir():
            continue
        for file in cfg_dir.iterdir():
            if not file.name.endswith(".yaml"):
                continue
            print(file)
            assert isinstance(file, Path)
            cfg_objs = schema.parse_connection_yaml(
                file, (ConnectionEnvironment.DRAFT, ConnectionEnvironment.LIVE)
            )
            for cfg_obj in cfg_objs:
                assert isinstance(cfg_obj, schema.ExtendedConnectionConfiguration)
                cfg_type = cfg_obj.kind
                try:
                    assert isinstance(
                        cfg_obj.credentials, schema.CREDENTIALS_KIND_TO_CLASS[cfg_type]
                    )
                except KeyboardInterrupt:
                    raise ValueError(
                        f"Unsupported auth type {cfg_type} for connection config file: {file}"
                    )
