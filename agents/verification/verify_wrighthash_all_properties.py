"""
Divide-and-verify for Wright# ADL — all property types.

Extends the original verify_wrighthash (liveness-only) to also handle
safety and security assertions during the divide step.

Supported assertion types:
  1. Liveness:              assert sys |= [] (A.p.e -> <> B.q.f);
  2. Safety absence:        assert sys |= [] (!A.p.e);
  3. Conditional absence:   assert sys |= [] (A.p.e -> !B.q.f);
                            assert sys |= [] (A.p.e -> [] (!B.q.f));
  4. Prerequisite (until):  assert sys |= (!B.q.f) U (A.p.e);
                            assert sys |= [] ((!B.q.f) U (A.p.e));

Usage (from project root):
    python -m agents.verification.verify_wrighthash_all_properties

Usage (from agentteam/):
    python3 ../agents/verification/verify_wrighthash_all_properties.py

Reads tmp/refactored.adl and tmp/assertions.md, prints "valid" or "invalid".
"""

import os
import re
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Optional

import requests


# ---------- Preprocessing (path extraction) ----------

def extract_connector_order(adl_text):
    connector_pattern = r'connector\s+(\w+)\s*{([^}]*)}'
    role_pattern = r'role\s+(\w+)\(?(\w*)\)?\s*=\s*([^;]+);'
    connectors = re.findall(connector_pattern, adl_text)
    connector_order = []
    for connector_name, connector_body in connectors:
        roles = re.findall(role_pattern, connector_body)
        output_role = None
        role_behaviors = {}
        for role_name, param, behavior in roles:
            role_behaviors[role_name] = behavior
            if param == 'j':
                output_role = role_name
        if not output_role:
            connector_order.append([connector_name, None, None, None])
            continue
        behavior_sequence = role_behaviors[output_role]
        tokens = [token.strip() for token in behavior_sequence.split('->')]
        first_input_role = None
        second_input_role = None
        exclamation_events = [t.replace('!j', '') for t in tokens if '!j' in t]
        for event in exclamation_events:
            for role_name, behavior in role_behaviors.items():
                if f"{event}?j" in behavior:
                    if not first_input_role:
                        first_input_role = role_name
                    elif not second_input_role and role_name != first_input_role:
                        second_input_role = role_name
        connector_order.append([connector_name, output_role, first_input_role, second_input_role])
    return connector_order


def parse_adl(adl_text):
    attachments = []
    connectors = {}
    for match in re.finditer(r'declare (\w+) = (\w+);', adl_text):
        connectors[match.group(1)] = match.group(2)
    for match in re.finditer(r'attach ([\w.]+)\(\) = (.+);', adl_text):
        component_port = match.group(1)
        roles = [role.strip() for role in match.group(2).split('<*>')]
        for role in roles:
            role_clean = role.split('(')[0]
            attachments.append((component_port, role_clean))
    return connectors, attachments


