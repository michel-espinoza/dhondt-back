# app/models/models.py
from pydantic import BaseModel
from typing import List, Optional
from dataclasses import dataclass

# ============================================================
# MODELOS PYDANTIC (para API responses)
# ============================================================

class Partido(BaseModel):
    id: int
    nombre: str
    sigla: Optional[str] = None
    
    class Config:
        from_attributes = True

class Candidato(BaseModel):
    id: int
    nombre: str
    partido: Partido
    votos: int
    matched_from: Optional[str] = None
    match_quality: Optional[float] = 0.0
    
    class Config:
        from_attributes = True

class Lista(BaseModel):
    id: int
    nombre: str
    distrito: str
    candidatos: List[Candidato] = []
    
    class Config:
        from_attributes = True

class Pacto(BaseModel):
    id: str
    nombre: str
    votos: int = 0
    escaños: Optional[int] = None
    porcentaje: Optional[float] = None
    
    class Config:
        from_attributes = True

class PartidoDetalle(BaseModel):
    id: str
    nombre: str
    pacto_id: Optional[str] = None
    votos: float = 0.0
    escaños: Optional[int] = None
    porcentaje: Optional[float] = None
    
    class Config:
        from_attributes = True

class Encuesta(BaseModel):
    nombre: str
    votos: int
    porcentaje: Optional[float] = None
    
    class Config:
        from_attributes = True

class ResultadoDHondt(BaseModel):
    distrito: str
    total_votos: float
    escaños_totales: int
    allocation_level: List[dict]  # Pactos con escaños
    parties: List[PartidoDetalle]
    elected_candidates: List[dict]
    
    class Config:
        from_attributes = True

# ============================================================
# DATACLASSES (para procesamiento interno)
# ============================================================

@dataclass
class CandidatoData:
    id: str
    nombre: str
    votos: float
    partido_id: str
    matched_from: Optional[str] = None
    match_quality: Optional[float] = 0.0

@dataclass
class PartidoData:
    id: str
    nombre: str
    votos: float
    pacto_id: Optional[str] = None

@dataclass
class PactoData:
    id: str
    nombre: str
    votos: int = 0