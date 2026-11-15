"""Read-only static documentation and source inspection."""
import ast
import os
from pathlib import Path
import re

from .phrases import MATERIALCERTIFICATEEXTRACTION, NOMATERIALCERTIFICATEEXTRACTION, GENERIC_NAMES


def normalize(text):
    return ' '.join(text.lower().replace("n't", ' not').replace('’nt', ' not').replace('n’t', ' not').replace('-', ' ').split())


def prose(text):
    """Replace fenced lines with blanks, preserving source line numbers."""
    fence = None
    result = []
    for line in text.splitlines():
        if fence:
            if re.match(r'^ {0,3}' + re.escape(fence[0]) + '{' + str(fence[1]) + r',}\s*$', line):
                fence = None
            result.append('')
        else:
            match = re.match(r'^ {0,3}(`{3,}|~{3,})(.*)$', line)
            if match and not (match[1][0] == '`' and '`' in match[2]):
                fence = (match[1][0], len(match[1]))
                result.append('')
            else:
                result.append(line)
    return '\n'.join(result)


def _pattern(phrases):
    return re.compile(r'\b(?:' + '|'.join(re.escape(p) for p in sorted(phrases, key=lambda p: (-len(p), p))) + r')\b')


POSITIVE = _pattern(MATERIALCERTIFICATEEXTRACTION)
NEGATIVE = _pattern(NOMATERIALCERTIFICATEEXTRACTION)


def claims(text):
    result = []
    paragraph = []
    start = 1
    def flush():
        value = normalize(' '.join(paragraph))
        denials = list(NEGATIVE.finditer(value))
        for match in denials:
            result.append({'family': 'negative', 'phrase': match[0], 'line': start})
        masked = list(value)
        for match in denials:
            masked[match.start():match.end()] = ' ' * (match.end()-match.start())
        for match in POSITIVE.finditer(''.join(masked)):
            result.append({'family': 'positive', 'phrase': match[0], 'line': start})
    for number, line in enumerate(prose(text).splitlines() + [''], 1):
        if line.strip():
            if not paragraph:
                start = number
            paragraph.append(line)
        else:
            flush()
            paragraph = []
    return result


def source_evidence(text):
    """Return route locations in one module; inspected code is never executed."""
    try:
        tree = ast.parse(text)
    except (SyntaxError, ValueError):
        return []
    nodes = list(ast.walk(tree))
    definitions = {n.name for n in nodes if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))}
    aliases = {}
    imported_mindee = False
    bindings = {}
    for node in nodes:
        if isinstance(node, ast.Import):
            for item in node.names:
                aliases[item.asname or item.name.split('.')[0]] = item.name if item.asname else item.name.split('.')[0]
                imported_mindee |= item.name.split('.')[0] == 'mindee'
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ''
            imported_mindee |= module.split('.')[0] == 'mindee'
            for item in node.names:
                aliases[item.asname or item.name] = module + '.' + item.name
        elif isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for target in targets:
                for name in ast.walk(target):
                    if isinstance(name, ast.Name):
                        bindings[name.id] = node.value if isinstance(target, ast.Name) else None
        elif isinstance(node, (ast.With, ast.AsyncWith)):
            for item in node.items:
                if item.optional_vars:
                    for name in ast.walk(item.optional_vars):
                        if isinstance(name, ast.Name):
                            bindings[name.id] = None

    def resolve(node, seen=None):
        seen = set() if seen is None else seen
        if isinstance(node, ast.Name):
            name = node.id
            if name in definitions or name in seen:
                return None
            if name in bindings:
                return resolve(bindings[name], seen | {name})
            return aliases.get(name)
        if isinstance(node, ast.Attribute):
            base = resolve(node.value, seen)
            return base + '.' + node.attr if base else None
        return None

    def shadowed(node):
        if isinstance(node, ast.Name):
            return node.id in definitions or (node.id in bindings and resolve(node) is None)
        if isinstance(node, ast.Attribute):
            if node.attr in definitions:
                return True
            # Binding an instance (x = Client()) is normal. Rebinding imported
            # module names invalidates their namespace routes.
            base = node.value
            while isinstance(base, ast.Attribute):
                base = base.value
            return isinstance(base, ast.Name) and base.id in aliases and resolve(base) is None
        return False

    calls = [n for n in nodes if isinstance(n, ast.Call)]
    clients = []
    parses = []
    result = []
    for call in calls:
        func = call.func
        if shadowed(func):
            continue
        resolved = resolve(func)
        literal_client = (isinstance(func, ast.Attribute) and func.attr == 'Client'
                          and isinstance(func.value, ast.Name) and func.value.id == 'mindee')
        if imported_mindee and (resolved == 'mindee.Client' or literal_client):
            clients.append(call)
        if isinstance(func, ast.Attribute) and func.attr == 'parse' and 'parse' not in definitions:
            arguments = list(call.args) + [kw.value for kw in call.keywords]
            for arg in arguments:
                name = arg.id if isinstance(arg, ast.Name) else arg.attr if isinstance(arg, ast.Attribute) else None
                if name == 'MaterialCertificateV1' and not shadowed(arg):
                    parses.append(call)
                    break
        route = func.attr if isinstance(func, ast.Attribute) else (resolved or '').split('.')[-1]
        if route in GENERIC_NAMES and route not in definitions:
            result.append({'line': call.lineno, 'route': route})
    if clients and parses:
        result.extend({'line': call.lineno, 'route': 'mindee.Client + parse(MaterialCertificateV1)'} for call in parses)
    return sorted(result, key=lambda item: (item['line'], item['route']))


