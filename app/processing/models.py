from dataclasses import dataclass, field

@dataclass
class ParsedDocument:
    doc_id: str
    title: str
    url: str | None
    text: str
    sections: list[tuple[list[str], str]]
    metadata: dict

@dataclass
class Chunk:
    chunk_id: str
    doc_id: str
    text: str
    title: str
    heading_path: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)