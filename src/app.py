from flask import Flask
import os
import sys

# Add the src directory to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def create_app():
    app = Flask(__name__)

    # Basic configuration
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key')
    app.config['DATABASE_PATH'] = os.environ.get('DATABASE_PATH', '/config/stash_manager.db')

    @app.route('/')
    def index():
        return '''
        <h1>Stash Manager</h1>
        <p>Welcome to Stash Manager Development Environment</p>
        <p>The application is running in development mode.</p>
        '''

    @app.route('/health')
    def health():
        return {'status': 'healthy', 'service': 'stash-manager'}

    return app

# Create the app instance for Gunicorn
app = create_app()

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5001)