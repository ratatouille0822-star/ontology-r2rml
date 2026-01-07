from app.models.schemas import MappingItem


def generate_r2rml(mapping: list[MappingItem], table_name: str, base_iri: str) -> str:
    base = base_iri if base_iri.endswith('/') else base_iri + '/'

    lines = [
        "@prefix rr: <http://www.w3.org/ns/r2rml#> .",
        f"@prefix ex: <{base}> .",
        "",
        "ex:TriplesMap1 a rr:TriplesMap ;",
        f"  rr:logicalTable [ rr:tableName \"{table_name}\" ] ;",
        f"  rr:subjectMap [ rr:template \"{base}row/{{id}}\" ] ;",
    ]

    for idx, item in enumerate(mapping, start=1):
        lines.append("  rr:predicateObjectMap [")
        lines.append(f"    rr:predicate <{item.property_iri}> ;")
        lines.append(f"    rr:objectMap [ rr:column \"{item.field}\" ]")
        lines.append("  ]" + (" ;" if idx != len(mapping) else " ."))

    return "\n".join(lines)