def build_graph(connectors, attachments, connector_order_list):
    conn_order = {}
    for entry in connector_order_list:
        ctype, out_role, in1, in2 = entry
        chain = [out_role]
        if in1:
            chain.append(in1)
        if in2:
            chain.append(in2)
        conn_order[ctype] = chain
    inst_roles = defaultdict(lambda: defaultdict(list))
    for comp, att in attachments:
        parts = att.split('.', 1)
        if len(parts) != 2:
            continue
        instance, role_part = parts
        role = role_part.split('(')[0]
        inst_roles[instance][role].append(comp)
    graph = defaultdict(list)
    for inst, roles in inst_roles.items():
        if inst not in connectors:
            continue
        ctype = connectors[inst]
        if ctype not in conn_order:
            continue
        chain = conn_order[ctype]
        if len(chain) == 2:
            out_role, final_role = chain
            if out_role in roles and final_role in roles:
                for src in roles[out_role]:
                    for tgt in roles[final_role]:
                        graph[src].append(tgt)
                for tgt in roles[final_role]:
                    graph[tgt].append(tgt)
        elif len(chain) == 3:
            out_role, mid_role, final_role = chain
            if out_role in roles and mid_role in roles:
                for src in roles[out_role]:
                    for mid in roles[mid_role]:
                        graph[src].append(mid)
            if final_role in roles:
                if mid_role in roles:
                    for mid in roles[mid_role]:
                        for tgt in roles[final_role]:
                            graph[mid].append(tgt)
                if out_role in roles:
                    for src in roles[out_role]:
                        for tgt in roles[final_role]:
                            graph[src].append(tgt)
                for tgt in roles[final_role]:
                    graph[tgt].append(tgt)
    for node in graph:
        graph[node] = list(set(graph[node]))
    non_final_ports = set()
    for inst, roles in inst_roles.items():
        if inst not in connectors:
            continue
        ctype = connectors[inst]
        if ctype not in conn_order:
            continue
        chain = conn_order[ctype]
        final_role = chain[-1]
        for role, comps in roles.items():
            if role != final_role:
                non_final_ports.update(comps)
    pruned_graph = {}
    for node, targets in graph.items():
        if node in non_final_ports:
            pruned_graph[node] = targets
    for port in non_final_ports:
        if port not in pruned_graph:
            pruned_graph[port] = []
    return pruned_graph


def strict_ordered_attachment_with_connector(adl_text, connector_order_list):
    connector_order = {}
    for entry in connector_order_list:
        ctype, out_role, in1, in2 = entry
        inputs = []
        if in1 is not None:
            inputs.append(in1)
        if in2 is not None:
            inputs.append(in2)
        connector_order[ctype] = {'output': out_role, 'inputs': inputs}
    system_match = re.search(r'system\s+\w+\s*\{(.*?)\n\}', adl_text, re.DOTALL)
    system_text = system_match.group(1) if system_match else ""
    declare_pattern = r'declare\s+(\w+)\s*=\s*(\w+)\s*;'
    declares = re.findall(declare_pattern, system_text)
    connector_instances = {inst: ctype for inst, ctype in declares}
    attach_pattern = r'attach\s+([\w\.]+)\s*\(\)\s*=\s*(.+?);'
    attach_matches = re.findall(attach_pattern, system_text)
    connector_usage = defaultdict(lambda: defaultdict(list))
    for lhs, rhs in attach_matches:
        parts = [part.strip() for part in rhs.split("<*>")]
        for part in parts:
            m = re.search(r'(\w+)\.(\w+)\s*\(', part)
            if m:
                instance, role = m.groups()
                connector_usage[instance][role].append(lhs)
    immediate_edges = defaultdict(list)
    for instance, roles in connector_usage.items():
        if instance not in connector_instances:
            continue
        ctype = connector_instances[instance]
        if ctype not in connector_order:
            continue
        out_role = connector_order[ctype]['output']
        input_roles = connector_order[ctype]['inputs']
        sources = roles.get(out_role, [])
        for in_role in input_roles:
            dests = roles.get(in_role, [])
            for s in sources:
                for d in dests:
                    immediate_edges[s].append(d)
    return dict(immediate_edges)


def merge_paths_with_strict_order(paths, attachment_order):
    merged_paths = []
    for path in paths:
        merged_path = []
        visited = set()
        for idx, node in enumerate(path):
            if node not in visited:
                merged_path.append(node)
                visited.add(node)
            if node in attachment_order:
                for ordered_node in attachment_order[node]:
                    if ordered_node in visited:
                        continue
                    stack = [ordered_node]
                    while stack:
                        current = stack.pop()
                        if current not in visited:
                            merged_path.append(current)
                            visited.add(current)
                            if current in attachment_order:
                                stack.extend(reversed(attachment_order[current]))
        if merged_path not in merged_paths:
            merged_paths.append(merged_path)
    return merged_paths


