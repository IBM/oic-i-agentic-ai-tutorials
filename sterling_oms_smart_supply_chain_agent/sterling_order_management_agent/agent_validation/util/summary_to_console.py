from collections import defaultdict
import csv
from pathlib import Path
from typing import Any, List, Optional

from wxo_agentic_evaluation.metrics.metrics import TextMatchType, ToolCallAndRoutingMetrics
from wxo_agentic_evaluation.utils.utils import AgentMetricsTable, create_table, safe_divide

# TODO: Submit a PR request to split the console logging logic out of main and into a reusable func.


def _filter_display_only_values(
    tool_call_metric: ToolCallAndRoutingMetrics,
) -> dict[str, Any]:
    """
    Map metrics dataclass values to the display columns.

    Args:
        tool_call_metric (ToolCallAndRoutingMetrics): metric data

    Returns:
        dict[str, Any]: display column names to the values in the input dataclass.
    """
    row = {
        "Dataset": tool_call_metric.dataset_name,
        "Total Steps": tool_call_metric.total_steps,
        "LLM Steps": tool_call_metric.llm_step,
        "Total Tool Calls": tool_call_metric.total_tool_calls,
        "Tool Call Precision": tool_call_metric.tool_call_precision,
        "Tool Call Recall": tool_call_metric.tool_call_recall,
        "Agent Routing Accuracy": tool_call_metric.agent_routing_accuracy,
        "Text Match": tool_call_metric.text_match,
        "Journey Success": tool_call_metric.is_success,
        "Avg Resp Time (sec)": tool_call_metric.avg_resp_time,
    }
    return row


def _create_summary_row(metrics: List[dict]) -> dict[str, Any]:
    """
    Calculate the Averages for all rows and create a summary row.

    Args:
        metrics (List[dict]): list of metrics from filter_display_only_values

    Returns:
        dict[str, Any]: Summary row
    """
    avg_row = {
        "Dataset": "Summary (Average)",
        "Runs": 0,
        "Total Steps": 0,
        "LLM Steps": 0,
        "Total Tool Calls": 0,
        "Tool Call Precision": 0,
        "Tool Call Recall": 0,
        "Agent Routing Accuracy": 0,
        "Text Match": 0,
        "Journey Success": 0,
        "Avg Resp Time (sec)": 0,
    }
    if metrics:
        for row in metrics:
            avg_row["Runs"] += row.get("Runs", 0)
            avg_row["Total Steps"] += row["Total Steps"]
            avg_row["LLM Steps"] += row["LLM Steps"]
            avg_row["Total Tool Calls"] += row["Total Tool Calls"]
            avg_row["Tool Call Precision"] += row["Tool Call Precision"]
            avg_row["Tool Call Recall"] += row["Tool Call Recall"]
            avg_row["Agent Routing Accuracy"] += row["Agent Routing Accuracy"]
            avg_row["Text Match"] += row["Text Match"]
            avg_row["Journey Success"] += row["Journey Success"]
            avg_row["Avg Resp Time (sec)"] += row["Avg Resp Time (sec)"]

        n = len(metrics)
        # Average over datasets
        avg_row["Runs"] = round(safe_divide(avg_row["Runs"], n), 2)
        avg_row["Total Steps"] = round(safe_divide(avg_row["Total Steps"], n), 2)
        avg_row["LLM Steps"] = round(safe_divide(avg_row["LLM Steps"], n), 2)
        avg_row["Total Tool Calls"] = round(safe_divide(avg_row["Total Tool Calls"], n), 2)
        avg_row["Tool Call Precision"] = round(safe_divide(avg_row["Tool Call Precision"], n), 2)
        avg_row["Tool Call Recall"] = round(safe_divide(avg_row["Tool Call Recall"], n), 2)
        avg_row["Agent Routing Accuracy"] = round(
            safe_divide(avg_row["Agent Routing Accuracy"], n), 2
        )
        avg_row["Text Match"] = round(safe_divide(avg_row["Text Match"], n), 2)
        avg_row["Journey Success"] = round(safe_divide(avg_row["Journey Success"], n), 2)
        avg_row["Avg Resp Time (sec)"] = round(safe_divide(avg_row["Avg Resp Time (sec)"], n), 2)

    return avg_row


def _calculate_mean(vals: list[float]) -> Optional[float]:
    """
    Calculate the mean of a list of values.

    Args:
        vals (List[float]): list of values

    Returns:
        float: mean if vals is provided, else None
    """
    return round(sum(vals) / len(vals), 2) if vals else None


