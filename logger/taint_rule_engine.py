# logger/taint_rule_engine.py
import re
from enum import Enum, auto
from typing import List, Set, Dict, Any

class TaintLabel(Enum):
    SENSITIVE = auto()
    COMMAND_INJECTION = auto()
    PATH_TRAVERSAL = auto()
    SQL_INJECTION = auto()

class TaintResult:
    def __init__(self, tainted: bool, labels: Set[TaintLabel]):
        self.tainted = tainted
        self.labels = labels

def sensitive_pattern():
    # This should be extended for real-world use!
    return re.compile(
        r"(password|passwd|pwd|secret|api[_-]?key|token|private[_-]?key|bearer)[\"':=\s]+([^\s\"']+)|-----BEGIN [A-Z ]+PRIVATE KEY-----",
        re.IGNORECASE
    )

class TaintRuleEngine:
    def __init__(self):
        self.sensitive_regex = sensitive_pattern()

    def evaluate(self, data: Any) -> TaintResult:
        # Accept data as dict, str, or list
        text = data if isinstance(data, str) else str(data)
        labels = set()
        if self.sensitive_regex.search(text):
            labels.add(TaintLabel.SENSITIVE)
        # Add more rules as needed here (cmd injection, etc.)
        # For demo, only SENSITIVE is implemented.
        return TaintResult(tainted=bool(labels), labels=labels)
