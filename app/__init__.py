from flask import Flask
from flask_cors import CORS
from flask_restx import Api
from config import config

def create_app(config_name='development'):
    """Factory pattern para crear la aplicación Flask"""
    app = Flask(__name__)
    
    # Cargar configuración
    app.config.from_object(config[config_name])
    app.config['JSON_AS_ASCII'] = False
    app.config['RESTX_JSON'] = {'ensure_ascii': False}
    
    # Habilitar CORS
    CORS(app, resources={r"/*": {"origins": "*"}})
    
    # Crear API con Flask-RESTX (genera Swagger en /docs)
    api = Api(
        app,
        version='1.0',
        title='API Electoral - D\'Hondt',
        description='Backend para cálculos electorales con método D\'Hondt',
        doc='/docs'
    )
    
    # Importar y registrar endpoints
    from app.api.routes import ns
    api.add_namespace(ns, path='/api')
    
    return app
