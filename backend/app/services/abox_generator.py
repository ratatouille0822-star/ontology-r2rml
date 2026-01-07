from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple
from urllib.parse import quote

from rdflib import Graph, Literal, URIRef

from app.models.schemas import MappingItem


def generate_abox(
    tables: list,
    mapping: list[MappingItem],
    base_iri: str,
    output_dir: Optional[str] = None,
) -> Tuple[str, Optional[str]]:
    graph = Graph()

    base = base_iri if base_iri.endswith('/') else base_iri + '/'
    mapping_by_table = _group_mapping_by_table(mapping)

    for table in tables:
        table_name = _table_value(table, 'name', None)
        rows = _table_value(table, 'rows', [])
        if not table_name or table_name not in mapping_by_table:
            continue
        table_mapping = mapping_by_table[table_name]
        table_token = quote(str(table_name))
        for index, row in enumerate(rows, start=1):
            subject = URIRef(f"{base}table/{table_token}/row/{index}")
            for item in table_mapping:
                value = row.get(item.field)
                if value is None:
                    continue
                graph.add((subject, URIRef(item.property_iri), Literal(value)))

    content = graph.serialize(format='turtle')
    file_path = None

    if output_dir:
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime('%Y%m%d-%H%M%S')
        target = Path(output_dir) / f"abox-{stamp}.ttl"
        target.write_text(content, encoding='utf-8')
        file_path = str(target)

    return content, file_path


def _group_mapping_by_table(mapping: list[MappingItem]) -> dict[str, list[MappingItem]]:
    grouped: dict[str, list[MappingItem]] = {}
    for item in mapping:
        if not item.table_name:
            continue
        grouped.setdefault(item.table_name, []).append(item)
    return grouped


def _table_value(table, key: str, default):
    if isinstance(table, dict):
        return table.get(key, default)
    return getattr(table, key, default)
