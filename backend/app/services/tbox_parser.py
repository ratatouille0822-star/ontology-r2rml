from typing import List

from rdflib import Graph, RDF, RDFS, OWL

from app.models.schemas import IriItem, ObjectPropertyItem, PropertyItem
from app.utils.text import local_name_from_iri


EXTENSION_FORMAT_MAP = {
    ".ttl": "turtle",
    ".rdf": "xml",
    ".owl": "xml",
    ".xml": "xml",
    ".nt": "nt",
}


def parse_tbox(content: bytes, filename: str | None) -> dict:
    graph = Graph()
    fmt = None
    if filename:
        lower = filename.lower()
        for ext, value in EXTENSION_FORMAT_MAP.items():
            if lower.endswith(ext):
                fmt = value
                break
    graph.parse(data=content, format=fmt)

    properties: dict[str, object] = {}
    for prop in graph.subjects(RDF.type, OWL.DatatypeProperty):
        properties[str(prop)] = prop
    for prop in graph.subjects(RDF.type, RDF.Property):
        properties.setdefault(str(prop), prop)

    parent_props = _find_parent_properties(graph, properties)

    results: List[PropertyItem] = []
    for iri, prop in properties.items():
        label = graph.value(prop, RDFS.label)
        domains = [_build_iri_item(graph, item) for item in graph.objects(prop, RDFS.domain)]
        ranges = [_build_iri_item(graph, item) for item in graph.objects(prop, RDFS.range)]
        results.append(
            PropertyItem(
                iri=iri,
                label=str(label) if label else None,
                local_name=local_name_from_iri(iri),
                domains=[item for item in domains if item],
                ranges=[item for item in ranges if item],
                is_leaf=iri not in parent_props,
            )
        )

    results.sort(key=lambda item: item.label or item.local_name or item.iri)
    classes = _extract_classes(graph)
    object_props = _extract_object_properties(graph)
    ttl = graph.serialize(format="turtle")
    return {
        "properties": results,
        "classes": classes,
        "object_properties": object_props,
        "ttl": ttl,
    }


def _build_iri_item(graph: Graph, node) -> IriItem | None:
    if node is None:
        return None
    iri = str(node)
    label = graph.value(node, RDFS.label)
    return IriItem(
        iri=iri,
        label=str(label) if label else None,
        local_name=local_name_from_iri(iri),
    )


def _find_parent_properties(graph: Graph, properties: dict[str, object]) -> set[str]:
    parent_props: set[str] = set()
    prop_set = set(properties.keys())
    for child, parent in graph.subject_objects(RDFS.subPropertyOf):
        child_iri = str(child)
        parent_iri = str(parent)
        if child_iri in prop_set and parent_iri in prop_set:
            parent_props.add(parent_iri)
    return parent_props


def _extract_classes(graph: Graph) -> List[IriItem]:
    classes: dict[str, object] = {}
    for cls in graph.subjects(RDF.type, OWL.Class):
        classes[str(cls)] = cls
    for cls in graph.subjects(RDF.type, RDFS.Class):
        classes.setdefault(str(cls), cls)

    results: List[IriItem] = []
    for iri, cls in classes.items():
        label = graph.value(cls, RDFS.label)
        results.append(
            IriItem(
                iri=iri,
                label=str(label) if label else None,
                local_name=local_name_from_iri(iri),
            )
        )
    results.sort(key=lambda item: item.label or item.local_name or item.iri)
    return results


def _extract_object_properties(graph: Graph) -> List[ObjectPropertyItem]:
    object_props: dict[str, object] = {}
    for prop in graph.subjects(RDF.type, OWL.ObjectProperty):
        object_props[str(prop)] = prop

    results: List[ObjectPropertyItem] = []
    for iri, prop in object_props.items():
        label = graph.value(prop, RDFS.label)
        domains = [_build_iri_item(graph, item) for item in graph.objects(prop, RDFS.domain)]
        ranges = [_build_iri_item(graph, item) for item in graph.objects(prop, RDFS.range)]
        results.append(
            ObjectPropertyItem(
                iri=iri,
                label=str(label) if label else None,
                local_name=local_name_from_iri(iri),
                domains=[item for item in domains if item],
                ranges=[item for item in ranges if item],
            )
        )
    results.sort(key=lambda item: item.label or item.local_name or item.iri)
    return results
