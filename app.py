# app.py - Flask Backend für Bautagebuch
from flask import Flask, render_template, request, jsonify, send_file
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, date
import os
import json
from werkzeug.utils import secure_filename
import uuid

app = Flask(__name__)

# Konfiguration
app.config['SECRET_KEY'] = 'bautagebuch-secret-key-2024'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///bautagebuch.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# Datenbank initialisieren
db = SQLAlchemy(app)

# Upload-Ordner erstellen
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Datenbankmodelle
class Project(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False, default='Mein Bauprojekt')
    builder_name = db.Column(db.String(200), nullable=False, default='Max Mustermann')
    start_date = db.Column(db.Date, nullable=False, default=date.today)
    status = db.Column(db.String(50), nullable=False, default='In Bearbeitung')
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Beziehungen
    entries = db.relationship('Entry', backref='project', lazy=True, cascade='all, delete-orphan')
    photos = db.relationship('Photo', backref='project', lazy=True, cascade='all, delete-orphan')

class Entry(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, nullable=False)
    weather = db.Column(db.String(50))
    temperature = db.Column(db.Float)
    content = db.Column(db.Text, nullable=False)
    workers_count = db.Column(db.Integer)
    materials = db.Column(db.Text)
    work_hours = db.Column(db.Float)
    costs = db.Column(db.Float)
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Foreign Key
    project_id = db.Column(db.Integer, db.ForeignKey('project.id'), nullable=False)

class Photo(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(255), nullable=False)
    original_filename = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text)
    date_taken = db.Column(db.Date, default=date.today)
    file_size = db.Column(db.Integer)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Foreign Key
    project_id = db.Column(db.Integer, db.ForeignKey('project.id'), nullable=False)

# Hilfsfunktionen
def allowed_file(filename):
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'bmp', 'webp'}
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_or_create_project():
    """Holt das erste Projekt oder erstellt ein neues"""
    project = Project.query.first()
    if not project:
        project = Project()
        db.session.add(project)
        db.session.commit()
    return project

# Routes
@app.route('/')
def index():
    """Hauptseite - zeigt das HTML-Frontend"""
    return render_template('index.html')

@app.route('/api/project', methods=['GET'])
def get_project():
    """Projektinformationen abrufen"""
    project = get_or_create_project()
    return jsonify({
        'id': project.id,
        'name': project.name,
        'builder_name': project.builder_name,
        'start_date': project.start_date.strftime('%Y-%m-%d'),
        'status': project.status,
        'description': project.description,
        'created_at': project.created_at.strftime('%Y-%m-%d %H:%M:%S')
    })

@app.route('/api/project', methods=['PUT'])
def update_project():
    """Projektinformationen aktualisieren"""
    project = get_or_create_project()
    data = request.get_json()
    
    project.name = data.get('name', project.name)
    project.builder_name = data.get('builder_name', project.builder_name)
    
    if 'start_date' in data:
        project.start_date = datetime.strptime(data['start_date'], '%Y-%m-%d').date()
    
    project.status = data.get('status', project.status)
    project.description = data.get('description', project.description)
    
    db.session.commit()
    return jsonify({'success': True, 'message': 'Projekt aktualisiert'})

@app.route('/api/entries', methods=['GET'])
def get_entries():
    """Alle Einträge abrufen"""
    project = get_or_create_project()
    entries = Entry.query.filter_by(project_id=project.id).order_by(Entry.date.desc()).all()
    
    entries_data = []
    for entry in entries:
        entries_data.append({
            'id': entry.id,
            'date': entry.date.strftime('%Y-%m-%d'),
            'weather': entry.weather,
            'temperature': entry.temperature,
            'content': entry.content,
            'workers_count': entry.workers_count,
            'materials': entry.materials,
            'work_hours': entry.work_hours,
            'costs': entry.costs,
            'notes': entry.notes,
            'created_at': entry.created_at.strftime('%Y-%m-%d %H:%M:%S')
        })
    
    return jsonify(entries_data)

@app.route('/api/entries', methods=['POST'])
def create_entry():
    """Neuen Eintrag erstellen"""
    project = get_or_create_project()
    data = request.get_json()
    
    try:
        entry = Entry(
            project_id=project.id,
            date=datetime.strptime(data['date'], '%Y-%m-%d').date(),
            weather=data.get('weather'),
            temperature=float(data['temperature']) if data.get('temperature') else None,
            content=data['content'],
            workers_count=int(data['workers_count']) if data.get('workers_count') else None,
            materials=data.get('materials'),
            work_hours=float(data['work_hours']) if data.get('work_hours') else None,
            costs=float(data['costs']) if data.get('costs') else None,
            notes=data.get('notes')
        )
        
        db.session.add(entry)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Eintrag erstellt',
            'entry_id': entry.id
        })
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/api/entries/<int:entry_id>', methods=['DELETE'])
def delete_entry(entry_id):
    """Eintrag löschen"""
    entry = Entry.query.get_or_404(entry_id)
    db.session.delete(entry)
    db.session.commit()
    return jsonify({'success': True, 'message': 'Eintrag gelöscht'})

