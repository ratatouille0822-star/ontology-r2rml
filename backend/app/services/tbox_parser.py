from typing import List

from rdflib import Graph, RDF, RDFS, OWL

from app.models.schemas import PropertyItem
from app.utils.text import local_name_from_iri


EXTENSION_FORMAT_MAP = {
    ".ttl": "turtle",
    ".rdf": "xml",
    ".owl": "xml",
    ".xml": "xml",
    ".nt": "nt",
}


def parse_tbox(content: bytes, filename: str | None) -> List[PropertyItem]:
    graph = Graph()
    fmt = None
    if filename:
        lower = filename.lower()
        for ext, value in EXTENSION_FORMAT_MAP.items():
            if lower.endswith(ext):
                fmt = value
                break
    graph.parse(data=content, format=fmt)

    properties = {}
    for prop in graph.subjects(RDF.type, OWL.DatatypeProperty):
        properties[str(prop)] = prop
    for prop in graph.subjects(RDF.type, RDF.Property):
        properties.setdefault(str(prop), prop)

    results: List[PropertyItem] = []
    for iri, prop in properties.items():
        label = graph.value(prop, RDFS.label)
        results.append(
            PropertyItem(
                iri=iri,
                label=str(label) if label else None,
                local_name=local_name_from_iri(iri),
            )
        )

    results.sort(key=lambda item: item.label or item.local_name or item.iri)
    return results
