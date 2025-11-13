import re
import json
from enum import Enum, auto
from typing import Any, Dict, List, Set, Optional, Union


class Confidence(Enum):
    LOW = auto()
    MEDIUM = auto()
    HIGH = auto()


class TaintLabel(Enum):
    SENSITIVE = auto()
    COMMAND_INJECTION = auto()
    PATH_TRAVERSAL = auto()
    SQL_INJECTION = auto()
    CUSTOM = auto()


class TaintFinding:
    def __init__(
        self,
        field_path: str,
        label: TaintLabel,
        matched: str,
        confidence: Confidence = Confidence.MEDIUM,
    ):
        self.field_path = field_path
        self.label = label
        self.matched = matched
        self.confidence = confidence

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

    @property
    def high_confidence_findings(self) -> List[TaintFinding]:
        return [f for f in self.findings if f.confidence == Confidence.HIGH]

    @property
    def risk_score(self) -> int:
        """Calculate risk score based on findings"""
        score = 0
        for finding in self.findings:
            if finding.confidence == Confidence.HIGH:
                score += 10
            elif finding.confidence == Confidence.MEDIUM:
                score += 5
            elif finding.confidence == Confidence.LOW:
                score += 2
        return score

    def to_dict(self):
        return [f.to_dict() for f in self.findings]


class RuleType(Enum):
    REGEX = auto()
    EXACT = auto()
    FUNC = auto()


