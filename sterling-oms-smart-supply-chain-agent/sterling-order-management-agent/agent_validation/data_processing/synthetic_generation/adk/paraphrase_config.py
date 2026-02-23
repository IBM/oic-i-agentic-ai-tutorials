from pathlib import Path
from typing import Union

from agent_validation.config.validation_config import load_yaml
from pydantic.dataclasses import dataclass

DEFAULT_PROMPT_FILE_FOR_PARAPHRASING = "agent_validation/data_processing/synthetic_generation/prompts/mistral_medium/paraphrase_default.txt"
DEFAULT_MODEL_FOR_PARAPHRASING = "mistralai/mistral-medium-2505"
DEFAULT_MAX_NEW_TOKENS = 5000


@dataclass
class ParaphraseConfig:
    """Config for paraphrase generator."""

    test_paths: list[str]
    output_dir: str
    paraphrase_count: int  # "the number of paraphrases"
    model: str = DEFAULT_MODEL_FOR_PARAPHRASING
    prompt_file: str = DEFAULT_PROMPT_FILE_FOR_PARAPHRASING
    max_new_tokens: int = DEFAULT_MAX_NEW_TOKENS

    @classmethod
    def load(cls, config_path: Union[Path, str]) -> "ParaphraseConfig":
        """
        Loads a ParaphraseConfig instance from a yaml file.

        Args:
            config_path: Path to the file.

        Returns:
            A deserialized ValidationConfig instance.
        """
        content = load_yaml(config_path)
        config = cls(**content)
        return config
