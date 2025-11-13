import argparse
import json
import pathlib

from logger.taint_rule_engine import Confidence, TaintRuleEngine


def process_logs(
    log_path: pathlib.Path,
    min_confidence: Confidence = Confidence.MEDIUM,
    min_risk_score: int = 2,
    analysis_filepath: pathlib.Path | None = None,
):
    """
    Process logs and detect malicious patterns with configurable filtering

    Args:
        log_path: Path to the log file
        min_confidence: Minimum confidence level to report (LOW, MEDIUM, HIGH)
        min_risk_score: Minimum risk score to flag as high priority
    """
    min_conf_value = min_confidence.value

    engine = TaintRuleEngine()

    if analysis_filepath is None:
        analysis_filepath = log_path.with_name(f"analysis_{log_path.name}")

    with open(log_path, "r", encoding="utf-8") as f:
        logs_str = f.read()

    logs = json.loads(logs_str)
    tool_calls = logs.get("tool_calls", [])
    tool_calls.sort(key=lambda x: x.get("timestamp", ""))

    # Write analysis to file instead of printing to stdout
    out = open(analysis_filepath, "w", encoding="utf-8")
    out.write("=" * 80 + "\n")
    out.write("SECURITY ANALYSIS OF TOOL CALLS\n")
    out.write(
        f"Filtering: confidence >= {min_confidence}, risk_score >= {min_risk_score}\n"
    )
    out.write("=" * 80 + "\n")

    high_risk_count = 0

    for idx, tool_call in enumerate(tool_calls, 1):
        taint_info = tool_call.get("taint_info", {})

        # Analyze input
        tool_input = tool_call.get("input", {})
        input_result = engine.evaluate(
            tool_input, context={"tool": tool_call.get("tool_name")}
        )

        # Analyze output
        output = tool_call.get("output", {})
        output_result = engine.evaluate(
            output, context={"tool": tool_call.get("tool_name")}
        )

        # Filter by confidence
        input_findings = [
            f for f in input_result.findings if f.confidence.value >= min_conf_value
        ]
        output_findings = [
            f for f in output_result.findings if f.confidence.value >= min_conf_value
        ]

        if not input_findings and not output_findings:
            continue

        total_risk = input_result.risk_score + output_result.risk_score

        if total_risk < min_risk_score:
            continue

        is_high_risk = total_risk >= 20
        if is_high_risk:
            high_risk_count += 1

        out.write(f"\n{'='*80}\n")
        risk_indicator = "🚨 HIGH RISK" if is_high_risk else "⚠️  SUSPICIOUS"
        out.write(f"{risk_indicator} - TOOL CALL #{idx}\n")
        out.write(f"{'='*80}\n")
        out.write(f"Tool Name: {tool_call.get('tool_name')}\n")
        out.write(f"Timestamp: {tool_call.get('timestamp', 'N/A')}\n")
        out.write(f"Risk Score: {total_risk}\n")

        if taint_info:
            out.write("\nOriginal Taint Info:\n")
            out.write(f"  Input Tainted: {taint_info.get('input_tainted')}\n")
            out.write(f"  Output Tainted: {taint_info.get('output_tainted')}\n")
            out.write(f"  Taint Flow: {taint_info.get('taint_flow_detected')}\n")

        # INPUT ANALYSIS
        if input_findings:
            out.write(f"\n{'─'*80}\n")
            out.write(f"INPUT ANALYSIS ({len(input_findings)} findings):\n")
            out.write(f"{'─'*80}\n")

            # Group by label
            by_label = {}
            for finding in input_findings:
                label = finding.label.name
                if label not in by_label:
                    by_label[label] = []
                by_label[label].append(finding)

            for label, findings in by_label.items():
                out.write(f"\n  [{label}]\n")
                for finding in findings:
                    conf_icon = (
                        "🔴"
                        if finding.confidence == Confidence.HIGH
                        else "🟡" if finding.confidence == Confidence.MEDIUM else "🟢"
                    )
                    out.write(
                        f"    {conf_icon} {finding.confidence}: {finding.field_path}\n"
                    )
                    out.write(f"       Matched: {finding.matched[:100]}\n")

            # Show relevant input snippet
            out.write("\n  Input Data Sample:\n")
            input_str = json.dumps(tool_input, indent=2)
            out.write(f"  {input_str[:500]}...\n")

        # OUTPUT ANALYSIS
        if output_findings:
            out.write(f"\n{'─'*80}\n")
            out.write(f"OUTPUT ANALYSIS ({len(output_findings)} findings):\n")
            out.write(f"{'─'*80}\n")

            by_label = {}
            for finding in output_findings:
                label = finding.label.name
                if label not in by_label:
                    by_label[label] = []
                by_label[label].append(finding)

            for label, findings in by_label.items():
                out.write(f"\n  [{label}]\n")
                for finding in findings:
                    conf_icon = (
                        "🔴"
                        if finding.confidence == "HIGH"
                        else "🟡" if finding.confidence == "MEDIUM" else "🟢"
                    )
                    out.write(
                        f"    {conf_icon} {finding.confidence}: {finding.field_path}\n"
                    )
                    out.write(f"       Matched: {finding.matched[:100]}\n")

            # Show relevant output snippet
            out.write("\n  Output Data Sample:\n")
            output_str = str(output.get("result", output))
            out.write(f"  {output_str[:500]}...\n")

    out.write("\n")
    out.write("=" * 80 + "\n")
    out.write(f"SUMMARY: {high_risk_count} high-risk tool calls detected\n")
    out.write("=" * 80 + "\n")

    # Close the analysis file
    out.close()


# Usage
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run log processor for MCPClient.")
    parser.add_argument(
        "--id",
        nargs="+",
        default=None,
        help=("Run log processor for specified session by ID."),
    )
    args = parser.parse_args()
    log_path = pathlib.Path("logs") / f"session_{args.id[0]}.json"
    analysis_path = pathlib.Path("logs") / f"analysis_{args.id[0]}.txt"

    process_logs(
        log_path,
        min_confidence=Confidence.MEDIUM,
        min_risk_score=2,
        analysis_filepath=analysis_path,
    )
