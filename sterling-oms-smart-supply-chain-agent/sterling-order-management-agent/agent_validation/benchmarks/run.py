import json
from pathlib import Path
import subprocess
from typing import Optional, Tuple

from agent_validation.benchmarks.versioning import lib
import typer
import yaml

OUTPUT_DIRECTORY = Path("agent_validation/benchmarks/results")
ADK_TEST_CASES_DIR = Path("agent_validation/adk_test_cases")
WXO_STOP_COMMAND = ["orchestrate", "server", "stop"]
RUNTIME_ERROR_MESSAGE = "No messages is produced. Exiting task."


def is_runtime_error(line: str, test_case_paths: list[str]) -> Tuple[bool, Optional[str]]:
    """
    Check if a log line contains a runtime error for any test case.

    Args:
        line: A single line of log output to check.
        test_case_paths: List of test case file paths to match against.

    Returns:
        Tuple of (is_error, matched_path) where is_error is True if runtime error
        detected and matched_path is the full path of the failing test case.
    """
    cleaned = line.lower().strip()
    if RUNTIME_ERROR_MESSAGE.lower() not in cleaned:
        return False, None

    for test_path in test_case_paths:
        basename = Path(test_path).name.lower()
        if basename in cleaned:
            return True, test_path

    return False, None


def wxo_start_command(env_file: Path) -> list[str]:
    """
    Build the command to start the WXO server.

    Args:
        env_file: Path to the environment file.

    Returns:
        List of command arguments for starting the server.
    """
    return ["orchestrate", "server", "start", f"--env-file={env_file}"]


def get_all_test_cases(test_cases_dir: Path) -> list[Path]:
    """
    Recursively find all JSON test case files in a directory.

    Args:
        test_cases_dir: Root directory to search for test cases.

    Returns:
        Sorted list of paths to JSON test case files (excluding hidden files).
    """
    return sorted(
        p for p in test_cases_dir.rglob("*.json") if p.is_file() and not p.name.startswith(".")
    )


def get_test_cases_from_config(config_path: Path) -> list[Path]:
    """
    Load test case paths from a YAML configuration file.

    Args:
        config_path: Path to the YAML config file containing test_paths.

    Returns:
        List of resolved test case file paths. Returns empty list on error.
    """
    try:
        with config_path.open("r") as f:
            config_data = yaml.safe_load(f) or {}

        test_paths: list[str] = config_data.get("test_paths") or []
        resolved: list[Path] = []

        for raw in test_paths:
            path = Path(raw)

            if path.is_file() and path.suffix == ".json":
                resolved.append(path)
            elif path.is_dir():
                resolved.extend(
                    p for p in path.rglob("*.json") if p.is_file() and not p.name.startswith(".")
                )
            else:
                typer.echo(f"Invalid path in config: '{path}'")

        return resolved

    except (FileNotFoundError, yaml.YAMLError, PermissionError) as e:
        typer.echo(f"Error reading config '{config_path}': {e}")
        return []


def run_command(command: list[str], timeout: Optional[int] = None) -> Tuple[bool, str]:
    """
    Execute a subprocess command and capture its output.

    Args:
        command: List of command arguments to execute.
        timeout: Optional timeout in seconds for the command.

    Returns:
        Tuple of (success, output) where success is True if command succeeded
        and output is the captured stdout/stderr.
    """
    typer.echo(f"Runing command: {' '.join(command)}")
    output_lines: list[str] = []

    try:
        proc = subprocess.Popen(
            command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8"
        )

        assert proc.stdout is not None
        for line in proc.stdout:
            output_lines.append(line)
            typer.echo(line.rstrip())

        proc.wait(timeout=timeout)

        success = proc.returncode == 0
        if not success:
            typer.echo(f"Command failed with exit code {proc.returncode}")

        return success, "".join(output_lines)

    except (subprocess.SubprocessError, OSError) as exc:
        typer.echo(f"Unexpected error running command: {exc}")
        return False, "".join(output_lines)


def parse_output_for_failures(output: str, test_case_paths: list[str]) -> list[str]:
    """
    Parse command output to identify failed test cases.

    Args:
        output: The captured command output to parse.
        test_case_paths: List of test case paths to check against.

    Returns:
        List of test case paths that failed with runtime errors.
    """
    failed: list[str] = []
    for line in output.splitlines():
        is_error, path = is_runtime_error(line, test_case_paths)
        if is_error and path:
            failed.append(path)
    return failed


def build_eval_command(
    env_file: Path,
    test_case_paths: list[str],
    benchmark_dir: lib.BenchmarkDirectory,
    config: Optional[Path],
) -> list[str]:
    """
    Build the orchestrate evaluations evaluate command.

    Args:
        env_file: Path to the environment file.
        test_case_paths: List of test case file paths to evaluate.
        benchmark_dir: Benchmark directory object for output.
        config: Optional path to config file.

    Returns:
        List of command arguments for running evaluations.
    """
    cmd = [
        "orchestrate",
        "evaluations",
        "evaluate",
        f"--output-dir={benchmark_dir.dir_path}",
        f"--env-file={env_file}",
        f"--test-paths={','.join(test_case_paths)}",
    ]
    if config:
        cmd.append(f"--config={config}")
    return cmd


