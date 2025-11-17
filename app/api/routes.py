# app/api/routes.py
from flask import Blueprint, request, jsonify, make_response
from flask_restx import Api, Resource, fields, Namespace
from app.services.diputados_service import diputados_service, get_distritos

# Crear blueprint
api_bp = Blueprint('api', __name__, url_prefix='/api')

# Crear namespace para organizar endpoints
ns = Namespace('', description='Endpoints electorales')

# ============================================================
# MODELOS PARA DOCUMENTACIÓN SWAGGER
# ============================================================

candidato_model = ns.model('Candidato', {
    'id': fields.String(required=True),
    'name': fields.String(required=True),
    'votes': fields.Float(),
    'party_id': fields.String(),
    'matched_from': fields.String(),
    'match_quality': fields.Float()
})

partido_model = ns.model('Partido', {
    'id': fields.String(required=True),
    'name': fields.String(required=True),
    'votes': fields.Float(),
    'pact_id': fields.String()
})

resultado_dhondt_model = ns.model('ResultadoDHondt', {
    'distrito': fields.String(required=True),
    'total_votes': fields.Float(),
    'allocation_level': fields.List(fields.Raw()),
    'parties': fields.List(fields.Raw()),
    'elected_candidates': fields.List(fields.Raw())
})

# ============================================================
# ENDPOINTS
# ============================================================

@ns.route('/emol/<string:distrito>')
class EmolResource(Resource):
    """Candidatos de Emol con votos de encuesta"""
    
    @ns.doc(
        'get_emol_csv',
        params={
            'distrito': {
                'description': 'Número del distrito (1-28). Ej: 10',
                'in': 'path',
                'type': 'string',
                'required': True,
                'example': '10'
            }
        }
    )
    @ns.response(200, 'Éxito', fields.Raw())
    @ns.response(404, 'Distrito no encontrado')
    @ns.response(500, 'Error del servidor')
    def get(self, distrito):
        """Obtiene candidatos de Emol con votos de encuesta para un distrito."""
        try:
            result = diputados_service.get_emol_csv(distrito)
            response = make_response(jsonify(result))
            response.headers["Content-Type"] = "application/json; charset=utf-8"
            return response
        except Exception as e:
            ns.abort(500, str(e))


@ns.route('/dhondt/<string:distrito>')
class DhondtResource(Resource):
    """Cálculo D'Hondt por distrito"""
    
    @ns.doc(
        'compute_dhondt',
        params={
            'distrito': {
                'description': 'Número del distrito (1-28). Ej: 10, D10, d10',
                'in': 'path',
                'type': 'string',
                'required': True,
                'example': '10'
            }
        }
    )
    @ns.response(200, 'Cálculo completado', resultado_dhondt_model)
    @ns.response(404, 'Distrito no encontrado')
    @ns.response(500, 'Error del servidor')
    def get(self, distrito):
        """Calcula D'Hondt para un distrito específico. Acepta '10' o 'D10'."""
        try:
            result = diputados_service.compute_dhondt(distrito)
            response = make_response(jsonify(result))
            response.headers["Content-Type"] = "application/json; charset=utf-8"
            return response
        except Exception as e:
            ns.abort(500, str(e))


@ns.route('/dhondt')
class DhondtPostResource(Resource):
    """Cálculo D'Hondt por POST"""
    
    distrito_model = ns.model('DistritoRequest', {
        'distrito': fields.String(
            required=True,
            description='Número del distrito (1-28). Ej: 10',
            example='10'
        )
    })
    
    @ns.doc('compute_dhondt_post')
    @ns.expect(distrito_model)
    @ns.response(200, 'Cálculo completado', resultado_dhondt_model)
    @ns.response(400, 'Parámetros inválidos')
    @ns.response(500, 'Error del servidor')
    def post(self):
        """Calcula D'Hondt enviando el distrito en el body JSON."""
        try:
            data = request.get_json(force=True)
            distrito = str(data.get("distrito", "10"))
            result = diputados_service.compute_dhondt(distrito)
            response = make_response(jsonify(result))
            response.headers["Content-Type"] = "application/json; charset=utf-8"
            return response
        except Exception as e:
            ns.abort(500, str(e))


