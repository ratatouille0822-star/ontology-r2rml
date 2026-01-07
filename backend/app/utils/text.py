import re


def normalize_text(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[_\-]+", " ", text)
    text = re.sub(r"[^a-z0-9\s]", "", text)
    return re.sub(r"\s+", " ", text).strip()


def local_name_from_iri(iri: str) -> str:
    if "#" in iri:
        return iri.split("#")[-1]
    return iri.rsplit("/", 1)[-1]