def _to_percentage(value: Optional[str], decimals: int = 0) -> str:
    """
    Convert a value to a percentage.

    Args:
        value (Optional[str]): value or None
        decimals (int): number of decimals to display

    Returns:
        str: percentage in string format or NA if value does not exist.
    """
    if value is None:
        return "NA"
    try:
        return f"{round(float(value) * 100, decimals)}%"
    except Exception:  # pylint: disable=broad-exception-caught
        return "NA"


def _build_evaluation_summary_table(
    tool_call_metrics: list[ToolCallAndRoutingMetrics],
) -> Optional[AgentMetricsTable]:
    """
    Build the summary table from the tool call metrics of an evaluation run and print to console.

    Duplicate code from wxo_agentic_evaluation.main module.
    Code is embedded in the main function so had to pull it out.

    Args:
        tool_call_metrics (list[ToolCallAndRoutingMetrics]): list of ToolCallAndRoutingMetrics

    Returns:
        AgentMetricsTable with data if data found, else None
    """

    if len(tool_call_metrics) > 0:
        # remove the average row if exist
        tool_call_metrics = [
            row for row in tool_call_metrics if row.dataset_name != "Summary (Average)"
        ]

        grouped = defaultdict(list)
        for m in tool_call_metrics:
            grouped[m.dataset_name].append(_filter_display_only_values(m))

        numeric_keys = [
            "Total Steps",
            "LLM Steps",
            "Total Tool Calls",
            "Tool Call Precision",
            "Tool Call Recall",
            "Agent Routing Accuracy",
            "Avg Resp Time (sec)",
        ]

        per_test_rows = []
        for ds, rows in grouped.items():
            out = {"Dataset": ds}
            # Average numeric columns over runs
            for k in numeric_keys:
                out[k] = _calculate_mean([r[k] for r in rows if isinstance(r.get(k), (int, float))])

            # Add total runs per dataset
            out["Runs"] = round(float(len(rows)), 2)

            # Journey Success -> numeric fraction in [0,1]
            js_vals = [1 if bool(r.get("Journey Success")) else 0 for r in rows]
            out["Journey Success"] = round(safe_divide(sum(js_vals), len(js_vals)), 2)

            # Text Match -> numeric fraction in [0,1]
            tm_hits = 0
            tm_den = len(rows)
            for r in rows:
                val = r.get("Text Match")
                if val == TextMatchType.text_match:
                    tm_hits += 1
            out["Text Match"] = round(safe_divide(tm_hits, tm_den), 2)

            per_test_rows.append(out)

        # Keep the old overall-avg logic: apply it over the per-test rows (each test counted once)
        overall_row = _create_summary_row(per_test_rows)
        tool_call_metrics_for_display = per_test_rows + [overall_row]

        column_order = [
            "Dataset",
            "Runs",
            "Total Steps",
            "LLM Steps",
            "Total Tool Calls",
            "Tool Call Precision",
            "Tool Call Recall",
            "Agent Routing Accuracy",
            "Text Match",
            "Journey Success",
            "Avg Resp Time (sec)",
        ]
        for row in tool_call_metrics_for_display:
            row["Text Match"] = _to_percentage(row.get("Text Match"), decimals=0)
            row["Journey Success"] = _to_percentage(row.get("Journey Success"), decimals=0)

        tool_call_metrics_for_display = [
            {col: row.get(col, "") for col in column_order} for row in tool_call_metrics_for_display
        ]
        tool_call_table_for_display = create_table(tool_call_metrics_for_display)

        return tool_call_table_for_display
    return None


def _csv_to_metrics(csv_path: Path) -> List[ToolCallAndRoutingMetrics]:
    """
    CSV to ToolCallAndRoutingMetrics list to build a table from.

    Args:
        csv_path: Path to the CSV file.

    Returns:
        ToolCallAndRoutingMetrics list for Table building.
    """
    csv_data = list(csv.DictReader(open(csv_path, "r")))
    metrics_list = [ToolCallAndRoutingMetrics(**row) for row in csv_data]
    return metrics_list


def summary_to_console(summary_csv: Path, missing_csv: Path) -> Optional[AgentMetricsTable]:
    """
    Take the summary and build a table to print to console.

    Args:
        summary_csv: Path to the summary csv file.
        missing_csv: Path to the missing datasets csv file.

    Returns:
        AgentMetricsTable with data if data found, else None
    """

    assert summary_csv.exists(), f"{summary_csv} does not exist"

    tool_call_metrics = _csv_to_metrics(summary_csv)
    if missing_csv.exists():
        tool_call_metrics.extend(_csv_to_metrics(missing_csv))
    tool_call_metrics.sort(key=lambda m: m.dataset_name)

    return _build_evaluation_summary_table(tool_call_metrics)
