# app/services/diputados_service.py
from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import List, Dict, Any, Optional
import unicodedata
import re
import difflib
import json
import os
import pandas as pd
import requests
from app.models.models import Partido, Candidato, Lista

# ============================================================
# CONFIGURACIÓN
# ============================================================
EMOL_CSV_URL = "https://www.emol.com/especiales/2025/nacional/elecciones/data/dip.csv"
DB_URL = "https://www.emol.com/especiales/2025/nacional/elecciones/data/db.json"

def load_pactos_from_file() -> List[Dict[str, Any]]:
    """Carga los pactos desde el archivo JSON."""
    try:
        ruta_pactos = os.path.join(os.path.dirname(__file__), '..', 'data', 'pactos.json')
        with open(ruta_pactos, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data.get('pactos', [])
    except Exception as e:
        print(f"⚠️ Error cargando pactos.json: {e}")
        return []

# Cargar pactos al iniciar
PACTOS_MAPPING = load_pactos_from_file()

def get_pacto_nombre(pacto_id: str) -> str:
    """Obtiene el nombre completo de un pacto desde su ID."""
    for pacto in PACTOS_MAPPING:
        if pacto.get("id") == pacto_id:
            return pacto.get("nombre", pacto_id)
    return pacto_id

# ============================================================
# DATACLASSES
# ============================================================
@dataclass
class Candidate:
    id: str
    name: str
    votes: float
    party_id: str
    matched_from: Optional[str] = None
    match_quality: Optional[float] = 0.0

@dataclass
class Party:
    id: str
    name: str
    votes: float
    pact_id: Optional[str] = None

@dataclass
class Pact:
    id: str
    name: str
    votes: int = 0

# ============================================================
# FUNCIONES AUXILIARES
# ============================================================

def normalize(s: str) -> str:
    """Normaliza texto: minúsculas, quita acentos."""
    if not s:
        return ""
    s = s.lower().strip()
    s = unicodedata.normalize("NFD", s)
    s = re.sub(r"[\u0300-\u036f]", "", s)
    return s


def normalize_district(distrito: str) -> str:
    """Normaliza el número de distrito. Acepta '10', 'D10', 'd10', etc."""
    # Extraer solo los números
    import re
    match = re.search(r'\d+', str(distrito))
    if match:
        num = match.group(0)
        # Asegurar que esté entre 1 y 28
        try:
            d = int(num)
            if 1 <= d <= 28:
                return str(d)
        except:
            pass
    return str(distrito)


def dhondt_alloc(votos_por_lista: Dict[str, float], num_escaños: int) -> Dict[str, int]:
    """
    Calcula la asignación de escaños usando el método D'Hondt.
    
    Args:
        votos_por_lista: Dict con {nombre_lista: votos}
        num_escaños: Número de escaños a distribuir
        
    Returns:
        Dict con {nombre_lista: escaños_asignados}
    """
    # 1️⃣ Crear tabla de cocientes (votos / divisor)
    cocientes = []
    for lista, votos in votos_por_lista.items():
        for divisor in range(1, num_escaños + 1):
            valor = votos / divisor
            cocientes.append((valor, lista))
    
    # 2️⃣ Ordenar de mayor a menor
    cocientes.sort(reverse=True, key=lambda x: x[0])
    
    # 3️⃣ Seleccionar los N cocientes más altos
    ganadores = cocientes[:num_escaños]
    
    # 4️⃣ Contar escaños por lista
    asignacion = {lista: 0 for lista in votos_por_lista}
    for _, lista in ganadores:
        asignacion[lista] += 1
    
    return asignacion


def load_encuesta(filename: str = "encuesta_d10.json") -> Dict:
    """Carga encuesta desde API externa: https://dhondt.azurewebsites.net/api/encuestas"""
    try:
        external_url = "https://dhondt.azurewebsites.net/api/encuestas"
        r = requests.get(external_url, timeout=10)
        r.raise_for_status()
        data = r.json()
        print("✅ Encuestas cargadas desde API externa")
        return data
    except Exception as e:
        print(f"❌ Error cargando encuestas desde API externa: {e}")
        # Retorna un diccionario vacío para evitar crashes
        return {}


def get_seats_for_district_api(distrito: str) -> int:
    """Obtiene cantidad de escaños desde API oficial de Emol."""
    try:
        codigo = f"60{str(distrito).zfill(2)}"
        r = requests.get(DB_URL, timeout=10)
        r.raise_for_status()
        data = r.json()
        entry = data.get("dbzonas", {}).get(codigo)
        if entry and "q" in entry:
            return int(entry["q"])
        else:
            print(f"⚠️ No se encontró distrito {codigo}")
            return 5
    except Exception as e:
        print(f"⚠️ Error obteniendo escaños: {e}")
        return 5


def assign_votes_to_candidates(
    candidates: List[Dict[str, Any]], 
    encuesta_lista: List[Dict[str, Any]],
    threshold: float = 0.8
) -> List[Dict[str, Any]]:
    """
    Asigna votos desde encuesta a candidatos usando fuzzy matching.
    
    Args:
        candidates: Lista de candidatos de Emol
        encuesta_lista: Lista de candidatos de encuesta
        threshold: Umbral mínimo de similitud (0-1)
        
    Returns:
        Candidatos con votos asignados
    """
    if not encuesta_lista:
        for c in candidates:
            c["votes"] = 0.0
            c["matched_from"] = None
            c["match_quality"] = 0.0
        return candidates

    names = [normalize(c["name"]) for c in candidates]
    matched_candidates = set()
    matched_encuestas = set()

    for e_idx, encuesta in enumerate(encuesta_lista):
        nombre_encuesta = normalize(encuesta.get("nombre", ""))
        best_match = None
        best_ratio = 0.0

        # Buscar candidato más parecido
        for i, name in enumerate(names):
            ratio = difflib.SequenceMatcher(None, nombre_encuesta, name).ratio()
            if ratio > best_ratio:
                best_ratio = ratio
                best_match = i

        # Aceptar match si supera umbral
        if best_match is not None and best_ratio >= threshold:
            if best_match in matched_candidates:
                raise ValueError(f"Candidato {candidates[best_match]['name']} duplicado")

            candidates[best_match]["votes"] = float(encuesta.get("votos", 0) or 0)
            candidates[best_match]["matched_from"] = encuesta.get("nombre")
            candidates[best_match]["match_quality"] = round(best_ratio, 3)

            matched_candidates.add(best_match)
            matched_encuestas.add(e_idx)

    # Candidatos sin match → votos 0
    for i, c in enumerate(candidates):
        if i not in matched_candidates:
            c["votes"] = float(c.get("votes", 0) or 0)
            c["matched_from"] = None
            c["match_quality"] = 0.0

    # Verificar que todas las encuestas fueron pareadas
    unmatched = [enc["nombre"] for idx, enc in enumerate(encuesta_lista) if idx not in matched_encuestas]
    if unmatched:
        print(f"⚠️ No se pudo hacer match: {', '.join(unmatched[:3])}")

    return candidates


def fetch_emol_csv(distrito: str) -> pd.DataFrame:
    """Descarga CSV de Emol y filtra por distrito."""
    try:
        df = pd.read_csv(EMOL_CSV_URL, encoding="utf-8")
        codigo_zona = int("60" + str(distrito).zfill(2))
        df_filtered = df[df["zona"] == codigo_zona]
        return df_filtered
    except Exception as e:
        print(f"⚠️ Error descargando CSV: {e}")
        return pd.DataFrame()


def get_distritos() -> List[Dict[str, Any]]:
    """
    Obtiene lista de todos los distritos con su nombre real desde DB_URL.
    Estructura: [{"numero": 1, "nombre": "Distrito 1 - Región de Arica y Parinacota"}, ...]
    """
    try:
        print("Obteniendo distritos desde DB_URL de EMOL...")
        r = requests.get(DB_URL, timeout=10)
        r.raise_for_status()
        data = r.json()
        
        distritos_list = []
        
        # dbzonas contiene los distritos electorales (6001-6028)
        dbzonas = data.get("dbzonas", {})
        dbregiones = data.get("dbregiones", {})
        
        for codigo, info in dbzonas.items():
            # Filtrar solo los distritos (códigos que empiezan con 60 y tienen 4 dígitos)
            if codigo.startswith("60") and len(codigo) == 4:
                try:
                    num_distrito = int(codigo[2:])  # Extraer número del distrito (01-28)
                    
                    if 1 <= num_distrito <= 28:
                        # Obtener nombre del distrito
                        nombre_distrito = info.get("n", "")
                        
                        # Obtener región desde dbregiones
                        codigo_region = info.get("r", "")
                        nombre_region = dbregiones.get(codigo_region, {}).get("n", "")
                        
                        # Construir nombre completo: "Distrito X - Región de ..."
                        if nombre_region:
                            nombre_completo = f"Distrito {num_distrito} - {nombre_region}"
                        else:
                            nombre_completo = f"Distrito {num_distrito}"
                        
                        distritos_list.append({
                            "numero": num_distrito,
                            "nombre": nombre_completo
                        })
                except (ValueError, TypeError):
                    pass
        
        # Ordenar por número de distrito
        distritos_list.sort(key=lambda x: x["numero"])
        
        if len(distritos_list) > 0:
            print(f"✅ {len(distritos_list)} distritos obtenidos desde DB_URL")
            return distritos_list
        else:
            print("⚠️ No se encontraron distritos en DB_URL, usando valores por defecto")
            return [{"numero": i, "nombre": f"Distrito {i}"} for i in range(1, 29)]
        
    except Exception as e:
        print(f"❌ Error obteniendo distritos: {e}")
        return [{"numero": i, "nombre": f"Distrito {i}"} for i in range(1, 29)]


# ============================================================
# SERVICIO ELECTORAL
# ============================================================

class DiputadosService:
    """Servicio para cálculos electorales."""
    
    def __init__(self):
        self.encuesta = load_encuesta()
        self.encuestas_by_d = {
            str(i): self.encuesta.get(f"D{i}", []) 
            for i in range(1, 29)
        }

    def get_emol_csv(self, distrito: str) -> Dict[str, Any]:
        """Obtiene candidatos de un distrito con votos de encuesta."""
        distrito = normalize_district(distrito)
        df = fetch_emol_csv(distrito)
        
        if df.empty:
            return {"error": f"No se encontraron datos para distrito {distrito}"}

        seats = get_seats_for_district_api(distrito)
        encuesta_lista = self.encuestas_by_d.get(str(distrito), [])

        # Construir candidatos
        candidates = [
            {
                "id": str(row.get("id_foto", idx)),
                "name": row["nombre"],
                "votes": 0.0,
                "party_id": row.get("cupo", ""),
            }
            for idx, (_, row) in enumerate(df.iterrows())
        ]

        # Pactos y partidos
        pact_ids = sorted(set(df["pacto"].dropna().unique()))
        pacts = [Pact(id=p, name=p) for p in pact_ids]

        party_ids = sorted(set(df["cupo"].dropna().unique()))
        parties = [
            Party(
                id=pid,
                name=pid,
                votes=0,
                pact_id=next((df[df["cupo"] == pid]["pacto"].iloc[0] for _ in [None] if True), None)
            )
            for pid in party_ids
        ]

        # Asignar votos desde encuesta
        candidates_with_votes = assign_votes_to_candidates(candidates, encuesta_lista, threshold=0.8)

        return {
            "distrito": distrito,
            "seats": seats,
            "threshold": 0.0,
            "level": "pact",
            "pacts": [asdict(p) for p in pacts],
            "parties": [asdict(p) for p in parties],
            "candidates": candidates_with_votes,
        }

    def compute_dhondt(self, distrito: str) -> Dict[str, Any]:
        """Calcula D'Hondt completo para un distrito."""
        distrito = normalize_district(distrito)
        df = fetch_emol_csv(distrito)
        print(distrito)
        if df.empty:
            return {"error": f"No hay datos para distrito {distrito}"}

        seats = get_seats_for_district_api(distrito)
        encuesta_lista = self.encuestas_by_d.get(str(distrito), [])

        # Candidatos
        candidates = []
        for idx, (_, row) in enumerate(df.iterrows()):
            nombre_emol = normalize(row.get("nombre", ""))
            best_ratio = 0.0
            best_enc = None

            for enc in encuesta_lista:
                nombre_enc = normalize(enc.get("nombre", ""))
                ratio = difflib.SequenceMatcher(None, nombre_emol, nombre_enc).ratio()
                if ratio > best_ratio:
                    best_ratio = ratio
                    best_enc = enc


            votos = float(best_enc["votos"]) if best_ratio >= 0.8 else 0.0

            candidates.append(Candidate(
                id=str(row.get("id_foto", idx)),
                name=row.get("nombre"),
                party_id=row.get("cupo"),
                votes=votos,
            ))

        # Agrupar por partido
        parties = []
        seen_parties = set()
        for _, row in df.iterrows():
            partido = row.get("cupo")
            pacto = row.get("pacto")
            if partido and partido not in seen_parties:
                votos = sum(c.votes for c in candidates if c.party_id == partido)
                seen_parties.add(partido)
                parties.append(Party(id=partido, name=partido, pact_id=pacto, votes=votos))

        # Agrupar por pacto
        pacts = []
        pact_names = df["pacto"].dropna().unique().tolist()
        for name in pact_names:
            votos = sum(p.votes for p in parties if p.pact_id == name)
            pacts.append(Pact(id=name, name=name, votes=votos))

        # Aplicar D'Hondt a pactos
        pact_votes = {p.id: p.votes for p in pacts if p.id}
        pact_alloc = dhondt_alloc(pact_votes, seats)

        # Aplicar D'Hondt a partidos dentro de cada pacto
        winners = []
        for pacto, n_seats in pact_alloc.items():
            sub_parties = [p for p in parties if p.pact_id == pacto]
            sub_votes = {p.id: p.votes for p in sub_parties if p.votes > 0}
            if not sub_votes:
                continue
            sub_alloc = dhondt_alloc(sub_votes, n_seats)
            for pid, n in sub_alloc.items():
                candidatos = sorted(
                    [c for c in candidates if c.party_id == pid],
                    key=lambda x: x.votes,
                    reverse=True,
                )[:n]
                winners.extend(candidatos)

        # Calcular totales
        total_votos = sum(pact_votes.values())
        
        # Construir resultado por pacto con candidatos electos
        resultado_por_pacto = []
        for pacto in sorted(pact_alloc.keys(), key=lambda x: pact_alloc[x], reverse=True):
            candidatos_pacto = [
                c for c in winners 
                if next((p.pact_id for p in parties if p.id == c.party_id), None) == pacto
            ]
            votos_pacto = pact_votes.get(pacto, 0)
            escanos_pacto = pact_alloc[pacto]
            
            porcentaje = (votos_pacto / total_votos * 100) if total_votos > 0 else 0
            
            # Obtener nombre completo del pacto
            pacto_nombre = get_pacto_nombre(pacto)
            
            resultado_por_pacto.append({
                "pacto": pacto_nombre,
                "pacto_id": pacto,
                "candidatos_electos": [
                    {
                        "nombre": c.name,
                        "partido": c.party_id,
                        "votos": c.votes
                    }
                    for c in sorted(candidatos_pacto, key=lambda x: x.votes, reverse=True)
                ],
                "votos": votos_pacto,
                "porcentaje": round(porcentaje, 1),
                "escanos": escanos_pacto
            })
        
        # Agregar pactos sin escaños
        for p in pacts:
            if p.id not in pact_alloc:
                votos_pacto = p.votes
                porcentaje = (votos_pacto / total_votos * 100) if total_votos > 0 else 0
                pacto_nombre = get_pacto_nombre(p.id)
                resultado_por_pacto.append({
                    "pacto": pacto_nombre,
                    "pacto_id": p.id,
                    "candidatos_electos": [],
                    "votos": votos_pacto,
                    "porcentaje": round(porcentaje, 1),
                    "escanos": 0
                })

        # Todos los candidatos del CSV (con o sin votos de encuesta)
        todos_candidatos = [
            {
                "nombre": c.name,
                "partido": c.party_id,
                "pacto": next((p.pact_id for p in parties if p.id == c.party_id), ""),
                "votos": c.votes
            }
            for c in candidates
        ]

        result = {
            "distrito": distrito,
            "total_escanos": seats,
            "total_votos": total_votos,
            "pactos": PACTOS_MAPPING,
            "resultado_por_pacto": resultado_por_pacto,
            "candidatos_cargados": {
                "total": len(todos_candidatos),
                "candidatos": sorted(todos_candidatos, key=lambda x: x["votos"], reverse=True)
            },
            "elected_candidates": [
                {
                    "id": c.id,
                    "name": c.name,
                    "party_id": c.party_id,
                    "party_name": c.party_id,
                    "pact_id": next((p.pact_id for p in parties if p.id == c.party_id), None),
                    "pact_name": get_pacto_nombre(
                        next((p.pact_id for p in parties if p.id == c.party_id), None) or ""
                    ),
                    "votes": c.votes,
                }
                for c in sorted(winners, key=lambda x: x.votes, reverse=True)
            ],
        }

        return result

    def resumen_nacional(self) -> Dict[str, Any]:
        """Calcula resumen nacional de todos los distritos."""
        distritos = list(range(1, 29))
        resumen_pactos: Dict[str, Dict[str, Any]] = {}
        resumen_partidos: Dict[str, Dict[str, Any]] = {}

        for d in distritos:
            df = fetch_emol_csv(str(d))
            if df.empty:
                continue

            seats = get_seats_for_district_api(str(d))
            encuesta_lista = self.encuestas_by_d.get(str(d), [])
            if not encuesta_lista:
                print(f"⚠️ No se encontró encuesta para el distrito {d}")
                continue

            # Asignar votos
            candidates = []
            matched_encuestas = set()

            for idx, (_, row) in enumerate(df.iterrows()):
                nombre_emol = normalize(row.get("nombre") or "")
                mejor_ratio = 0
                best_idx = None

                for e_idx, enc in enumerate(encuesta_lista):
                    nombre_enc = normalize(enc["nombre"])
                    ratio = difflib.SequenceMatcher(None, nombre_emol, nombre_enc).ratio()
                    if ratio > mejor_ratio:
                        mejor_ratio = ratio
                        best_idx = e_idx

                if best_idx is not None and mejor_ratio >= 0.8:
                    enc = encuesta_lista[best_idx]
                    votos = float(enc["votos"])
                    matched_encuestas.add(best_idx)
                else:
                    votos = 0

                candidates.append(Candidate(
                    id=str(row.get("id_foto", idx)),
                    name=row["nombre"],
                    party_id=row.get("cupo"),
                    votes=votos,
                ))

            # Agrupar por partido y pacto
            parties = []
            for partido, grupo in df.groupby("cupo"):
                pacto = grupo["pacto"].iloc[0] if "pacto" in grupo and pd.notna(grupo["pacto"].iloc[0]) else None
                votos = sum(c.votes for c in candidates if c.party_id == partido)
                parties.append(Party(id=partido, name=partido, votes=votos, pact_id=pacto))

            pacts = []
            for pacto, grupo in df.groupby("pacto"):
                votos = sum(p.votes for p in parties if p.pact_id == pacto)
                pacts.append(Pact(id=pacto, name=pacto, votes=votos))

            # Aplicar D'Hondt
            pact_votes = {p.id: p.votes for p in pacts if p.id}
            pact_alloc = dhondt_alloc(pact_votes, seats)

            for pacto, n_seats in pact_alloc.items():
                sub_parties = [p for p in parties if p.pact_id == pacto]
                sub_votes = {p.id: p.votes for p in sub_parties if p.votes > 0}
                if not sub_votes:
                    continue
                sub_alloc = dhondt_alloc(sub_votes, n_seats)

                # Acumular nacional
                resumen_pactos.setdefault(pacto, {"escaños": 0, "votos": 0})
                resumen_pactos[pacto]["escaños"] += n_seats
                resumen_pactos[pacto]["votos"] += pact_votes.get(pacto, 0)

                for pid, n in sub_alloc.items():
                    resumen_partidos.setdefault(pid, {"escaños": 0, "votos": 0, "pacto": pacto})
                    resumen_partidos[pid]["escaños"] += n
                    resumen_partidos[pid]["votos"] += next((p.votes for p in parties if p.id == pid), 0)

        # Calcular porcentajes
        total_votos = sum(v["votos"] for v in resumen_pactos.values())
        for pacto in resumen_pactos.values():
            if total_votos > 0:
                pacto["porcentaje"] = round(100 * pacto["votos"] / total_votos, 2)

        result = {
            "total_votos": total_votos,
            "pactos": [
                {"id": k, **v}
                for k, v in sorted(resumen_pactos.items(), key=lambda x: x[1]["escaños"], reverse=True)
            ],
            "partidos": [
                {"id": k, **v}
                for k, v in sorted(resumen_partidos.items(), key=lambda x: x[1]["escaños"], reverse=True)
            ],
        }

        return result

    def get_resultado_por_pacto(self, distrito: str) -> Dict[str, Any]:
        """
        Obtiene resultado formateado por pacto (como tabla frontend).
        Estructura: Array de pactos con candidatos electos, votos y escaños.
        """
        distrito = normalize_district(distrito)
        
        # Obtener datos D'Hondt
        dhondt_result = self.compute_dhondt(distrito)
        
        if "error" in dhondt_result:
            return dhondt_result
        
        total_escaños = sum(p["seats"] for p in dhondt_result.get("allocation_level", []))
        total_votos = dhondt_result.get("total_votes", 0)
        
        # Organizar candidatos por pacto
        candidatos_por_pacto = {}
        for candidate in dhondt_result.get("elected_candidates", []):
            pact_id = candidate.get("pact_id", "Sin pacto")
            pact_name = candidate.get("pact_name", "Sin pacto")
            
            if pact_id not in candidatos_por_pacto:
                candidatos_por_pacto[pact_id] = {
                    "pact_id": pact_id,
                    "pact_name": pact_name,
                    "candidatos": [],
                    "votos": 0,
                    "escaños": 0
                }
            
            candidatos_por_pacto[pact_id]["candidatos"].append({
                "nombre": candidate.get("name", ""),
                "partido": candidate.get("party_id", ""),
                "votos": candidate.get("votes", 0)
            })
            candidatos_por_pacto[pact_id]["votos"] += candidate.get("votes", 0)
            candidatos_por_pacto[pact_id]["escaños"] += 1
        
        # Calcular porcentajes y ordenar por votos
        for pacto in candidatos_por_pacto.values():
            if total_votos > 0:
                pacto["porcentaje"] = round(100 * pacto["votos"] / total_votos, 1)
            else:
                pacto["porcentaje"] = 0.0
        
        # Convertir a lista ordenada por escaños (descendente)
        resultado = sorted(
            candidatos_por_pacto.values(),
            key=lambda x: x["escaños"],
            reverse=True
        )
        
        return {
            "distrito": distrito,
            "total_escaños": total_escaños,
            "total_votos": total_votos,
            "pactos": resultado
        }

    def get_todos_candidatos(self) -> List[Dict[str, Any]]:
        """
        Obtiene todos los candidatos de todos los distritos que tienen votos.
        Estructura: Array con nombre, partido, pacto, distrito y votos.
        """
        # Mapeo de colores por pacto (basado en imagen mostrada)
        colores_pactos = {
            "Unidad por Chile (FA, PS, DC, PPD, PL, PR)": "#FF1493",  # Rosa
            "Chile Grande y Unido (UDI, RN, Evópoli, Demócratas)": "#ADD8E6",  # Azul
            "Cambio por Chile (PSC, PNL, REP)": "#FFFF99",  # Amarillo
            "Movimiento Amarillos por Chile": "#FFFF99",  # Amarillo
            "Partido de la Gente": "#D2B48C",  # Beige/Marrón
            "Verdes, Regionalistas y Humanistas (FRVS, AH)": "#90EE90",  # Verde claro
        }
        
        todos_candidatos = []
        
        # Iterar sobre todos los distritos (1-28)
        for distrito_num in range(1, 29):
            try:
                df = fetch_emol_csv(str(distrito_num))
                
                if df.empty:
                    continue
                
                encuesta_lista = self.encuestas_by_d.get(str(distrito_num), [])
                
                # Procesar cada candidato
                for idx, (_, row) in enumerate(df.iterrows()):
                    nombre = row.get("nombre", "")
                    partido = row.get("cupo", "")
                    pacto = row.get("pacto", "")
                    
                    # Buscar votos desde encuesta
                    votos = 0.0
                    nombre_norm = normalize(nombre)
                    
                    for enc in encuesta_lista:
                        nombre_enc = normalize(enc.get("nombre", ""))
                        ratio = difflib.SequenceMatcher(None, nombre_norm, nombre_enc).ratio()
                        if ratio > 0.8:
                            votos = float(enc.get("votos", 0) or 0)
                            break
                    
                    # Solo incluir si tiene votos
                    if votos > 0:
                        # Obtener color del pacto
                        color = colores_pactos.get(pacto, "#CCCCCC")  # Gris por defecto
                        
                        todos_candidatos.append({
                            "nombre": nombre,
                            "partido": partido,
                            "pacto": pacto,
                            "distrito": distrito_num,
                            "votos": votos,
                            "color": color
                        })
            
            except Exception as e:
                print(f"⚠️ Error procesando distrito {distrito_num}: {e}")
                continue
        
        # Ordenar por votos (descendente)
        todos_candidatos.sort(key=lambda x: x["votos"], reverse=True)
        
        return todos_candidatos


# Instancia global
diputados_service = DiputadosService()