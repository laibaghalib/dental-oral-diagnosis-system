import io
import base64
import json
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, Image as RLImage
)
from reportlab.graphics.shapes import Drawing, Rect
from reportlab.graphics import renderPDF
from PIL import Image as PILImage


# ── Colours ─────────────────────────────────────────────────────────────────
TEAL       = colors.HexColor('#0d9488')
TEAL_LIGHT = colors.HexColor('#e8f5f3')
DARK       = colors.HexColor('#0a1628')
MUTED      = colors.HexColor('#64748b')
WHITE      = colors.white
DANGER     = colors.HexColor('#a32d2d')
AMBER      = colors.HexColor('#b45309')
SUCCESS    = colors.HexColor('#166534')
BG         = colors.HexColor('#f8fafc')
BORDER     = colors.HexColor('#e2e8f0')


# ── Confidence colour ────────────────────────────────────────────────────────
def confidence_color(pct):
    if pct >= 75:  return SUCCESS
    if pct >= 50:  return AMBER
    return DANGER


# ── Base64 image → ReportLab Image ──────────────────────────────────────────
def b64_to_rl_image(b64_str, width_mm, height_mm):
    try:
        data  = base64.b64decode(b64_str)
        buf   = io.BytesIO(data)
        pil   = PILImage.open(buf).convert('RGB')
        out   = io.BytesIO()
        pil.save(out, format='PNG')
        out.seek(0)
        return RLImage(out, width=width_mm * mm, height=height_mm * mm)
    except Exception:
        return None


