# app.py - Flask Backend für Bautagebuch
from flask import Flask, render_template, request, jsonify, send_file
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, date
import os
import json
from werkzeug.utils import secure_filename
import uuid
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch, cm
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
import io
import base64
from PIL import Image as PILImage

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

# Neue Route für PDF-Export hinzufügen:

@app.route('/api/export/pdf', methods=['GET'])
def export_pdf():
    """Bautagebuch als PDF exportieren"""
    try:
        project = get_or_create_project()
        entries = Entry.query.filter_by(project_id=project.id).order_by(Entry.date.asc()).all()
        photos = Photo.query.filter_by(project_id=project.id).order_by(Photo.date_taken.asc()).all()

        # PDF in Memory erstellen
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=2 * cm,
            leftMargin=2 * cm,
            topMargin=2 * cm,
            bottomMargin=2 * cm
        )

        # Styles definieren
        styles = getSampleStyleSheet()

        # Custom Styles
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Title'],
            fontSize=24,
            spaceAfter=30,
            alignment=TA_CENTER,
            textColor=colors.darkblue
        )

        heading_style = ParagraphStyle(
            'CustomHeading',
            parent=styles['Heading1'],
            fontSize=16,
            spaceAfter=12,
            spaceBefore=20,
            textColor=colors.darkblue
        )

        subheading_style = ParagraphStyle(
            'CustomSubHeading',
            parent=styles['Heading2'],
            fontSize=14,
            spaceAfter=6,
            spaceBefore=12,
            textColor=colors.darkgreen
        )

        normal_style = ParagraphStyle(
            'CustomNormal',
            parent=styles['Normal'],
            fontSize=11,
            spaceAfter=6,
            alignment=TA_LEFT
        )

        # PDF Content aufbauen
        story = []

        # Titel
        story.append(Paragraph("Bautagebuch", title_style))
        story.append(Paragraph(f"Projekt: {project.name}", heading_style))
        story.append(Spacer(1, 20))

        # Projektinformationen
        story.append(Paragraph("Projektinformationen", heading_style))

        project_data = [
            ['Projektname:', project.name],
            ['Bauherr:', project.builder_name],
            ['Startdatum:', project.start_date.strftime('%d.%m.%Y')],
            ['Status:', project.status],
            ['Beschreibung:', project.description or 'Keine Beschreibung']
        ]

        project_table = Table(project_data, colWidths=[4 * cm, 12 * cm])
        project_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 11),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
        ]))

        story.append(project_table)
        story.append(Spacer(1, 20))

        # Statistiken
        total_entries = len(entries)
        total_photos = len(photos)
        project_days = (date.today() - project.start_date).days + 1
        total_costs = sum(entry.costs or 0 for entry in entries)
        total_hours = sum(entry.work_hours or 0 for entry in entries)

        story.append(Paragraph("Projektstatistiken", heading_style))

        stats_data = [
            ['Gesamte Einträge:', str(total_entries)],
            ['Gesamte Fotos:', str(total_photos)],
            ['Projekttage:', str(project_days)],
            ['Gesamtkosten:', f"{total_costs:.2f} €"],
            ['Gesamtarbeitsstunden:', f"{total_hours:.1f} h"]
        ]

        stats_table = Table(stats_data, colWidths=[4 * cm, 12 * cm])
        stats_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 11),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.lightgrey),
        ]))

        story.append(stats_table)
        story.append(PageBreak())

        # Einträge
        story.append(Paragraph("Bautagebuch-Einträge", heading_style))
        story.append(Spacer(1, 12))

        for i, entry in enumerate(entries):
            # Datum als Überschrift
            story.append(Paragraph(
                f"Eintrag {i + 1}: {entry.date.strftime('%d.%m.%Y')}",
                subheading_style
            ))

            # Entry Details Table
            entry_data = []

            if entry.weather:
                entry_data.append(['Wetter:', entry.weather])
            if entry.temperature:
                entry_data.append(['Temperatur:', f"{entry.temperature}°C"])
            if entry.workers_count:
                entry_data.append(['Arbeiter:', str(entry.workers_count)])
            if entry.work_hours:
                entry_data.append(['Arbeitsstunden:', f"{entry.work_hours} h"])
            if entry.costs:
                entry_data.append(['Kosten:', f"{entry.costs:.2f} €"])

            if entry_data:
                entry_table = Table(entry_data, colWidths=[3 * cm, 8 * cm])
                entry_table.setStyle(TableStyle([
                    ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                    ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, -1), 10),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
                    ('TOPPADDING', (0, 0), (-1, -1), 4),
                ]))
                story.append(entry_table)
                story.append(Spacer(1, 8))

            # Arbeitsinhalt
            story.append(Paragraph("<b>Arbeitsinhalt:</b>", normal_style))
            story.append(Paragraph(entry.content, normal_style))
            story.append(Spacer(1, 6))

            # Materialien
            if entry.materials:
                story.append(Paragraph("<b>Materialien:</b>", normal_style))
                story.append(Paragraph(entry.materials, normal_style))
                story.append(Spacer(1, 6))

            # Notizen
            if entry.notes:
                story.append(Paragraph("<b>Notizen:</b>", normal_style))
                story.append(Paragraph(entry.notes, normal_style))
                story.append(Spacer(1, 6))

            story.append(Spacer(1, 15))

            # Seitenwechsel nach jedem 3. Eintrag
            if (i + 1) % 3 == 0 and i < len(entries) - 1:
                story.append(PageBreak())

        # Fotos Sektion
        if photos:
            story.append(PageBreak())
            story.append(Paragraph("Projektfotos", heading_style))
            story.append(Spacer(1, 12))

            photos_per_page = 4
            for i, photo in enumerate(photos):
                try:
                    # Bild laden und skalieren
                    img_path = os.path.join(app.config['UPLOAD_FOLDER'], photo.filename)
                    if os.path.exists(img_path):
                        # Bild öffnen und Größe prüfen
                        with PILImage.open(img_path) as pil_img:
                            # Maximale Größe für PDF
                            max_width = 8 * cm
                            max_height = 6 * cm

                            # Aspect Ratio beibehalten
                            img_width, img_height = pil_img.size
                            aspect = img_width / img_height

                            if aspect > max_width / max_height:
                                # Bild ist breiter
                                pdf_width = max_width
                                pdf_height = max_width / aspect
                            else:
                                # Bild ist höher
                                pdf_height = max_height
                                pdf_width = max_height * aspect

                        # Bild zu PDF hinzufügen
                        img = Image(img_path, width=pdf_width, height=pdf_height)

                        # Foto-Info
                        photo_info = f"<b>{photo.original_filename}</b><br/>"
                        photo_info += f"Datum: {photo.date_taken.strftime('%d.%m.%Y')}<br/>"
                        if photo.description:
                            photo_info += f"Beschreibung: {photo.description}"

                        # Foto und Info in Tabelle
                        photo_table = Table([[img, Paragraph(photo_info, normal_style)]],
                                            colWidths=[pdf_width + 1 * cm, 8 * cm])
                        photo_table.setStyle(TableStyle([
                            ('ALIGN', (0, 0), (0, 0), 'CENTER'),
                            ('ALIGN', (1, 0), (1, 0), 'LEFT'),
                            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                            ('TOPPADDING', (0, 0), (-1, -1), 6),
                            ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
                        ]))

                        story.append(photo_table)
                        story.append(Spacer(1, 12))

                        # Seitenwechsel nach bestimmter Anzahl Fotos
                        if (i + 1) % photos_per_page == 0 and i < len(photos) - 1:
                            story.append(PageBreak())

                except Exception as e:
                    # Fehler beim Laden des Bildes - Info hinzufügen
                    error_text = f"<b>{photo.original_filename}</b> (Bild konnte nicht geladen werden)<br/>"
                    error_text += f"Datum: {photo.date_taken.strftime('%d.%m.%Y')}<br/>"
                    if photo.description:
                        error_text += f"Beschreibung: {photo.description}"

                    story.append(Paragraph(error_text, normal_style))
                    story.append(Spacer(1, 12))

        # PDF generieren
        doc.build(story)
        buffer.seek(0)

        # PDF als Download zurückgeben
        filename = f"Bautagebuch_{project.name.replace(' ', '_')}_{date.today().strftime('%Y%m%d')}.pdf"

        return send_file(
            buffer,
            as_attachment=True,
            download_name=filename,
            mimetype='application/pdf'
        )

    except Exception as e:
        return jsonify({'success': False, 'error': f'PDF-Export fehlgeschlagen: {str(e)}'}), 500