def enhanced_find_all_paths(graph, extracted_attachments):
    def dfs(current, path, all_paths):
        path.append(current)
        if current not in graph or not graph[current]:
            all_paths.append(list(path))
        else:
            for neighbor in graph[current]:
                if neighbor not in path:
                    dfs(neighbor, path, all_paths)
        path.pop()

    def is_subsequence(sub, full):
        if len(sub) > len(full):
            return False
        it = iter(full)
        return all(node in it for node in sub)

    all_paths = []
    for start in graph.keys():
        dfs(start, [], all_paths)
    unique_paths = []
    seen = set()
    for path in all_paths:
        path_str = " -> ".join(path)
        if path_str not in seen:
            seen.add(path_str)
            unique_paths.append(path)
    non_redundant_paths = []
    for idx, path in enumerate(unique_paths):
        is_subpath = False
        for jdx, other_path in enumerate(unique_paths):
            if idx != jdx and is_subsequence(path, other_path):
                is_subpath = True
                break
        if not is_subpath:
            non_redundant_paths.append(path)
    final_paths = merge_paths_with_strict_order(non_redundant_paths, extracted_attachments)
    return final_paths


def preprocess_with_adl(input_adl):
    connectors, attachments = parse_adl(input_adl)
    connector_order = extract_connector_order(input_adl)
    graph = build_graph(connectors, attachments, connector_order)
    attachment_order = strict_ordered_attachment_with_connector(input_adl, connector_order)
    all_paths = enhanced_find_all_paths(graph, attachment_order)
    return all_paths


# ---------- Divide ADL & PAT verification ----------

def _verify_adl_via_pat(adl_with_assertions):
    url = "http://0.0.0.0:0000/api/adlapi/verify"  # adjust if needed
    data = {"model": "test", "code": adl_with_assertions}
    try:
        response = requests.post(url, json=data, timeout=(10, 900))
        VS = response.json()
    except Exception as e:
        print("Error occurred:", e)
        return "error"
    return VS


def extract_attach_statements(adl_text):
    attach_pattern = r'attach\s+[\w\.]+\(\)\s*=\s*.*?;'
    attach_statements = re.findall(attach_pattern, adl_text, re.DOTALL)
    return [stmt.strip() for stmt in attach_statements]


def extract_lhs(attach_statement):
    m = re.search(r'^attach\s+([\w\.]+)\(\)\s*=', attach_statement)
    if m:
        return m.group(1)
    return None


def select_attachments_for_paths(paths, attach_statements):
    attach_dict = {}
    for stmt in attach_statements:
        comp_port = extract_lhs(stmt)
        if comp_port:
            attach_dict[comp_port] = stmt
    all_selected_attachments = []
    for path_idx, path_nodes in enumerate(paths):
        selected_attachments = set()
        for node in path_nodes:
            if node in attach_dict:
                selected_attachments.add(attach_dict[node])
        all_selected_attachments.append((path_idx, list(selected_attachments)))
    return all_selected_attachments


def fix_last_brace_indentation(adl_code):
    lines = adl_code.split("\n")
    for i in range(len(lines) - 1, -1, -1):
        if lines[i].strip() == "}":
            lines[i] = "}"
            break
    return "\n".join(lines)


def update_adl_with_new_attachments(original_adl, new_attachments, new_execute_line):
    cleaned_adl = re.sub(r'attach\s+[\w\.]+\(\)\s*=.*?;\s*', '', original_adl, flags=re.DOTALL)
    cleaned_adl = re.sub(r'execute\s+[^;\n]+;?', '', cleaned_adl, flags=re.DOTALL)
    cleaned_adl = re.sub(r'\n\s*\n', '\n', cleaned_adl).strip()
    system_block_pattern = r'(system\s+\w+\s*{)'
    match = re.search(system_block_pattern, cleaned_adl)
    if match:
        new_attachments_str = "\n" + new_attachments + "\n\t " + new_execute_line
        declare_pattern = r'(declare\s+\w+\s*=\s*\w+\s*;)'
        declares = list(re.finditer(declare_pattern, cleaned_adl, flags=re.MULTILINE))
        if declares:
            last_declare = declares[-1]
            insertion_point = last_declare.end()
            updated_adl = cleaned_adl[:insertion_point] + new_attachments_str + cleaned_adl[insertion_point:]
        else:
            updated_adl = re.sub(system_block_pattern, r'\1' + new_attachments_str, cleaned_adl)
        updated_adl = fix_last_brace_indentation(updated_adl)
        return updated_adl
    raise ValueError("System block not found in ADL.")


