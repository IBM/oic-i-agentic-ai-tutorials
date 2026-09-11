import typer

from .analyze import app as analyze_app
from .run import app as run_app

benchmarking_cli = typer.Typer(name="benchmark")
benchmarking_cli.add_typer(analyze_app, name="analyze", help="analyze benchmark results")
benchmarking_cli.add_typer(run_app, name="run", help="run benchmarking")

if __name__ == "__main__":
    benchmarking_cli()