def retry_failures(
    failed: list[str],
    env_file: Path,
    benchmark_dir: lib.BenchmarkDirectory,
    config: Optional[Path],
    retries: int,
) -> list[str]:
    """
    Retry failed test cases up to a specified number of times.

    Args:
        failed: List of test case paths that failed.
        env_file: Path to the environment file.
        benchmark_dir: Benchmark directory object for output.
        config: Optional path to config file.
        retries: Maximum number of retry attempts.

    Returns:
        List of test case paths that still failed after all retries.
    """
    remaining = failed[:]

    for attempt in range(1, retries + 1):
        if not remaining:
            break

        typer.echo(f"Retry attempt {attempt}/{retries} for {len(remaining)} failed tests")
        cmd = build_eval_command(env_file, remaining, benchmark_dir, config)
        _success, output = run_command(cmd)

        new_failures = parse_output_for_failures(output, remaining)
        remaining = new_failures

        typer.echo(f"{len(remaining)} tests still failing after attempt {attempt}")

    return remaining


def validate_test_case_paths(test_case_paths: list[Path]) -> None:
    """
    Validate that all test case file names are unique and they exist.

    Test cases file names are used as the dataset name row. If there is a collision, then
    evaluations will save only one instance of metrics data.

    If parsing from a config, the test paths have a loose link to the files themselves, confirm
    the files exists.

    Args:
        test_case_paths: List of test case paths.

    Raises:
        KeyError: If any key (test cases file names) are found.
    """

    valid_test_cases: dict[str, str] = {}
    test_case_name_collisions = []
    for test_case_path in test_case_paths:

        test_case_name = test_case_path.name  # Is this the file name or the full path name?
        if test_case_name in valid_test_cases:
            test_case_name_collisions.append(
                (str(test_case_path), str(valid_test_cases[test_case_name]))
            )
        valid_test_cases[test_case_name] = str(test_case_path)

    if test_case_name_collisions:
        err_msg = ""
        for test_case_path_collision, valid_test_case_path in test_case_name_collisions:
            err_msg += f"Name Collision: ({test_case_path_collision}, {valid_test_case_path})\n"

        raise KeyError(err_msg)


app = typer.Typer()


@app.command()
def main(
    env_file: Path = typer.Option(..., help="Path to .env file."),
    config: Optional[Path] = typer.Option(
        None, "--config", "-c", help="Path to benchmark config file."
    ),
    chunk: Optional[int] = typer.Option(
        None, "--chunk", help="Number of test cases to process per chunk."
    ),
    retries: int = typer.Option(
        0, "--retries", "-r", help="Retry failed test cases this many times."
    ),
) -> None:
    """
    Run benchmark evaluations and track failed test cases.

    Executes test cases either in chunks or all at once, captures runtime errors, and optionally
    retries failed tests. Results are saved to a versioned directory.
    """

    if not env_file.exists():
        typer.echo(f"Env file not found: {env_file}")
        raise typer.Exit(1)

    if config:
        cases = get_test_cases_from_config(config)
        if cases:
            typer.echo(f"Loaded {len(cases)} test cases from config.")
        else:
            typer.echo("No valid test paths in config. Using all ADK test cases.")
            cases = get_all_test_cases(ADK_TEST_CASES_DIR)
    else:
        cases = get_all_test_cases(ADK_TEST_CASES_DIR)

    validate_test_case_paths(cases)

    typer.echo(f"Total test cases: {len(cases)}")

    benchmark_dir = lib.BenchmarkDirectory.build(str(OUTPUT_DIRECTORY))
    all_failed_cases: list[str] = []
    all_case_paths = [str(p) for p in cases]

    start_cmd = wxo_start_command(env_file)
    use_chunks = chunk is not None and chunk > 0

    if use_chunks and chunk is not None:
        chunk_size: int = chunk
        total = len(cases)
        num_chunks = (total + chunk_size - 1) // chunk_size

        typer.echo(f"Processing {total} cases in {num_chunks} chunks of {chunk_size}.")

        for idx in range(0, total, chunk_size):
            subset = cases[idx : idx + chunk_size]
            subset_paths = [str(p) for p in subset]
            chunk_id = idx // chunk_size + 1

            typer.echo(f"Chunk {chunk_id}/{num_chunks}: {len(subset)} tests")

            cmd = build_eval_command(env_file, subset_paths, benchmark_dir, config)
            success, output = run_command(cmd)

            failures = parse_output_for_failures(output, all_case_paths)
            all_failed_cases.extend(failures)

            if not success:
                typer.echo(f"Chunk {chunk_id} failed. Aborting.")
                raise typer.Exit(1)

            run_command(WXO_STOP_COMMAND)
            run_command(start_cmd)

            typer.echo(f"Chunk {chunk_id} complete.")

    else:
        typer.echo("Running all test cases in one batch...")
        paths = [str(p) for p in cases]

        cmd = build_eval_command(env_file, paths, benchmark_dir, config)
        success, output = run_command(cmd)

        all_failed_cases.extend(parse_output_for_failures(output, paths))

        if not success:
            typer.echo("Evaluation failed.")
            raise typer.Exit(1)

    if retries > 0 and all_failed_cases:
        typer.echo(f"Retrying {len(all_failed_cases)} failing tests up to {retries} times")
        final_failures = retry_failures(all_failed_cases, env_file, benchmark_dir, config, retries)
    else:
        final_failures = all_failed_cases

    try:
        with open(benchmark_dir.metadata_path, "w") as f:
            json.dump(benchmark_dir.metadata.to_json(), f, indent=2)

        typer.echo(f"Metadata written: {benchmark_dir.metadata_path}")

        if final_failures:
            failed_yaml = benchmark_dir.dir_path / "failed_test_cases.yaml"
            with failed_yaml.open("w") as f:
                yaml.safe_dump({"failed_test_case_paths": final_failures}, f)

            typer.echo(f"Final failed test cases recorded in: {failed_yaml}")
        else:
            typer.echo("All tests passed after retries")

    except IOError as e:
        typer.echo(f"Error writing metadata: {e}")


if __name__ == "__main__":
    app()