def _ignored(parts, prefixes):
    return any(parts[:len(prefix)] == prefix for prefix in prefixes)


def audit(root, ignores=(), fail_on='high'):
    root = Path(root)
    if root.is_symlink() or not root.is_dir():
        raise OSError('Repository must be a readable, non-symlink directory: ' + str(root))
    prefixes = [tuple(Path(p).parts) for p in ignores if p]
    found_claims, production, tests = [], [], []
    def walk_error(error):
        raise error
    for directory, dirs, files in os.walk(root, followlinks=False, onerror=walk_error):
        current = Path(directory)
        dirs[:] = sorted(d for d in dirs if not (current/d).is_symlink() and not _ignored((current/d).relative_to(root).parts, prefixes))
        for filename in sorted(files):
            path = current/filename
            rel = path.relative_to(root)
            if path.is_symlink() or _ignored(rel.parts, prefixes):
                continue
            is_doc = rel.as_posix() == 'README.md' or (path.suffix == '.md' and 'docs' in rel.parts[:-1])
            is_source = path.suffix == '.py'
            if not (is_doc or is_source):
                continue
            text = path.read_text(encoding='utf-8')
            if is_doc:
                found_claims.extend(dict(item, path=rel.as_posix()) for item in claims(text))
            if is_source:
                if any(p in rel.parts[:-1] for p in ('fixtures', 'docs', 'examples')):
                    continue
                test = 'tests' in rel.parts[:-1] or filename.startswith('test_') or filename.endswith('_test.py')
                destination = tests if test else production
                destination.extend(dict(item, path=rel.as_posix()) for item in source_evidence(text))
    findings = []
    for family in ('positive', 'negative'):
        locations = [item for item in found_claims if item['family'] == family]
        if locations and ((family == 'positive' and not production) or (family == 'negative' and production)):
            severity = 'MEDIUM' if family == 'positive' and tests else 'HIGH'
            rule = 'documented-' + ('no-' if family == 'negative' else '') + 'material-certificate-extraction-claim-false'
            message = ('Documented capability has no production source evidence.' if family == 'positive' else 'Documented denial contradicts production source evidence.')
            findings.append({'rule': rule, 'severity': severity, 'message': message, 'locations': locations})
    failed = any(f['severity'] == 'HIGH' or fail_on == 'medium' for f in findings)
    return {'verdict': 'FAIL' if failed else 'PASS', 'findings': findings, 'production_evidence': production, 'test_evidence': tests}