# ── Assertion parser ──────────────────────────────────────────────

_COMP_PORT_EVENT = r'(\w+\.\w+\.\w+)'


@dataclass
class ParsedAssertion:
    raw: str
    kind: str       # liveness | safety_absence | safety_conditional_absence | safety_prerequisite
    system: str
    components: dict = field(default_factory=dict)  # Component.port -> role


def _system_name(assertion: str) -> str:
    m = re.search(r'assert\s+(\w+)', assertion)
    return m.group(1) if m else ""


def _comp_port(ref: str) -> str:
    """'Component.port.event' → 'Component.port'"""
    parts = ref.split('.')
    return f"{parts[0]}.{parts[1]}" if len(parts) >= 2 else ref


def _try_liveness(a: str) -> Optional[ParsedAssertion]:
    """assert sys |= [] (A.p.e -> <> B.q.f);"""
    m = re.search(
        r'assert\s+\w+\s+\|=\s+\[\]\s+\(' + _COMP_PORT_EVENT
        + r'\s+->\s+<>\s+' + _COMP_PORT_EVENT + r'\)', a)
    if not m:
        return None
    return ParsedAssertion(raw=a, kind='liveness', system=_system_name(a),
                           components={_comp_port(m.group(1)): 'source',
                                       _comp_port(m.group(2)): 'target'})


def _try_cond_absence_box(a: str) -> Optional[ParsedAssertion]:
    """assert sys |= [] (A.p.e -> [] (!B.q.f));"""
    m = re.search(
        r'assert\s+\w+\s+\|=\s+\[\]\s+\(' + _COMP_PORT_EVENT
        + r'\s+->\s+\[\]\s+\(\s*!' + _COMP_PORT_EVENT + r'\s*\)\)', a)
    if not m:
        return None
    return ParsedAssertion(raw=a, kind='safety_conditional_absence', system=_system_name(a),
                           components={_comp_port(m.group(1)): 'trigger',
                                       _comp_port(m.group(2)): 'forbidden'})


def _try_cond_absence_simple(a: str) -> Optional[ParsedAssertion]:
    """assert sys |= [] (A.p.e -> !B.q.f);"""
    m = re.search(
        r'assert\s+\w+\s+\|=\s+\[\]\s+\(' + _COMP_PORT_EVENT
        + r'\s+->\s+!' + _COMP_PORT_EVENT + r'\)', a)
    if not m:
        return None
    return ParsedAssertion(raw=a, kind='safety_conditional_absence', system=_system_name(a),
                           components={_comp_port(m.group(1)): 'trigger',
                                       _comp_port(m.group(2)): 'forbidden'})


def _try_absence(a: str) -> Optional[ParsedAssertion]:
    """assert sys |= [] (!A.p.e);"""
    m = re.search(
        r'assert\s+\w+\s+\|=\s+\[\]\s+\(\s*!' + _COMP_PORT_EVENT + r'\s*\)', a)
    if not m:
        return None
    return ParsedAssertion(raw=a, kind='safety_absence', system=_system_name(a),
                           components={_comp_port(m.group(1)): 'absent'})


