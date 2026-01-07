from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple

from rdflib import Graph, Literal, URIRef

from app.models.schemas import MappingItem


def generate_abox(
    rows: list[dict],
    mapping: list[MappingItem],
    base_iri: str,
    output_dir: Optional[str] = None,
) -> Tuple[str, Optional[str]]:
    graph = Graph()

    base = base_iri if base_iri.endswith('/') else base_iri + '/'

    for index, row in enumerate(rows, start=1):
        subject = URIRef(f"{base}row/{index}")
        for item in mapping:
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
