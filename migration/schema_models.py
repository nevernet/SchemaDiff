from dataclasses import dataclass, field
from typing import Optional, Dict, List
from collections import OrderedDict


@dataclass
class Column:
    name: str
    data_type: str
    nullable: bool = True
    default: Optional[str] = None
    auto_increment: bool = False
    generated: Optional[dict] = None
    comment: Optional[str] = None


@dataclass
class Index:
    name: str
    columns: List[str]
    unique: bool = False
    index_type: Optional[str] = None


@dataclass
class ForeignKey:
    name: str
    columns: List[str]
    ref_table: str
    ref_columns: List[str]
    on_delete: Optional[str] = None
    on_update: Optional[str] = None


@dataclass
class Table:
    name: str
    schema: Optional[str] = None
    columns: OrderedDict = field(default_factory=OrderedDict)
    indexes: Dict = field(default_factory=dict)
    primary_key: Optional[List[str]] = None
    fks: Dict = field(default_factory=dict)
    engine: Optional[str] = None
    charset: Optional[str] = None
    comment: Optional[str] = None


@dataclass
class DatabaseSchema:
    tables: Dict = field(default_factory=dict)