@app.route('/api/export/pdf/entry/<int:entry_id>', methods=['GET'])
def export_single_entry_pdf(entry_id):
    """Einzelnen Eintrag als PDF exportieren"""
    try:
        entry = Entry.query.get_or_404(entry_id)
        project = entry.project

        # PDF in Memory erstellen
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=2 * cm,
            leftMargin=2 * cm,
            topMargin=2 * cm,
            bottomMargin=2 * cm
        )

        styles = getSampleStyleSheet()
        story = []

        # Titel
        story.append(Paragraph(f"Bautagebuch-Eintrag", styles['Title']))
        story.append(Paragraph(f"Projekt: {project.name}", styles['Heading1']))
        story.append(Paragraph(f"Datum: {entry.date.strftime('%d.%m.%Y')}", styles['Heading2']))
        story.append(Spacer(1, 20))

        # Entry Details
        if any([entry.weather, entry.temperature, entry.workers_count, entry.work_hours, entry.costs]):
            story.append(Paragraph("Details", styles['Heading2']))

            details_data = []
            if entry.weather:
                details_data.append(['Wetter:', entry.weather])
            if entry.temperature:
                details_data.append(['Temperatur:', f"{entry.temperature}°C"])
            if entry.workers_count:
                details_data.append(['Arbeiter:', str(entry.workers_count)])
            if entry.work_hours:
                details_data.append(['Arbeitsstunden:', f"{entry.work_hours} h"])
            if entry.costs:
                details_data.append(['Kosten:', f"{entry.costs:.2f} €"])

            details_table = Table(details_data, colWidths=[4 * cm, 10 * cm])
            details_table.setStyle(TableStyle([
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.lightgrey),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
                ('TOPPADDING', (0, 0), (-1, -1), 6),
            ]))

            story.append(details_table)
            story.append(Spacer(1, 20))

        # Arbeitsinhalt
        story.append(Paragraph("Arbeitsinhalt", styles['Heading2']))
        story.append(Paragraph(entry.content, styles['Normal']))
        story.append(Spacer(1, 15))

        # Materialien
        if entry.materials:
            story.append(Paragraph("Materialien", styles['Heading2']))
            story.append(Paragraph(entry.materials, styles['Normal']))
            story.append(Spacer(1, 15))

        # Notizen
        if entry.notes:
            story.append(Paragraph("Notizen", styles['Heading2']))
            story.append(Paragraph(entry.notes, styles['Normal']))

        # PDF generieren
        doc.build(story)
        buffer.seek(0)

        filename = f"Eintrag_{entry.date.strftime('%Y%m%d')}.pdf"

        return send_file(
            buffer,
            as_attachment=True,
            download_name=filename,
            mimetype='application/pdf'
        )

    except Exception as e:
        return jsonify({'success': False, 'error': f'PDF-Export fehlgeschlagen: {str(e)}'}), 500

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