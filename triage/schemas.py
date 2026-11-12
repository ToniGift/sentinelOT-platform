from typing import List, Literal, Optional
from pydantic import BaseModel, Field


class Alert(BaseModel):
    alert_id: str
    timestamp: str
    source: str      # "synthetic", "labshock-elk" or "labshock-sniffer"
    title: str
    description: str
    severity_src: Optional[str] = None
    protocol: Optional[str] = None   # modbus, opcua, enip, dnp3, profinet
    src_ip: Optional[str] = None
    dst_ip: Optional[str] = None
    src_asset: Optional[str] = None
    dst_asset: Optional[str] = None
    raw: dict = Field(default_factory=dict)


class Indicators(BaseModel):
    ips: List[str] = Field(default_factory=list)
    cves: List[str] = Field(default_factory=list)
    protocols: List[str] = Field(default_factory=list)
    function_codes: List[str] = Field(default_factory=list)


class IntakeResult(BaseModel):
    summary: str
    indicators: Indicators
    search_queries: List[str] = Field(default_factory=list)  # code uses [:3]
    embedded_instructions: bool = False
    embedded_instructions_note: str = ""


class IntelItem(BaseModel):
    title: str
    url: str
    finding: str
    product: str = "not stated"   # vendor/product the finding concerns


class IntelResult(BaseModel):
    summary: str
    items: List[IntelItem] = Field(default_factory=list)


class Technique(BaseModel):
    id: str
    name: str
    rationale: str


class MapperResult(BaseModel):
    techniques: List[Technique] = Field(default_factory=list)


class TriageResult(BaseModel):
    verdict: Literal["escalate", "investigate", "likely_benign"]
    priority: Literal["P1", "P2", "P3", "P4"]
    confidence: float = Field(ge=0.0, le=1.0)
    process_impact: str
    reasoning: str
    evidence: List[str]


class Action(BaseModel):
    action: str
    type: Literal["read_only", "needs_operator_approval"]
    standard_ref: Optional[str] = None   # e.g. IEC 62443, NIST SP 800-82


class AdvisorResult(BaseModel):
    summary: str
    actions: List[Action]
