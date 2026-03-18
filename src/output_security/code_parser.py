"""
Parses LLM response text to extract code blocks and their dependencies.

Supports:
  - Python:     import X, from X import Y
  - JavaScript/TypeScript: require('X'), import ... from 'X'
  - Java:       import com.example.X
  - Go:         import "pkg"
  - Ruby:       require 'gem'
  - Shell:      pip install X, npm install X, apt-get install X
"""
import re
from dataclasses import dataclass


# Matches fenced markdown code blocks: ```lang\n...\n```
_CODE_BLOCK_RE = re.compile(r'```(\w*)\n(.*?)```', re.DOTALL)

# Per-language import extraction patterns.
# Each yields the package/module name as group(1).
_EXTRACTORS: dict[str, list[re.Pattern]] = {
    "python": [
        re.compile(r'^\s*import\s+([\w.]+)', re.MULTILINE),
        re.compile(r'^\s*from\s+([\w.]+)\s+import', re.MULTILINE),
        re.compile(r'pip\s+install\s+([\w\-]+)', re.MULTILINE),
    ],
    "javascript": [
        re.compile(r'require\([\'"]([^\'"\s./][^\'"\s]*)[\'"]'),
        re.compile(r'from\s+[\'"]([^\'"\s./][^\'"\s]*)[\'"]'),
        re.compile(r'npm\s+install\s+([\w\-@/]+)', re.MULTILINE),
    ],
    "typescript": [
        re.compile(r'require\([\'"]([^\'"\s./][^\'"\s]*)[\'"]'),
        re.compile(r'from\s+[\'"]([^\'"\s./][^\'"\s]*)[\'"]'),
    ],
    "java": [
        re.compile(r'^\s*import\s+([\w.]+);', re.MULTILINE),
    ],
    "go": [
        re.compile(r'^\s*"([^"]+)"', re.MULTILINE),  # inside import() block
    ],
    "ruby": [
        re.compile(r'require\s+[\'"]([^\'"]+)[\'"]'),
        re.compile(r'gem\s+[\'"]([^\'"]+)[\'"]'),
    ],
    "shell": [
        re.compile(r'pip\s+install\s+([\w\-]+)', re.MULTILINE),
        re.compile(r'npm\s+install\s+([\w\-@/]+)', re.MULTILINE),
        re.compile(r'apt(?:-get)?\s+install\s+([\w\-]+)', re.MULTILINE),
    ],
    "bash": [
        re.compile(r'pip\s+install\s+([\w\-]+)', re.MULTILINE),
        re.compile(r'npm\s+install\s+([\w\-@/]+)', re.MULTILINE),
        re.compile(r'apt(?:-get)?\s+install\s+([\w\-]+)', re.MULTILINE),
    ],
}

# Stdlib modules we never need to validate — not external dependencies.
_PYTHON_STDLIB = {
    "os", "sys", "re", "json", "math", "time", "datetime", "pathlib",
    "collections", "itertools", "functools", "typing", "dataclasses",
    "abc", "io", "string", "copy", "enum", "logging", "unittest",
    "threading", "multiprocessing", "subprocess", "socket", "ssl",
    "http", "urllib", "email", "html", "xml", "csv", "hashlib",
    "hmac", "secrets", "random", "struct", "base64", "uuid",
    "contextlib", "warnings", "traceback", "inspect", "ast",
    "argparse", "configparser", "tempfile", "shutil", "glob",
    "fnmatch", "gzip", "zipfile", "tarfile", "sqlite3", "pickle",
}

_JAVA_STDLIB_PREFIXES = {"java.", "javax.", "sun.", "com.sun."}
_GO_STDLIB_PREFIXES = {
    "fmt", "os", "io", "net", "http", "strings", "strconv",
    "errors", "sync", "context", "time", "math", "sort", "log",
    "path", "bufio", "bytes", "encoding", "unicode", "reflect",
    "runtime", "testing",
}


@dataclass(frozen=True)
class CodeBlock:
    language: str
    content: str
    dependencies: list[str]


def _is_stdlib(lang: str, package: str) -> bool:
    if lang == "python":
        root = package.split(".")[0]
        return root in _PYTHON_STDLIB
    if lang == "java":
        return any(package.startswith(p) for p in _JAVA_STDLIB_PREFIXES)
    if lang == "go":
        root = package.split("/")[0]
        return root in _GO_STDLIB_PREFIXES
    return False


def _extract_deps(lang: str, code: str) -> list[str]:
    patterns = _EXTRACTORS.get(lang, [])
    deps: set[str] = set()
    for pat in patterns:
        for match in pat.finditer(code):
            pkg = match.group(1).strip()
            if pkg and not _is_stdlib(lang, pkg):
                # Normalise: take the top-level package name only
                deps.add(pkg.split(".")[0])
    return sorted(deps)


def extract_code_blocks(text: str) -> list[CodeBlock]:
    """Return all fenced code blocks with their extracted external dependencies."""
    blocks = []
    for match in _CODE_BLOCK_RE.finditer(text):
        lang = (match.group(1) or "").lower().strip()
        code = match.group(2)
        deps = _extract_deps(lang, code)
        blocks.append(CodeBlock(language=lang, content=code, dependencies=deps))
    return blocks