class TaintRule:
    """Generic taint-matching rule"""

    def __init__(
        self,
        label: TaintLabel,
        rule_type: RuleType,
        pattern: Union[str, re.Pattern, callable],
        field_match: Optional[str] = None,
        description: str = "",
        whitelist: Optional[Set[str]] = None,
        context_keys: Optional[Set[str]] = None,
        confidence: Confidence = Confidence.MEDIUM,
    ):
        self.label = label
        self.rule_type = rule_type
        self.pattern = pattern
        self.field_match = field_match  # If not None, only apply to these fields
        self.description = description
        self.whitelist = whitelist if whitelist is not None else set()
        self.context_keys = context_keys if context_keys is not None else set()
        self.confidence = confidence

    def match(
        self,
        value: Any,
        field_path: str,
        context: str = "",
    ) -> List[TaintFinding]:
        findings = []
        txt = str(value) if not isinstance(value, (dict, list)) else ""
        match_found = False
        matched_val = None

        if self.field_match and not field_path.endswith(self.field_match):
            return findings

        # Check whitelist
        for wl_item in self.whitelist:
            if re.search(wl_item, txt):
                return findings

        if self.rule_type == RuleType.EXACT and txt == self.pattern:
            match_found = True
            matched_val = txt

        elif self.rule_type == RuleType.REGEX:
            m = re.search(self.pattern, txt, re.IGNORECASE)
            if m:
                # Check context keys if specified
                if len(self.context_keys) > 0:
                    is_context_matched = any(
                        re.search(req, context, re.IGNORECASE)
                        for req in self.context_keys
                    )

                    if not is_context_matched:  # No context match
                        return findings

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
        self.rules: List[TaintRule] = (
            rules if rules is not None else self._default_rules()
        )

    def _default_rules(self) -> List[TaintRule]:
        """Enhanced rules with false positive reduction"""

        # SENSITIVE DATA PATTERNS
        sensitive_pat = (
            r"(password|passwd|pwd|secret|token|apikey|api[_-]?key|private[_-]?key|bearer|client[_-]?secret)[\"'=:]\s*[\w\-_.\/+]{8,}|"
            r"-----BEGIN (RSA|EC|OPENSSH|PGP|PRIVATE) KEY-----|"
            r"AKIA[0-9A-Z]{16}|"  # AWS keys
            r"AIza[0-9A-Za-z-_]{35}|"  # Google API keys
            r"ya29\.[0-9A-Za-z\-_]+|"  # Google OAuth tokens
            r"ghp_[0-9A-Za-z]{36}|"  # GitHub tokens
            r"sk-[0-9A-Za-z]{48}"  # OpenAI keys
        )

        # COMMAND INJECTION - More precise patterns
        cmd_inj_high_risk = (
            r"[;&|`]\s*(rm|cat|wget|curl|bash|sh|powershell|nc|netcat)\s"
        )

        cmd_inj_medium_risk = (
            r"\$\([^)]*\)|"  # Command substitution $(...)
            r"`[^`]+`|"  # Backtick substitution
            r"&&\s*(cat|rm|curl|wget|bash|sh|nc|chmod|chown)\s|"  # Chained commands
            r"\|\s*(grep|awk|sed|xargs|sh|bash)\s"  # Piped commands
        )

        # PATH TRAVERSAL
        pathtrav_pat = (
            r"\.\./\.\./|"  # Multiple directory traversal
            r"\.\./etc/|"  # Traversal to etc
            r"/etc/(passwd|shadow)|"
            r"\\.\\.\\.\\|"  # Windows traversal
            r"%2e%2e[/\\]|"  # URL encoded
            r"\.\.%2f"
        )

        # SQL INJECTION - More context-aware
        sqli_high_risk = (
            r"'\s*(or|and)\s+['\"]?\d+['\"]?\s*=\s*['\"]?\d+|"  # '1'='1'
            r"union\s+select\s+|"
            r"drop\s+table\s+|"
            r";\s*drop\s+|"
            r"exec\s*\(\s*|"
            r"xp_cmdshell"
        )

        sqli_medium_risk = (
            r"--\s*$|"  # SQL comment at end
            r"/\*.*\*/|"  # Block comments
            r"insert\s+into\s+|"
            r"delete\s+from\s+|"
            r"update\s+\w+\s+set"
        )

        # PII - with context
        email_pat = r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"

        # IP addresses - exclude common safe ones
        ip_addr_pat = r"\b(?:(?:2[0-4]\d|25[0-5]|1\d{2}|[1-9]?\d)\.){3}(?:2[0-4]\d|25[0-5]|1\d{2}|[1-9]?\d)\b"

        return [
            # SENSITIVE DATA
            TaintRule(
                TaintLabel.SENSITIVE,
                RuleType.REGEX,
                sensitive_pat,
                description="Sensitive credentials or keys detected",
                confidence=Confidence.HIGH,
                whitelist=[
                    r"password\s*=\s*\*+",  # Masked passwords
                    r"example\.com",  # Example domains
                    r"your[_-]?api[_-]?key",  # Placeholder text
                    r"<your-token>",
                ],
            ),
            # COMMAND INJECTION - HIGH RISK
            TaintRule(
                TaintLabel.COMMAND_INJECTION,
                RuleType.REGEX,
                cmd_inj_high_risk,
                description="High-risk command injection pattern",
                confidence=Confidence.HIGH,
                whitelist=[
                    r"description|comment|note|example",  # In documentation
                ],
            ),
            # COMMAND INJECTION - MEDIUM RISK
            TaintRule(
                TaintLabel.COMMAND_INJECTION,
                RuleType.REGEX,
                cmd_inj_medium_risk,
                description="Potential command injection",
                confidence=Confidence.MEDIUM,
                context_keys=["inject", "attack", "exploit", "malicious"],
                whitelist=[
                    r"npm\s+install|yarn\s+add",  # Package managers
                    r"git\s+commit|git\s+push",  # Git commands in docs
                ],
            ),
            # PATH TRAVERSAL
            TaintRule(
                TaintLabel.PATH_TRAVERSAL,
                RuleType.REGEX,
                pathtrav_pat,
                description="Path traversal attempt",
                confidence=Confidence.HIGH,
                whitelist=[
                    r"node_modules/\.\./",  # npm paths
                    r"relative.*path.*example",  # Documentation
                ],
            ),
            # SQL INJECTION - HIGH RISK
            TaintRule(
                TaintLabel.SQL_INJECTION,
                RuleType.REGEX,
                sqli_high_risk,
                description="High-risk SQL injection pattern",
                confidence=Confidence.HIGH,
            ),
            # SQL INJECTION - MEDIUM RISK
            TaintRule(
                TaintLabel.SQL_INJECTION,
                RuleType.REGEX,
                sqli_medium_risk,
                description="Potential SQL injection",
                confidence=Confidence.MEDIUM,
                whitelist=[
                    r"--\s*TODO|--\s*NOTE|--\s*FIXME",  # Code comments
                ],
                context_keys=["query", "sql", "database", "injection"],
            ),
            # PII - EMAIL
            TaintRule(
                TaintLabel.SENSITIVE,
                RuleType.REGEX,
                email_pat,
                description="Email address detected",
                confidence=Confidence.LOW,  # Emails are often public
                whitelist=[
                    r"example\.com|test\.com|localhost",
                    r"noreply@|no-reply@",
                    r"@example\.|@test\.",
                ],
            ),
            # IP ADDRESS
            TaintRule(
                TaintLabel.SENSITIVE,
                RuleType.REGEX,
                ip_addr_pat,
                description="IP address detected",
                confidence=Confidence.LOW,
                whitelist=[
                    r"127\.0\.0\.1|localhost",  # Loopback
                    r"0\.0\.0\.0",  # Wildcard
                    r"192\.168\.|10\.\d+\.|172\.(1[6-9]|2\d|3[01])\.",  # Private networks
                    r"255\.255\.255\.",  # Netmasks
                ],
            ),
        ]

    def evaluate(self, data: Any, context: Optional[Dict] = None) -> TaintResult:
        result = TaintResult()
        full_context = json.dumps(context or {})
        self._recursive_check(data, result, "", full_context)
        return result

    def _recursive_check(
        self, val: Any, result: TaintResult, field_path: str, context: Dict
    ):
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
