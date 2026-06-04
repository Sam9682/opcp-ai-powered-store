"""Main application routes"""
from flask import Blueprint, render_template, session, redirect, url_for, request, send_from_directory
import os

# Use PostgreSQL by default
from ..database_postgres import db_manager
from ..config_postgres import DOMAIN, PLTF_NAME, APP_VERSION

main_bp = Blueprint('main', __name__)

@main_bp.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('main.dashboard'))
    return render_template('login.html', DOMAIN=DOMAIN, PLTF_NAME=PLTF_NAME, APP_VERSION=APP_VERSION)

@main_bp.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('main.index'))
    
    # Get username for admin check
    user = db_manager.execute_query(
        'SELECT username FROM users WHERE id = %s', 
        (session['user_id'],), fetch_one=True
    )
    username = user[0] if user else ''
    
    # Get applications based on user role with swautomorph_url from deployments
    applications_raw = db_manager.execute_query('''SELECT a.id, a.name, ua.url, a.description, a.git_url, a.git_local_url, a.git_repo_size, 
               a.docker_build_duration, a.docker_start_duration, a.docker_stop_duration, a.docker_ps_duration,
               d.swautomorph_url
        FROM applications a
        JOIN user_applications ua ON a.id = ua.application_id
        LEFT JOIN deployments d ON d.user_id = %s AND d.application_name = a.name
        WHERE ua.user_id = %s
        ORDER BY a.name
    ''', (session['user_id'], session['user_id']), fetch_all=True)
    
    # Use URLs directly from the database table user_applications
    applications = []
    for app in applications_raw:
        app_id, app_name, user_appli_url, description, git_url, git_local_url, git_repo_size, docker_build_duration, docker_start_duration, docker_stop_duration, docker_ps_duration, deployment_url = app
        
        # Use the URL stored in the database instead of calculating it
        applications.append((app_id, app_name, user_appli_url, description, git_url, git_local_url, git_repo_size or 50, docker_build_duration, docker_start_duration or 30, docker_stop_duration or 10, docker_ps_duration, deployment_url or 'Not yet deployed'))
    
    # Get SSO token for the user
    sso_token = session.get('sso_token', '')
    
    return render_template('dashboard.html', applications=applications, username=username, sso_token=sso_token, user_id=session['user_id'], DOMAIN=DOMAIN, PLTF_NAME=PLTF_NAME, APP_VERSION=APP_VERSION)

@main_bp.route('/set_language/<language>')
def set_language(language):
    if language in ['en', 'fr']:
        session['language'] = language
    return redirect(request.referrer or url_for('main.index'))

@main_bp.route('/docs')
def docs():
    # Get list of .md files in docs directory
    docs_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'docs')
    md_files = []
    if os.path.exists(docs_dir):
        for file in os.listdir(docs_dir):
            if file.endswith('.md'):
                md_files.append(file)
    
    return render_template('docs.html', md_files=sorted(md_files))

@main_bp.route('/docs/<filename>')
def view_doc(filename):
    # Security check - only allow .md files
    if not filename.endswith('.md'):
        return "Invalid file type", 400
    
    docs_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'docs')
    file_path = os.path.join(docs_dir, filename)
    
    if not os.path.exists(file_path):
        return "File not found", 404
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        return render_template('doc_viewer.html', filename=filename, content=content)
    except Exception as e:
        return f"Error reading file: {str(e)}", 500

@main_bp.route('/userguide')
def userguide():
    """Serve the user guide with language support"""
    docs_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'docs')
    file_path = os.path.join(docs_dir, 'USER_GUIDE.md')
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        return render_template('doc_viewer.html', filename='USER_GUIDE.md', content=content)
    except Exception as e:
        return f"Error reading file: {str(e)}", 500

@main_bp.route('/favicon.ico')
def favicon():
    """Serve favicon.ico"""
    try:
        static_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'static')
        return send_from_directory(static_dir, 'favicon.ico', mimetype='image/vnd.microsoft.icon')
    except Exception as e:
        print(f"Error serving favicon: {e}")
        return '', 404

@main_bp.route('/.well-known/pki-validation/<filename>')
def ssl_validation(filename):
    """Serve SSL certificate validation files"""
    static_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'static')
    validation_dir = os.path.join(static_dir, '.well-known', 'pki-validation')
    return send_from_directory(validation_dir, filename)