def _try_prereq_global(a: str) -> Optional[ParsedAssertion]:
    """assert sys |= [] ((!B.q.f) U (A.p.e));"""
    m = re.search(
        r'assert\s+\w+\s+\|=\s+\[\]\s+\(\s*\(\s*!' + _COMP_PORT_EVENT
        + r'\s*\)\s*U\s+\(\s*' + _COMP_PORT_EVENT + r'\s*\)\s*\)', a)
    if not m:
        return None
    return ParsedAssertion(raw=a, kind='safety_prerequisite', system=_system_name(a),
                           components={_comp_port(m.group(1)): 'guarded',
                                       _comp_port(m.group(2)): 'prerequisite'})


def _try_prereq(a: str) -> Optional[ParsedAssertion]:
    """assert sys |= (!B.q.f) U (A.p.e);"""
    m = re.search(
        r'assert\s+\w+\s+\|=\s+\(\s*!' + _COMP_PORT_EVENT
        + r'\s*\)\s*U\s+\(\s*' + _COMP_PORT_EVENT + r'\s*\)', a)
    if not m:
        return None
    return ParsedAssertion(raw=a, kind='safety_prerequisite', system=_system_name(a),
                           components={_comp_port(m.group(1)): 'guarded',
                                       _comp_port(m.group(2)): 'prerequisite'})


_MATCHERS = [
    _try_liveness,
    _try_cond_absence_box,
    _try_cond_absence_simple,
    _try_absence,
    _try_prereq_global,
    _try_prereq,
]


def parse_assertion(assertion: str) -> Optional[ParsedAssertion]:
    assertion = assertion.strip()
    for matcher in _MATCHERS:
        result = matcher(assertion)
        if result is not None:
            return result
    print(f"WARNING: unrecognised assertion, skipping: {assertion}")
    return None


def clean_assertions(raw_lines: list[str]) -> list[str]:
    """Strip comments (#, --, //), markdown headers (##), and blank lines.
    Returns only lines that look like actual assert statements (or could be one)."""
    cleaned = []
    for line in raw_lines:
        stripped = line.strip()
        if not stripped:
            continue
        # Markdown / hash comments
        if stripped.startswith('#'):
            continue
        # SQL/Ada-style line comments
        if stripped.startswith('--'):
            continue
        # C-style line comments
        if stripped.startswith('//'):
            continue
        # Optional: only keep lines that look like assertions (start with "assert ")
        # to avoid passing through any other accidental non-comment text
        if not stripped.startswith('assert '):
            continue
        cleaned.append(stripped)
    return cleaned


def parse_assertions(assertions: list[str]) -> list[ParsedAssertion]:
    cleaned = clean_assertions(assertions)
    results = []
    for a in cleaned:
        parsed = parse_assertion(a)
        if parsed is not None:
            results.append(parsed)
    return results


# ── Path-aware assertion filtering ────────────────────────────────


def _find_index(path_nodes, comp_port):
    """Return index of comp_port in path_nodes, or -1."""
    for i, node in enumerate(path_nodes):
        if node == comp_port:
            return i
    return -1


def _filter_liveness(path_nodes, assertions):
    """Include if both source and target on path, source before target."""
    result = []
    for a in assertions:
        src = a.components.get('source') or next((c for c, r in a.components.items() if r == 'source'), None)
        tgt = a.components.get('target') or next((c for c, r in a.components.items() if r == 'target'), None)
        # Fix: components dict is {comp_port: role}, so iterate properly
        src = tgt = None
        for comp, role in a.components.items():
            if role == 'source': src = comp
            elif role == 'target': tgt = comp
        if src is None or tgt is None:
            continue
        si, ti = _find_index(path_nodes, src), _find_index(path_nodes, tgt)
        if si != -1 and ti != -1 and si < ti:
            result.append(a.raw)
    return result


def _filter_absence(path_nodes, assertions):
    """Include if the referenced component.port appears on the path."""
    path_set = set(path_nodes)
    return [a.raw for a in assertions
            if any(comp in path_set for comp in a.components)]


def _filter_conditional_absence(path_nodes, assertions):
    """Include if both trigger and forbidden appear on the path."""
    path_set = set(path_nodes)
    result = []
    for a in assertions:
        trigger = forbidden = None
        for comp, role in a.components.items():
            if role == 'trigger': trigger = comp
            elif role == 'forbidden': forbidden = comp
        if trigger and forbidden and trigger in path_set and forbidden in path_set:
            result.append(a.raw)
    return result