# ── Main generator ───────────────────────────────────────────────────────────
def generate_pdf(scan, patient_info):
    """
    scan         — Scan model instance (with .probs, .models already parsed)
    patient_info — dict with keys:
                   name, email, dob, age, gender, phone,
                   medical_history, allergies, current_medications, notes
    Returns bytes of the PDF.
    """
    buf    = io.BytesIO()
    W, H   = A4
    margin = 18 * mm

    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=margin, rightMargin=margin,
        topMargin=14 * mm, bottomMargin=14 * mm,
        title='DentalAI Diagnostic Report',
        author='DentalAI',
    )

    styles = getSampleStyleSheet()

    # Custom styles
    def S(name, **kw):
        return ParagraphStyle(name, **kw)

    s_h1    = S('h1',    fontSize=22, textColor=DARK,  fontName='Helvetica-Bold',  leading=28, alignment=TA_CENTER)
    s_h2    = S('h2',    fontSize=13, textColor=TEAL,  fontName='Helvetica-Bold',  leading=18, spaceAfter=4)
    s_h3    = S('h3',    fontSize=10, textColor=DARK,  fontName='Helvetica-Bold',  leading=14)
    s_body  = S('body',  fontSize=9,  textColor=DARK,  fontName='Helvetica',       leading=14)
    s_muted = S('muted', fontSize=8,  textColor=MUTED, fontName='Helvetica',       leading=12)
    s_ctr   = S('ctr',   fontSize=9,  textColor=MUTED, fontName='Helvetica',       leading=12, alignment=TA_CENTER)
    s_warn  = S('warn',  fontSize=8,  textColor=DANGER,fontName='Helvetica-Oblique',leading=12)

    story = []

    # ── HEADER ───────────────────────────────────────────────────────────────
    header_data = [[
        Paragraph('<font color="#0d9488"><b>🦷 DentalAI</b></font><br/>'
                  '<font size="7" color="#64748b">Smart AI Dental Assistant · dentalai.pk</font>', s_body),
        Paragraph(f'<font size="7" color="#64748b">Report ID: DX-{scan.id:05d}<br/>'
                  f'Generated: {datetime.utcnow().strftime("%d %b %Y, %H:%M UTC")}</font>', 
                  ParagraphStyle('rt', fontSize=7, textColor=MUTED, alignment=TA_RIGHT, leading=11)),
    ]]
    header_tbl = Table(header_data, colWidths=[W - 2*margin - 60*mm, 60*mm])
    header_tbl.setStyle(TableStyle([
        ('VALIGN',      (0,0), (-1,-1), 'MIDDLE'),
        ('BOTTOMPADDING',(0,0),(-1,-1), 6),
    ]))
    story.append(header_tbl)
    story.append(HRFlowable(width='100%', thickness=1.5, color=TEAL, spaceAfter=10))

    # Title
    story.append(Paragraph('Dental Diagnostic Report', s_h1))
    story.append(Spacer(1, 6))

    # ── PATIENT INFO ──────────────────────────────────────────────────────────
    story.append(Paragraph('Patient Information', s_h2))

    pi = patient_info
    patient_rows = [
        ['Full Name',    pi.get('name', '—'),          'Date of Birth', pi.get('dob', '—')],
        ['Age',          pi.get('age', '—'),            'Gender',        pi.get('gender', '—')],
        ['Email',        pi.get('email', '—'),          'Phone',         pi.get('phone', '—')],
    ]
    pt = Table(patient_rows, colWidths=[30*mm, 60*mm, 30*mm, 60*mm - (W - A4[0])])
    pt.setStyle(TableStyle([
        ('FONTNAME',     (0,0), (0,-1), 'Helvetica-Bold'),
        ('FONTNAME',     (2,0), (2,-1), 'Helvetica-Bold'),
        ('FONTSIZE',     (0,0), (-1,-1), 8.5),
        ('TEXTCOLOR',    (0,0), (0,-1), MUTED),
        ('TEXTCOLOR',    (2,0), (2,-1), MUTED),
        ('TEXTCOLOR',    (1,0), (1,-1), DARK),
        ('TEXTCOLOR',    (3,0), (3,-1), DARK),
        ('BACKGROUND',   (0,0), (-1,-1), BG),
        ('ROWBACKGROUNDS',(0,0),(-1,-1), [BG, WHITE]),
        ('GRID',         (0,0), (-1,-1), 0.3, BORDER),
        ('TOPPADDING',   (0,0), (-1,-1), 5),
        ('BOTTOMPADDING',(0,0), (-1,-1), 5),
        ('LEFTPADDING',  (0,0), (-1,-1), 8),
    ]))
    story.append(pt)
    story.append(Spacer(1, 8))

    # Medical history
    mh_rows = [
        ['Medical History',      pi.get('medical_history', 'None reported')],
        ['Allergies',            pi.get('allergies', 'None reported')],
        ['Current Medications',  pi.get('current_medications', 'None reported')],
        ['Additional Notes',     pi.get('notes', '—')],
    ]
    mht = Table(mh_rows, colWidths=[38*mm, W - 2*margin - 38*mm])
    mht.setStyle(TableStyle([
        ('FONTNAME',     (0,0), (0,-1), 'Helvetica-Bold'),
        ('FONTSIZE',     (0,0), (-1,-1), 8.5),
        ('TEXTCOLOR',    (0,0), (0,-1), MUTED),
        ('TEXTCOLOR',    (1,0), (1,-1), DARK),
        ('ROWBACKGROUNDS',(0,0),(-1,-1), [BG, WHITE]),
        ('GRID',         (0,0), (-1,-1), 0.3, BORDER),
        ('TOPPADDING',   (0,0), (-1,-1), 5),
        ('BOTTOMPADDING',(0,0), (-1,-1), 5),
        ('LEFTPADDING',  (0,0), (-1,-1), 8),
        ('VALIGN',       (0,0), (-1,-1), 'TOP'),
    ]))
    story.append(mht)
    story.append(Spacer(1, 12))

    # ── DIAGNOSIS ────────────────────────────────────────────────────────────
    story.append(HRFlowable(width='100%', thickness=0.5, color=BORDER, spaceAfter=8))
    story.append(Paragraph('AI Diagnosis', s_h2))

    conf     = scan.confidence
    c_color  = confidence_color(conf)
    scan_dt  = scan.created_at.strftime('%d %b %Y at %I:%M %p')

    diag_data = [[
        Paragraph(f'<b>Detected Condition</b><br/>'
                  f'<font size="18" color="#0d9488"><b>{scan.predicted_class}</b></font>', s_body),
        Paragraph(f'<b>Confidence Score</b><br/>'
                  f'<font size="18"><b>{conf:.1f}%</b></font>', 
                  ParagraphStyle('conf', fontSize=9, textColor=c_color, fontName='Helvetica-Bold', leading=24)),
        Paragraph(f'<b>Scan Date</b><br/>'
                  f'<font size="9" color="#0a1628">{scan_dt}</font>', s_body),
    ]]
    dt = Table(diag_data, colWidths=[(W - 2*margin)/3]*3)
    dt.setStyle(TableStyle([
        ('BACKGROUND',   (0,0), (-1,-1), TEAL_LIGHT),
        ('GRID',         (0,0), (-1,-1), 0.3, TEAL),
        ('TOPPADDING',   (0,0), (-1,-1), 10),
        ('BOTTOMPADDING',(0,0), (-1,-1), 10),
        ('LEFTPADDING',  (0,0), (-1,-1), 10),
        ('VALIGN',       (0,0), (-1,-1), 'MIDDLE'),
    ]))
    story.append(dt)
    story.append(Spacer(1, 10))

    # Individual model predictions
    story.append(Paragraph('Individual Model Predictions', s_h3))
    story.append(Spacer(1, 4))
    models     = scan.models if hasattr(scan, 'models') else {}
    model_rows = [[
        Paragraph(f'<b>{m}</b>', s_body),
        Paragraph(pred, s_body),
        Paragraph('✓ Agree' if pred == scan.predicted_class else '≠ Differ',
                  ParagraphStyle('chk', fontSize=8, fontName='Helvetica-Bold',
                                 textColor=SUCCESS if pred == scan.predicted_class else AMBER, leading=12)),
    ] for m, pred in models.items()]

    if model_rows:
        mt = Table([['Model', 'Prediction', 'vs Ensemble']] + model_rows,
                   colWidths=[50*mm, 80*mm, 40*mm])
        mt.setStyle(TableStyle([
            ('BACKGROUND',    (0,0), (-1,0), DARK),
            ('TEXTCOLOR',     (0,0), (-1,0), WHITE),
            ('FONTNAME',      (0,0), (-1,0), 'Helvetica-Bold'),
            ('FONTSIZE',      (0,0), (-1,-1), 8.5),
            ('ROWBACKGROUNDS',(0,1),(-1,-1), [BG, WHITE]),
            ('GRID',          (0,0), (-1,-1), 0.3, BORDER),
            ('TOPPADDING',    (0,0), (-1,-1), 5),
            ('BOTTOMPADDING', (0,0), (-1,-1), 5),
            ('LEFTPADDING',   (0,0), (-1,-1), 8),
        ]))
        story.append(mt)
    story.append(Spacer(1, 10))

    # ── PROBABILITY TABLE ────────────────────────────────────────────────────
    story.append(Paragraph('Class Probability Breakdown', s_h3))
    story.append(Spacer(1, 4))

    probs  = scan.probs if hasattr(scan, 'probs') else {}
    sorted_probs = sorted(probs.items(), key=lambda x: x[1], reverse=True)

    prob_rows = []
    for cls, pct in sorted_probs:
        bar_w  = int((pct / 100) * 80)  # max 80 chars visual
        is_top = cls == scan.predicted_class
        prob_rows.append([
            Paragraph(f'<b>{cls}</b>' if is_top else cls, s_body),
            Paragraph(f'<b>{pct:.1f}%</b>' if is_top else f'{pct:.1f}%',
                      ParagraphStyle('pp', fontSize=9,
                                     fontName='Helvetica-Bold' if is_top else 'Helvetica',
                                     textColor=TEAL if is_top else DARK, leading=12)),
        ])

    if prob_rows:
        probt = Table([['Condition', 'Probability']] + prob_rows,
                      colWidths=[100*mm, 60*mm])
        probt.setStyle(TableStyle([
            ('BACKGROUND',    (0,0), (-1,0), DARK),
            ('TEXTCOLOR',     (0,0), (-1,0), WHITE),
            ('FONTNAME',      (0,0), (-1,0), 'Helvetica-Bold'),
            ('FONTSIZE',      (0,0), (-1,-1), 8.5),
            ('ROWBACKGROUNDS',(0,1),(-1,-1), [TEAL_LIGHT, WHITE]),
            ('GRID',          (0,0), (-1,-1), 0.3, BORDER),
            ('TOPPADDING',    (0,0), (-1,-1), 5),
            ('BOTTOMPADDING', (0,0), (-1,-1), 5),
            ('LEFTPADDING',   (0,0), (-1,-1), 8),
        ]))
        story.append(probt)
    story.append(Spacer(1, 12))

    # ── IMAGES ───────────────────────────────────────────────────────────────
    img_elems = []

    if scan.image_b64:
        img = b64_to_rl_image(scan.image_b64, 75, 75)
        if img:
            img_elems.append([
                Paragraph('Original Image', s_muted),
                img,
            ])

    if scan.gradcam_b64:
        img = b64_to_rl_image(scan.gradcam_b64, 75, 75)
        if img:
            img_elems.append([
                Paragraph('GradCAM Heatmap', s_muted),
                img,
            ])

    if img_elems:
        story.append(HRFlowable(width='100%', thickness=0.5, color=BORDER, spaceAfter=8))
        story.append(Paragraph('Scan Images', s_h2))

        flat_labels = [e[0] for e in img_elems]
        flat_imgs   = [e[1] for e in img_elems]

        col_w = (W - 2*margin) / max(len(img_elems), 1)
        lbl_t = Table([flat_labels], colWidths=[col_w]*len(flat_labels))
        img_t = Table([flat_imgs],   colWidths=[col_w]*len(flat_imgs))

        for t in [lbl_t, img_t]:
            t.setStyle(TableStyle([
                ('ALIGN',   (0,0), (-1,-1), 'CENTER'),
                ('VALIGN',  (0,0), (-1,-1), 'MIDDLE'),
            ]))

        story.append(lbl_t)
        story.append(img_t)
        story.append(Spacer(1, 12))

    # ── CLINICAL GUIDELINES ──────────────────────────────────────────────────
    story.append(HRFlowable(width='100%', thickness=0.5, color=BORDER, spaceAfter=8))
    story.append(Paragraph('Clinical Guidelines & Recommendations', s_h2))

    guidelines = {
        'Calculus': [
            'Schedule a professional scaling and root planing session.',
            'Use an electric toothbrush with a timer (2 min, twice daily).',
            'Floss daily and consider an antiseptic mouthwash.',
            'Follow-up dental cleaning every 3–6 months.',
        ],
        'Data caries': [
            'Consult a dentist promptly for cavity assessment.',
            'Fluoride toothpaste and fluoride varnish application recommended.',
            'Reduce sugar intake and acidic beverages.',
            'Dental sealants may be advised for molars.',
        ],
        'Gingivitis': [
            'Improve oral hygiene: brush gently along the gumline.',
            'Professional cleaning to remove plaque and tartar.',
            'Chlorhexidine mouthwash for short-term gum care.',
            'Re-evaluate after 4 weeks of improved hygiene.',
        ],
        'Mouth Ulcer': [
            'Avoid spicy, acidic, and abrasive foods temporarily.',
            'Topical anesthetic or antiseptic gel for pain relief.',
            'Stay hydrated and maintain soft diet.',
            'If ulcers persist beyond 2 weeks, seek specialist evaluation.',
        ],
        'Tooth Discoloration': [
            'Professional whitening or microabrasion may be indicated.',
            'Identify and address the cause (diet, medication, trauma).',
            'Avoid staining foods: coffee, tea, tobacco.',
            'Veneers or bonding for severe intrinsic discoloration.',
        ],
        'hypodontia': [
            'Orthodontic assessment to evaluate space management.',
            'Implants, bridges, or partial dentures may be considered.',
            'Regular monitoring of jaw development in younger patients.',
            'Multidisciplinary care involving orthodontist and prosthodontist.',
        ],
    }

    cond     = scan.predicted_class
    gl_items = guidelines.get(cond, ['Consult your dentist for a personalised treatment plan.'])

    gl_rows = [[
        Paragraph(f'{i+1}. {item}', s_body)
    ] for i, item in enumerate(gl_items)]

    glt = Table(gl_rows, colWidths=[W - 2*margin])
    glt.setStyle(TableStyle([
        ('ROWBACKGROUNDS',(0,0),(-1,-1), [TEAL_LIGHT, WHITE]),
        ('GRID',         (0,0), (-1,-1), 0.3, BORDER),
        ('TOPPADDING',   (0,0), (-1,-1), 6),
        ('BOTTOMPADDING',(0,0), (-1,-1), 6),
        ('LEFTPADDING',  (0,0), (-1,-1), 10),
    ]))
    story.append(glt)
    story.append(Spacer(1, 12))

    # ── GENERAL DENTAL CARE TIPS ─────────────────────────────────────────────
    story.append(Paragraph('General Oral Health Guidelines', s_h2))

    general = [
        'Brush teeth twice daily for at least 2 minutes using fluoride toothpaste.',
        'Floss at least once daily to remove interdental plaque.',
        'Replace your toothbrush every 3 months or after illness.',
        'Visit your dentist every 6 months for a routine check-up.',
        'Drink plenty of water — fluoridated water strengthens enamel.',
        'Limit sugary snacks and acidic drinks to protect enamel.',
        'Do not smoke — tobacco significantly increases gum disease and oral cancer risk.',
        'Wear a mouthguard during contact sports.',
        'This report is AI-generated and is intended for screening purposes only. '
        'Always consult a qualified dental professional for diagnosis and treatment.',
    ]

    for tip in general:
        story.append(Paragraph(f'• {tip}', s_body))
        story.append(Spacer(1, 2))

    story.append(Spacer(1, 12))

    # ── DISCLAIMER ───────────────────────────────────────────────────────────
    story.append(HRFlowable(width='100%', thickness=1, color=TEAL, spaceAfter=6))
    story.append(Paragraph(
        'DISCLAIMER: This report is generated by an AI system and is intended solely for '
        'informational and screening purposes. It does not constitute a medical diagnosis. '
        'Always consult a licensed dental professional before making any clinical decisions.',
        s_warn
    ))
    story.append(Spacer(1, 4))
    story.append(Paragraph(
        f'© {datetime.utcnow().year} DentalAI · info@dentalai.pk · dentalai.pk · '
        f'Report generated for: {pi.get("name", "Patient")} · '
        f'Scan ID: DX-{scan.id:05d}',
        s_ctr
    ))

    doc.build(story)
    buf.seek(0)
    return buf.read()
