import re
from enum import Enum, auto
from typing import Any, Dict, List, Set, Optional, Tuple, Union

class TaintLabel(Enum):
    SENSITIVE = auto()
    COMMAND_INJECTION = auto()
    PATH_TRAVERSAL = auto()
    SQL_INJECTION = auto()
    CUSTOM = auto()

class TaintFinding:
    def __init__(self, field_path: str, label: TaintLabel, matched: str):
        self.field_path = field_path
        self.label = label
        self.matched = matched

    def to_dict(self):
        return {
            "field_path": self.field_path,
            "label": self.label.name,
            "matched": self.matched,
        }

class TaintResult:
    """TaintResult provides full details about why a data item is tainted"""
    def __init__(self):
        self.findings: List[TaintFinding] = []
    @property
    def tainted(self) -> bool:
        return len(self.findings) > 0
    @property
    def labels(self) -> Set[TaintLabel]:
        return {finding.label for finding in self.findings}
    def to_dict(self):
        return [f.to_dict() for f in self.findings]

class RuleType(Enum):
    REGEX = auto()
    EXACT = auto()
    FUNC = auto()

class TaintRule:
    """Generic taint-matching rule"""
    def __init__(self, label: TaintLabel, rule_type: RuleType, pattern: Union[str, re.Pattern, callable], field_match: Optional[str] = None, description: str = ""):
        self.label = label
        self.rule_type = rule_type
        self.pattern = pattern
        self.field_match = field_match  # If not None, only apply to these fields
        self.description = description

    def match(self, value: Any, field_path: str) -> List[TaintFinding]:
        findings = []
        txt = str(value) if not isinstance(value, (dict, list)) else ""
        match_found = False
        matched_val = None

        if self.field_match and not field_path.endswith(self.field_match):
            return findings

        if self.rule_type == RuleType.EXACT and txt == self.pattern:
            match_found = True
            matched_val = txt

        elif self.rule_type == RuleType.REGEX:
            m = re.search(self.pattern, txt)
            if m:
                match_found = True
                matched_val = m.group(0)

        elif self.rule_type == RuleType.FUNC and callable(self.pattern):
            result = self.pattern(value)
            if result:
                match_found = True
                matched_val = str(value)

        if match_found:
            findings.append(TaintFinding(field_path, self.label, matched_val))
        return findings

class TaintRuleEngine:

    def __init__(self, rules: Optional[List[TaintRule]] = None):
        self.rules: List[TaintRule] = rules if rules is not None else self._default_rules()

    def _default_rules(self) -> List[TaintRule]:
        # Regex patterns inspired by YARA, Pysa, industry sources[web:6][web:39][web:48]
        sensitive_pat = r"(password|passwd|pwd|secret|api[_-]?key|token|private[_-]?key|bearer|client[_-]?secret)[\"':=\s]+\S+|-----BEGIN [A-Z ]+PRIVATE KEY-----"
        cmd_inj_pat = r"\b(rm|cat|ls|wget|curl|exec|eval|system|bash|sh|powershell|cmd)\b"
        pathtrav_pat = r"\.\.(\/|\\|%2e)|/etc/passwd|/etc/shadow"
        sqli_pat = r"(?:'|\")?(?:\s*)(or|and)(?:\s+)?\d+\s*=\s*\d+|union\s+select|drop\s+table|--|/\*.*\*/"

        return [
            TaintRule(TaintLabel.SENSITIVE, RuleType.REGEX, sensitive_pat, description="Sensitive data leak"),
            TaintRule(TaintLabel.COMMAND_INJECTION, RuleType.REGEX, cmd_inj_pat, description="Command injection"),
            TaintRule(TaintLabel.PATH_TRAVERSAL, RuleType.REGEX, pathtrav_pat, description="Path traversal"),
            TaintRule(TaintLabel.SQL_INJECTION, RuleType.REGEX, sqli_pat, description="SQL Injection"),
        ]

    def evaluate(self, data: Any, context: Optional[Dict] = None) -> TaintResult:
        result = TaintResult()
        self._recursive_check(data, result, "", context or {})
        return result

    def _recursive_check(self, val: Any, result: TaintResult, field_path: str, context: Dict):
        # If dict, descend into keys
        if isinstance(val, dict):
            for k, v in val.items():
                next_field = f"{field_path}.{k}" if field_path else k
                self._recursive_check(v, result, next_field, context)
        # If list, descend into items
        elif isinstance(val, list):
            for idx, item in enumerate(val):
                next_field = f"{field_path}[{idx}]"
                self._recursive_check(item, result, next_field, context)
        # Otherwise, check rules for this value
        else:
            for rule in self.rules:
                for finding in rule.match(val, field_path):
                    result.findings.append(finding)