@app.route('/api/photos', methods=['GET'])
def get_photos():
    """Alle Fotos abrufen"""
    project = get_or_create_project()
    photos = Photo.query.filter_by(project_id=project.id).order_by(Photo.date_taken.desc()).all()
    
    photos_data = []
    for photo in photos:
        photos_data.append({
            'id': photo.id,
            'filename': photo.filename,
            'original_filename': photo.original_filename,
            'description': photo.description,
            'date_taken': photo.date_taken.strftime('%Y-%m-%d'),
            'file_size': photo.file_size,
            'url': f'/static/uploads/{photo.filename}'
        })
    
    return jsonify(photos_data)

@app.route('/api/photos', methods=['POST'])
def upload_photo():
    """Foto hochladen"""
    if 'file' not in request.files:
        return jsonify({'success': False, 'error': 'Keine Datei ausgewählt'}), 400
    
    file = request.files['file']
    if file.filename == '' or not allowed_file(file.filename):
        return jsonify({'success': False, 'error': 'Ungültiger Dateityp'}), 400
    
    project = get_or_create_project()
    
    # Eindeutigen Dateinamen generieren
    file_extension = file.filename.rsplit('.', 1)[1].lower()
    unique_filename = f"{uuid.uuid4().hex}.{file_extension}"
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
    
    try:
        file.save(file_path)
        file_size = os.path.getsize(file_path)
        
        photo = Photo(
            project_id=project.id,
            filename=unique_filename,
            original_filename=secure_filename(file.filename),
            description=request.form.get('description', ''),
            file_size=file_size
        )
        
        db.session.add(photo)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Foto hochgeladen',
            'photo': {
                'id': photo.id,
                'filename': photo.filename,
                'url': f'/static/uploads/{photo.filename}'
            }
        })
    
    except Exception as e:
        db.session.rollback()
        if os.path.exists(file_path):
            os.remove(file_path)
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/photos/<int:photo_id>', methods=['DELETE'])
def delete_photo(photo_id):
    """Foto löschen"""
    photo = Photo.query.get_or_404(photo_id)
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], photo.filename)
    
    try:
        # Datei löschen
        if os.path.exists(file_path):
            os.remove(file_path)
        
        # Datenbankeintrag löschen
        db.session.delete(photo)
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Foto gelöscht'})
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/stats', methods=['GET'])
def get_stats():
    """Statistiken abrufen"""
    project = get_or_create_project()
    
    total_entries = Entry.query.filter_by(project_id=project.id).count()
    total_photos = Photo.query.filter_by(project_id=project.id).count()
    
    # Projekttage berechnen
    project_days = (date.today() - project.start_date).days + 1
    
    # Gesamtkosten berechnen
    total_costs = db.session.query(db.func.sum(Entry.costs)).filter_by(project_id=project.id).scalar() or 0
    
    # Gesamtarbeitsstunden
    total_hours = db.session.query(db.func.sum(Entry.work_hours)).filter_by(project_id=project.id).scalar() or 0
    
    return jsonify({
        'total_entries': total_entries,
        'total_photos': total_photos,
        'project_days': project_days,
        'total_costs': float(total_costs),
        'total_hours': float(total_hours),
        'completion': 65  # Placeholder - kann später erweitert werden
    })

@app.route('/api/export', methods=['GET'])
def export_data():
    """Daten als JSON exportieren"""
    project = get_or_create_project()
    entries = Entry.query.filter_by(project_id=project.id).all()
    photos = Photo.query.filter_by(project_id=project.id).all()
    
    export_data = {
        'project': {
            'name': project.name,
            'builder_name': project.builder_name,
            'start_date': project.start_date.strftime('%Y-%m-%d'),
            'status': project.status,
            'description': project.description
        },
        'entries': [],
        'photos': []
    }
    
    for entry in entries:
        export_data['entries'].append({
            'date': entry.date.strftime('%Y-%m-%d'),
            'weather': entry.weather,
            'temperature': entry.temperature,
            'content': entry.content,
            'workers_count': entry.workers_count,
            'materials': entry.materials,
            'work_hours': entry.work_hours,
            'costs': entry.costs,
            'notes': entry.notes
        })
    
    for photo in photos:
        export_data['photos'].append({
            'filename': photo.original_filename,
            'description': photo.description,
            'date_taken': photo.date_taken.strftime('%Y-%m-%d')
        })
    
    return jsonify(export_data)

# Fehlerbehandlung
@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Nicht gefunden'}), 404

@app.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    return jsonify({'error': 'Interner Serverfehler'}), 500

# Datenbank initialisieren
@app.before_first_request
def create_tables():
    db.create_all()

if __name__ == '__main__':
    # Datenbank erstellen falls nicht vorhanden
    with app.app_context():
        db.create_all()
    
    app.run(debug=True, host='0.0.0.0', port=5000)