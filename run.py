import os
from app import create_app

if __name__ == '__main__':
    config_name = os.getenv('FLASK_ENV', 'development')
    app = create_app(config_name)
    
    # Toma el puerto de la variable PORT (Render lo define), usa 5000 solo si no está
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)