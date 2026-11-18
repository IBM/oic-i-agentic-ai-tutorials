import sys
from pathlib import Path

# The AP engine (wxo/tools/apcore) is deployed to watsonx Orchestrate as part of the tool package;
# the workbench imports the same code for reviewer actions.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "wxo" / "tools"))
