import argparse
import json
import os
from pathlib import Path
from typing import List, Optional

from agent_validation.data_processing.synthetic_generation.adk.paraphrase_config import (
    ParaphraseConfig,
)
from agent_validation.util.constants import WATSONX_AI_SERVICE_URL
from agent_validation.util.file_system import FileType, list_all_files
from agent_validation.util.logger import get_logger
from dotenv import dotenv_values
from ibm_watsonx_ai import Credentials
from ibm_watsonx_ai.foundation_models.inference import ModelInference
from ibm_watsonx_ai.metanames import GenTextParamsMetaNames as GenParams
from jinja2 import Environment, FileSystemLoader
from wxo_agentic_evaluation.type import ContentType, EvaluationData

logger = get_logger(__name__, verbose=False)


class ParaphraseGenerator:
    """Class to help generate different versions of paraphrases for user inputs in a validation test
    suite."""

    TOOL_FIELD_ORDER = ["name", "type", "tool_name", "args"]
    test_cases: list[EvaluationData]
    model: Optional[ModelInference] = None

    def __init__(self, config: ParaphraseConfig, env_file: str):
        """
        Sets up credentials and load test cases.

        Args:
            config: a ParaphraseConfig object containing parameters for the generator
        """
        self.config = config

        env = dotenv_values(env_file)
        watsonx_apikey = env.get("WATSONX_APIKEY", "")
        watsonx_space_id = env.get("WATSONX_SPACE_ID", "")
        if not watsonx_apikey or not watsonx_space_id:
            err_msg = f"Missing credentials in environment variable. Please ensure WATSONX_APIKEY and WATSONX_SPACE_ID are set"
            logger.error(err_msg)
            raise Exception(err_msg)

        self.credentials = Credentials(url=WATSONX_AI_SERVICE_URL, api_key=watsonx_apikey)
        self.watsonx_space_id = watsonx_space_id
        self.generate_params = (
            {GenParams.MAX_NEW_TOKENS: config.max_new_tokens} if config.max_new_tokens else {}
        )
        os.makedirs(self.config.output_dir, exist_ok=True)

        # load test cases
        self.test_cases: list[EvaluationData] = []
        self.test_files = list_all_files(config.test_paths, file_types=[FileType.JSON])
        logger.info(
            f"Loading test cases, there are total {len(self.test_files)} test cases to load."
        )
        for file in self.test_files:
            with open(file, "r") as f:
                self.test_cases.append(EvaluationData.model_validate(json.load(f)))

    def load_prompt(self, prompt_file: str, prompt_args: dict) -> str:
        """
        Load a prompt template from a file and substitute it with the provided arguments.

        Args:
            prompt_file: Path to the prompt template file
            prompt_args: Dictionary of key-value pairs used to fill in placeholders in the prompt.

        Returns:
            A string containing the fully rendered prompt with all substitutions applied.
        """
        template = Environment(loader=FileSystemLoader(".")).get_template(prompt_file)
        return template.render(**prompt_args)

    def batch_query(self, prompts: List[str], model_type: str) -> List[str]:
        """
        Send a list of prompts in a batch to the desired model.

        Args:
            prompts: A list of prompts to send
            model_type: the model to call

        Returns:
            A list of model responses
        """
        if self.model is None:
            self.model = ModelInference(
                model_id=model_type,
                params=self.generate_params,
                credentials=self.credentials,
                space_id=self.watsonx_space_id,
            )
        return self.model.generate_text(prompt=prompts)

    def _clean_model_reponse(self, text: str) -> List[str]:
        """
        Clean model responses and filter out extremely short sentences in the result.

        Args:
            text: model response

        Returns:
            Cleaned response as a list of sentences
        """
        sentences = text.strip("\n").strip().split("\n")
        # filter extremely short responses, as they are likely incorrectly formatted
        sentences = list(filter(lambda k: len(k) > 10, sentences))
        return sentences

    def paraphrase_test_cases(
        self,
    ) -> List[List[str]]:
        """
        Paraphrase starting sentence in the given test cases using a prompt template and a model.
        The function loads and creates a prompt from each test case, it then sends the list of
        prompts to the model.

        Returns:
            A list of paraphrased sentences for each test case.
        """

        # make prompts
        prompts = []
        prompt_args = {}
        for test_case in self.test_cases:
            prompt_args["num"] = self.config.paraphrase_count
            prompt_args["sentence"] = test_case.starting_sentence
            prompt = self.load_prompt(self.config.prompt_file, prompt_args=prompt_args)
            prompts.append(prompt)

        # send to model
        logger.info(f"Sending prompts to model {self.config.model}")
        results = self.batch_query(prompts, model_type=self.config.model)
        logger.debug(f"Results retrieved: {'\n'.join(results)}")
        return [self._clean_model_reponse(r) for r in results]

    def _dump_clean_test_case(self, test_case: EvaluationData, output_file: str | Path) -> None:
        """
        Dump test case and strip empty/unnecessary fields.

        Args:
            test_case: the test case object
            output_file: file path to save the test case
        """
        goal_details = []
        for goal in test_case.goal_details:
            data = goal.model_dump(
                exclude={"knowledge_base"},
                exclude_none=True,
            )
            # reorder field for readability
            if goal.type == ContentType.tool_call:
                data = {k: data[k] for k in self.TOOL_FIELD_ORDER if k in data}
            goal_details.append(data)

        content = test_case.model_dump()
        # replace goal details with custom dump
        content["goal_details"] = goal_details

        with open(output_file, "w") as f:
            json.dump(content, f, indent=2)

    def save_output(self, results: List[List[str]]) -> None:
        """
        Save the each generated paraphrased sentence to a new test case file.

        Args:
            results: paraphrased sentences generated for each test case
        """

        logger.info(f"Saving output to {self.config.output_dir}")
        for idx, test_file in enumerate(self.test_files):
            sentences = results[idx]
            test_name = Path(test_file).stem
            test_case = self.test_cases[idx]
            for j, sentence in enumerate(sentences):

                output_file = Path(self.config.output_dir) / f"{test_name}_paraphrase{j}.json"
                test_case.starting_sentence = sentence
                self._dump_clean_test_case(test_case, output_file)


def main() -> None:
    """The main of paraphrase generator CLI that can be a part of a test case generation
    pipepline."""
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--config_file",
        type=str,
        default="agent_validation/data_processing/synthetic_generation/adk/config/sample_config.yaml",
        help="Config file",
    )
    parser.add_argument(
        "--env_file",
        type=str,
        default="orders-team.env",
        help="Environment file.",
    )
    args = parser.parse_args()

    config = ParaphraseConfig.load(args.config_file)
    generator = ParaphraseGenerator(config, args.env_file)

    results = generator.paraphrase_test_cases()
    generator.save_output(results)


if __name__ == "__main__":
    main()