def _filter_prerequisite(path_nodes, assertions):
    """Include if prerequisite appears BEFORE guarded on the path."""
    result = []
    for a in assertions:
        prereq = guarded = None
        for comp, role in a.components.items():
            if role == 'prerequisite': prereq = comp
            elif role == 'guarded': guarded = comp
        if prereq is None or guarded is None:
            continue
        pi, gi = _find_index(path_nodes, prereq), _find_index(path_nodes, guarded)
        if pi != -1 and gi != -1 and pi < gi:
            result.append(a.raw)
    return result


_FILTERS = {
    'liveness':                   _filter_liveness,
    'safety_absence':             _filter_absence,
    'safety_conditional_absence': _filter_conditional_absence,
    'safety_prerequisite':        _filter_prerequisite,
}


def get_tailored_assertions_for_path(path_nodes, parsed_assertions):
    """Return raw assertion strings relevant to a specific execution path."""
    if not path_nodes:
        return []
    by_kind = {}
    for p in parsed_assertions:
        by_kind.setdefault(p.kind, []).append(p)
    result = []
    for kind, group in by_kind.items():
        if kind in _FILTERS:
            result.extend(_FILTERS[kind](path_nodes, group))
    return result


# ── Divide & verify ──────────────────────────────────────────────


def divide_adl(adl_text, assertions):
    """Divide ADL into subdesigns, each with its tailored assertions."""
    paths = preprocess_with_adl(adl_text)
    attach_statements = extract_attach_statements(adl_text)
    selected_attachments = select_attachments_for_paths(paths, attach_statements)
    parsed = parse_assertions(assertions)

    adl_variants = []
    for path_idx, attaches in selected_attachments:
        attachment_string = "\t " + "\n\t ".join(attaches)
        lhs_list = [f"{extract_lhs(stmt)}()" for stmt in attaches]
        execute_line = "execute " + " || ".join(lhs_list) + ";"
        new_adl = update_adl_with_new_attachments(adl_text, attachment_string, execute_line)

        path_nodes = paths[path_idx] if path_idx < len(paths) else []
        tailored = get_tailored_assertions_for_path(path_nodes, parsed)

        if tailored:
            full_adl = new_adl + "\n" + "\n".join(tailored)
        else:
            full_adl = new_adl
        adl_variants.append(full_adl)
    return adl_variants


def verify_adl(adl_text, assertions):
    """Verify ADL against all property types. Returns 'valid' or 'invalid'."""
    divided_adls = divide_adl(adl_text, assertions)
    final_result = "valid"
    for adl_variant in divided_adls:
        VS = _verify_adl_via_pat(adl_variant)
        if VS == "error" or isinstance(VS, dict):
            if isinstance(VS, dict):
                print(VS.get('Message', 'Unknown error'))
            print(adl_variant)
            print("-" * 50)
            final_result = "invalid"
        else:
            for vs in VS:
                if vs['result'] == "invalid":
                    print(vs['fullResultString'])
                    print(adl_variant)
                    print("-" * 50)
                    final_result = "invalid"
    return final_result


def verify_from_files(adl_path="tmp/refactored.adl", assertions_path="tmp/assertions.md"):
    """Read ADL + assertions from files and verify. Returns 'valid' or 'invalid'."""
    if not os.path.isabs(adl_path):
        adl_path = os.path.join(os.getcwd(), adl_path)
    if not os.path.isabs(assertions_path):
        assertions_path = os.path.join(os.getcwd(), assertions_path)

    with open(adl_path) as f:
        adl_text = f.read()
    with open(assertions_path) as f:
        properties = [line.strip() for line in f if line.strip()]

    return verify_adl(adl_text, properties)


if __name__ == "__main__":
    print(verify_from_files())
