import json
import pathlib

from logger.taint_rule_engine import Confidence, TaintRuleEngine


def process_logs(
    log_path: pathlib.Path,
    min_confidence: Confidence = Confidence.MEDIUM,
    min_risk_score: int = 2,
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

    with open(log_path, "r", encoding="utf-8") as f:
        logs_str = f.read()

    logs = json.loads(logs_str)
    tool_calls = logs.get("tool_calls", [])
    tool_calls.sort(key=lambda x: x.get("timestamp", ""))

    print("=" * 80)
    print("SECURITY ANALYSIS OF TOOL CALLS")
    print(f"Filtering: confidence >= {min_confidence}, risk_score >= {min_risk_score}")
    print("=" * 80)

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

        print(f"\n{'='*80}")
        risk_indicator = "🚨 HIGH RISK" if is_high_risk else "⚠️  SUSPICIOUS"
        print(f"{risk_indicator} - TOOL CALL #{idx}")
        print(f"{'='*80}")
        print(f"Tool Name: {tool_call.get('tool_name')}")
        print(f"Timestamp: {tool_call.get('timestamp', 'N/A')}")
        print(f"Risk Score: {total_risk}")

        if taint_info:
            print("\nOriginal Taint Info:")
            print(f"  Input Tainted: {taint_info.get('input_tainted')}")
            print(f"  Output Tainted: {taint_info.get('output_tainted')}")
            print(f"  Taint Flow: {taint_info.get('taint_flow_detected')}")

        # INPUT ANALYSIS
        if input_findings:
            print(f"\n{'─'*80}")
            print(f"INPUT ANALYSIS ({len(input_findings)} findings):")
            print(f"{'─'*80}")

            # Group by label
            by_label = {}
            for finding in input_findings:
                label = finding.label.name
                if label not in by_label:
                    by_label[label] = []
                by_label[label].append(finding)

            for label, findings in by_label.items():
                print(f"\n  [{label}]")
                for finding in findings:
                    conf_icon = (
                        "🔴"
                        if finding.confidence == Confidence.HIGH
                        else "🟡" if finding.confidence == Confidence.MEDIUM else "🟢"
                    )
                    print(f"    {conf_icon} {finding.confidence}: {finding.field_path}")
                    print(f"       Matched: {finding.matched[:100]}")

            # Show relevant input snippet
            print("\n  Input Data Sample:")
            input_str = json.dumps(tool_input, indent=2)
            print(f"  {input_str[:500]}...")

        # OUTPUT ANALYSIS
        if output_findings:
            print(f"\n{'─'*80}")
            print(f"OUTPUT ANALYSIS ({len(output_findings)} findings):")
            print(f"{'─'*80}")

            by_label = {}
            for finding in output_findings:
                label = finding.label.name
                if label not in by_label:
                    by_label[label] = []
                by_label[label].append(finding)

            for label, findings in by_label.items():
                print(f"\n  [{label}]")
                for finding in findings:
                    conf_icon = (
                        "🔴"
                        if finding.confidence == "HIGH"
                        else "🟡" if finding.confidence == "MEDIUM" else "🟢"
                    )
                    print(f"    {conf_icon} {finding.confidence}: {finding.field_path}")
                    print(f"       Matched: {finding.matched[:100]}")

            # Show relevant output snippet
            print("\n  Output Data Sample:")
            output_str = str(output.get("result", output))
            print(f"  {output_str[:500]}...")

        print()

    print("=" * 80)
    print(f"SUMMARY: {high_risk_count} high-risk tool calls detected")
    print("=" * 80)


# Usage
if __name__ == "__main__":
    log_path = "logs/session_ec0c4e57-a8c9-4368-8146-f6016a12819a.json"
    process_logs(log_path, min_confidence=Confidence.MEDIUM, min_risk_score=2)