@ns.route('/resumen')
class ResumenResource(Resource):
    """Resumen nacional de todos los distritos"""
    
    @ns.doc('resumen_nacional')
    @ns.response(200, 'Resumen completado', fields.Raw())
    @ns.response(500, 'Error del servidor')
    def get(self):
        """Calcula resumen nacional agregando resultados de todos los 28 distritos."""
        try:
            result = diputados_service.resumen_nacional()
            response = make_response(jsonify(result))
            response.headers["Content-Type"] = "application/json; charset=utf-8"
            return response
        except Exception as e:
            ns.abort(500, str(e))


@ns.route('/encuestas')
class EncuestasResource(Resource):
    """Encuestas cargadas desde API externa"""
    
    @ns.doc('get_encuestas')
    @ns.response(200, 'Encuestas disponibles', fields.Raw())
    @ns.response(500, 'Error del servidor')
    def get(self):
        """Obtiene todas las encuestas cargadas desde la API externa."""
        try:
            encuestas = diputados_service.encuesta
            response = make_response(jsonify(encuestas))
            response.headers["Content-Type"] = "application/json; charset=utf-8"
            return response
        except Exception as e:
            ns.abort(500, str(e))


@ns.route('/resultado/<string:distrito>')
class ResultadoResource(Resource):
    """Resultado por pacto - Formato frontend (tabla)"""
    
    @ns.doc(
        'get_resultado_por_pacto',
        params={
            'distrito': {
                'description': 'Número del distrito (1-28). Ej: 10',
                'in': 'path',
                'type': 'string',
                'required': True,
                'example': '10'
            }
        }
    )
    @ns.response(200, 'Resultado formateado para frontend', fields.Raw())
    @ns.response(404, 'Distrito no encontrado')
    @ns.response(500, 'Error del servidor')
    def get(self, distrito):
        """
        Obtiene el resultado electoral por pacto, formateado para mostrar en tabla.
        Estructura: Array de pactos con candidatos electos, votos totales y escaños.
        """
        try:
            result = diputados_service.get_resultado_por_pacto(distrito)
            response = make_response(jsonify(result))
            response.headers["Content-Type"] = "application/json; charset=utf-8"
            return response
        except Exception as e:
            ns.abort(500, str(e))


@ns.route('/distritos')
class DistritosResource(Resource):
    """Lista de todos los distritos electorales"""
    
    @ns.doc('get_distritos')
    @ns.response(200, 'Lista de distritos', fields.Raw())
    @ns.response(500, 'Error del servidor')
    def get(self):
        """
        Obtiene la lista de todos los distritos electorales (1-28).
        Cada distrito incluye número y nombre para usar en expandibles/dropdowns.
        
        Respuesta ejemplo:
        [
          {"numero": 1, "nombre": "Distrito 1 - Región de Arica y Parinacota"},
          {"numero": 2, "nombre": "Distrito 2 - Región de Tarapacá"},
          ...
          {"numero": 28, "nombre": "Distrito 28 - Región de Magallanes"}
        ]
        """
        try:
            distritos = get_distritos()
            response = make_response(jsonify(distritos))
            response.headers["Content-Type"] = "application/json; charset=utf-8"
            return response
        except Exception as e:
            ns.abort(500, str(e))


@ns.route('/candidatos')
class CandidatosResource(Resource):
    """Lista de todos los candidatos electorales nacionales"""
    
    @ns.doc('get_candidatos')
    @ns.response(200, 'Lista de candidatos', fields.Raw())
    @ns.response(500, 'Error del servidor')
    def get(self):
        """
        Obtiene la lista de todos los candidatos de todos los distritos (1-28).
        Cada candidato incluye: nombre, partido, pacto, distrito y votos.
        
        Estructura respuesta:
        [
          {
            "nombre": "Gonzalo Winter",
            "partido": "FA",
            "pacto": "Unidad por Chile (FA, PS, DC, PPD, PL, PR)",
            "distrito": 10,
            "votos": 45000,
            "color": "#FF1493"
          },
          ...
        ]
        """
        try:
            result = diputados_service.get_todos_candidatos()
            response = make_response(jsonify(result))
            response.headers["Content-Type"] = "application/json; charset=utf-8"
            return response
        except Exception as e:
            ns.abort(500, str(e))


