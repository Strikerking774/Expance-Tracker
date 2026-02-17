from flask import Flask, request, jsonify, send_file, send_from_directory
from flask_cors import CORS
from datetime import datetime
import pandas as pd
import json
import os
from io import BytesIO

app = Flask(__name__, static_folder='.', static_url_path='')
CORS(app)

@app.route('/')
def serve_index():
    return send_from_directory('.', 'index.html')

# Data storage files
TRIPS_FILE = 'trips_data.json'
EXPENSES_FILE = 'expenses_data.json'

# Initialize data files if they don't exist
def init_data_files():
    if not os.path.exists(TRIPS_FILE):
        with open(TRIPS_FILE, 'w') as f:
            json.dump([], f)
    if not os.path.exists(EXPENSES_FILE):
        with open(EXPENSES_FILE, 'w') as f:
            json.dump([], f)

# Load data
def load_trips():
    with open(TRIPS_FILE, 'r') as f:
        return json.load(f)

def save_trips(trips):
    with open(TRIPS_FILE, 'w') as f:
        json.dump(trips, f, indent=2)

def load_expenses():
    with open(EXPENSES_FILE, 'r') as f:
        return json.load(f)

def save_expenses(expenses):
    with open(EXPENSES_FILE, 'w') as f:
        json.dump(expenses, f, indent=2)

# API Routes

@app.route('/api/trips', methods=['GET'])
def get_trips():
    """Get all trips"""
    trips = load_trips()
    return jsonify(trips)

@app.route('/api/trips', methods=['POST'])
def create_trip():
    """Create a new trip - budget is optional"""
    data = request.json
    trips = load_trips()
    
    # Handle optional budget safely
    budget_value = data.get('budget')
    if budget_value is not None and str(budget_value).strip():
        budget = float(budget_value)
    else:
        budget = None
    
    new_trip = {
        'id': str(len(trips) + 1),
        'name': data.get('name'),
        'budget': budget,
        'created_at': datetime.now().isoformat(),
        'status': 'ongoing'
    }
    
    trips.append(new_trip)
    save_trips(trips)
    
    return jsonify(new_trip), 201

@app.route('/api/trips/<trip_id>', methods=['PUT'])
def update_trip(trip_id):
    """Update trip status or details"""
    data = request.json
    trips = load_trips()
    
    for trip in trips:
        if trip['id'] == trip_id:
            if 'status' in data:
                trip['status'] = data['status']
            if 'budget' in data:
                budget_value = data['budget']
                if budget_value is not None and str(budget_value).strip():
                    trip['budget'] = float(budget_value)
                else:
                    trip['budget'] = None
            if 'name' in data:
                trip['name'] = data['name']
            save_trips(trips)
            return jsonify(trip)
    
    return jsonify({'error': 'Trip not found'}), 404

@app.route('/api/trips/<trip_id>', methods=['DELETE'])
def delete_trip(trip_id):
    """Delete a trip and its expenses"""
    trips = load_trips()
    expenses = load_expenses()
    
    # Remove trip
    trips = [t for t in trips if t['id'] != trip_id]
    save_trips(trips)
    
    # Remove associated expenses
    expenses = [e for e in expenses if e['trip_id'] != trip_id]
    save_expenses(expenses)
    
    return jsonify({'message': 'Trip deleted successfully'})

@app.route('/api/expenses', methods=['GET'])
def get_expenses():
    """Get all expenses or expenses for a specific trip"""
    trip_id = request.args.get('trip_id')
    expenses = load_expenses()
    
    if trip_id:
        expenses = [e for e in expenses if e['trip_id'] == trip_id]
    
    return jsonify(expenses)

@app.route('/api/expenses', methods=['POST'])
def add_expense():
    """Add a new expense"""
    data = request.json
    expenses = load_expenses()
    
    new_expense = {
        'id': str(len(expenses) + 1),
        'trip_id': data.get('trip_id'),
        'category': data.get('category'),
        'amount': float(data.get('amount')),
        'description': data.get('description', ''),
        'person': data.get('person', ''),
        'image': data.get('image', ''),  # Base64 encoded image
        'date': datetime.now().strftime('%Y-%m-%d'),
        'time': datetime.now().strftime('%H:%M:%S')
    }
    
    expenses.append(new_expense)
    save_expenses(expenses)
    
    return jsonify(new_expense), 201

@app.route('/api/expenses/<expense_id>', methods=['DELETE'])
def delete_expense(expense_id):
    """Delete an expense"""
    expenses = load_expenses()
    expenses = [e for e in expenses if e['id'] != expense_id]
    save_expenses(expenses)
    
    return jsonify({'message': 'Expense deleted successfully'})

@app.route('/api/trips/<trip_id>/summary', methods=['GET'])
def get_trip_summary(trip_id):
    """Get summary for a specific trip"""
    trips = load_trips()
    expenses = load_expenses()
    
    trip = next((t for t in trips if t['id'] == trip_id), None)
    if not trip:
        return jsonify({'error': 'Trip not found'}), 404
    
    trip_expenses = [e for e in expenses if e['trip_id'] == trip_id]
    total_spent = sum(e['amount'] for e in trip_expenses)
    
    # Only calculate remaining if budget is set
    remaining = (trip['budget'] - total_spent) if trip['budget'] is not None else None
    
    # Category breakdown
    categories = {}
    for expense in trip_expenses:
        cat = expense['category']
        if cat not in categories:
            categories[cat] = 0
        categories[cat] += expense['amount']
    
    summary = {
        'trip': trip,
        'total_budget': trip['budget'],
        'total_spent': total_spent,
        'remaining': remaining,
        'expense_count': len(trip_expenses),
        'categories': categories
    }
    
    return jsonify(summary)

@app.route('/api/export/<trip_id>', methods=['GET'])
def export_trip_to_excel(trip_id):
    """Export trip expenses to Excel with professional formatting"""
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    
    trips = load_trips()
    expenses = load_expenses()
    
    trip = next((t for t in trips if t['id'] == trip_id), None)
    if not trip:
        return jsonify({'error': 'Trip not found'}), 404
    
    trip_expenses = [e for e in expenses if e['trip_id'] == trip_id]
    
    if not trip_expenses:
        return jsonify({'error': 'No expenses to export'}), 400
    
    # Create DataFrame with person field
    df = pd.DataFrame(trip_expenses)
    df = df[['date', 'time', 'category', 'amount', 'person', 'description']]
    df.columns = ['Date', 'Time', 'Category', 'Amount (₹)', 'Person', 'Description']
    
    # Create Excel file in memory
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Expenses', startrow=4)
        
        # Get worksheet
        worksheet = writer.sheets['Expenses']
        
        # Add Trip Header
        worksheet['A1'] = f'TRIP: {trip["name"]}'
        worksheet['A1'].font = Font(size=16, bold=True, color='FFFFFF')
        worksheet['A1'].fill = PatternFill(start_color='667eea', end_color='667eea', fill_type='solid')
        worksheet['A1'].alignment = Alignment(horizontal='left', vertical='center')
        worksheet.merge_cells('A1:F1')
        worksheet.row_dimensions[1].height = 30
        
        if trip['budget'] is not None:
            worksheet['A2'] = f'Budget: ₹{trip["budget"]:,.2f}'
        else:
            worksheet['A2'] = 'Budget: Not Set'
        worksheet['A2'].font = Font(size=11, bold=True)
        worksheet['A2'].alignment = Alignment(horizontal='left')
        
        # Define styles
        header_fill = PatternFill(start_color='1e293b', end_color='1e293b', fill_type='solid')
        header_font = Font(bold=True, color='FFFFFF', size=11)
        
        border = Border(
            left=Side(style='thin', color='e2e8f0'),
            right=Side(style='thin', color='e2e8f0'),
            top=Side(style='thin', color='e2e8f0'),
            bottom=Side(style='thin', color='e2e8f0')
        )
        
        # Format header row (row 5)
        for col in range(1, 7):
            cell = worksheet.cell(row=5, column=col)
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = Alignment(horizontal='center', vertical='center')
            cell.border = border
        
        worksheet.row_dimensions[5].height = 25
        
        # Format data rows
        for row in range(6, len(df) + 6):
            for col in range(1, 7):
                cell = worksheet.cell(row=row, column=col)
                cell.border = border
                cell.alignment = Alignment(horizontal='left', vertical='center', wrap_text=True)
                
                # Format amount column
                if col == 4:
                    cell.number_format = '₹#,##0.00'
                    cell.alignment = Alignment(horizontal='right', vertical='center')
                    cell.font = Font(bold=True, size=11)
        
        # Adjust column widths
        worksheet.column_dimensions['A'].width = 12
        worksheet.column_dimensions['B'].width = 10
        worksheet.column_dimensions['C'].width = 20
        worksheet.column_dimensions['D'].width = 15
        worksheet.column_dimensions['E'].width = 18
        worksheet.column_dimensions['F'].width = 40
        
        # Add summary section
        last_row = len(df) + 7
        
        # Summary box styling
        summary_fill = PatternFill(start_color='f8fafc', end_color='f8fafc', fill_type='solid')
        summary_font = Font(bold=True, size=11)
        amount_font = Font(bold=True, size=12, color='1e293b')
        
        thick_border = Border(
            left=Side(style='medium', color='1e293b'),
            right=Side(style='medium', color='1e293b'),
            top=Side(style='medium', color='1e293b'),
            bottom=Side(style='medium', color='1e293b')
        )
        
        worksheet[f'D{last_row}'] = 'TOTAL SPENT:'
        worksheet[f'D{last_row}'].font = summary_font
        worksheet[f'D{last_row}'].alignment = Alignment(horizontal='right')
        worksheet[f'D{last_row}'].fill = summary_fill
        worksheet[f'D{last_row}'].border = thick_border
        
        worksheet[f'E{last_row}'] = sum(e['amount'] for e in trip_expenses)
        worksheet[f'E{last_row}'].font = amount_font
        worksheet[f'E{last_row}'].number_format = '₹#,##0.00'
        worksheet[f'E{last_row}'].alignment = Alignment(horizontal='right')
        worksheet[f'E{last_row}'].fill = summary_fill
        worksheet[f'E{last_row}'].border = thick_border
        
        # Only show budget and remaining rows if budget is set
        if trip['budget'] is not None:
            worksheet[f'D{last_row+1}'] = 'TRIP BUDGET:'
            worksheet[f'D{last_row+1}'].font = summary_font
            worksheet[f'D{last_row+1}'].alignment = Alignment(horizontal='right')
            worksheet[f'D{last_row+1}'].fill = summary_fill
            worksheet[f'D{last_row+1}'].border = thick_border
            
            worksheet[f'E{last_row+1}'] = trip['budget']
            worksheet[f'E{last_row+1}'].font = amount_font
            worksheet[f'E{last_row+1}'].number_format = '₹#,##0.00'
            worksheet[f'E{last_row+1}'].alignment = Alignment(horizontal='right')
            worksheet[f'E{last_row+1}'].fill = summary_fill
            worksheet[f'E{last_row+1}'].border = thick_border
            
            remaining = trip['budget'] - sum(e['amount'] for e in trip_expenses)
            remaining_color = '10b981' if remaining >= 0 else 'ef4444'
            
            worksheet[f'D{last_row+2}'] = 'REMAINING:'
            worksheet[f'D{last_row+2}'].font = Font(bold=True, size=12, color='FFFFFF')
            worksheet[f'D{last_row+2}'].alignment = Alignment(horizontal='right')
            worksheet[f'D{last_row+2}'].fill = PatternFill(start_color=remaining_color, end_color=remaining_color, fill_type='solid')
            worksheet[f'D{last_row+2}'].border = thick_border
            
            worksheet[f'E{last_row+2}'] = remaining
            worksheet[f'E{last_row+2}'].font = Font(bold=True, size=13, color='FFFFFF')
            worksheet[f'E{last_row+2}'].number_format = '₹#,##0.00'
            worksheet[f'E{last_row+2}'].alignment = Alignment(horizontal='right')
            worksheet[f'E{last_row+2}'].fill = PatternFill(start_color=remaining_color, end_color=remaining_color, fill_type='solid')
            worksheet[f'E{last_row+2}'].border = thick_border
            
            worksheet.row_dimensions[last_row+1].height = 25
            worksheet.row_dimensions[last_row+2].height = 30
        
        # Make summary rows taller
        worksheet.row_dimensions[last_row].height = 25
        
        # Add footer
        footer_row = last_row + 4 if trip['budget'] is not None else last_row + 2
        worksheet[f'A{footer_row}'] = f'Generated on: {datetime.now().strftime("%B %d, %Y at %I:%M %p")}'
        worksheet[f'A{footer_row}'].font = Font(size=9, italic=True, color='64748b')
    
    output.seek(0)
    
    filename = f"{trip['name'].replace(' ', '_')}_{datetime.now().strftime('%Y%m%d')}.xlsx"
    
    return send_file(
        output,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name=filename
    )

@app.route('/api/export-pdf/<trip_id>', methods=['GET'])
def export_trip_to_pdf(trip_id):
    """Export trip expenses to PDF with professional formatting"""
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, letter
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image as RLImage
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT
    import base64
    from io import BytesIO as BIO
    
    trips = load_trips()
    expenses = load_expenses()
    
    trip = next((t for t in trips if t['id'] == trip_id), None)
    if not trip:
        return jsonify({'error': 'Trip not found'}), 404
    
    trip_expenses = [e for e in expenses if e['trip_id'] == trip_id]
    
    if not trip_expenses:
        return jsonify({'error': 'No expenses to export'}), 400
    
    # Create PDF in memory
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
    
    # Container for PDF elements
    elements = []
    
    # Styles
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        textColor=colors.HexColor('#667eea'),
        spaceAfter=30,
        alignment=TA_CENTER,
        fontName='Helvetica-Bold'
    )
    
    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontSize=16,
        textColor=colors.HexColor('#1e293b'),
        spaceAfter=12,
        fontName='Helvetica-Bold'
    )
    
    # Title
    elements.append(Paragraph(f"✈️ {trip['name']}", title_style))
    elements.append(Spacer(1, 12))
    
    # Budget Info
    budget_data = [
        ['Trip Budget:', f"₹{trip['budget']:,.2f}"],
        ['Total Spent:', f"₹{sum(e['amount'] for e in trip_expenses):,.2f}"],
        ['Remaining:', f"₹{trip['budget'] - sum(e['amount'] for e in trip_expenses):,.2f}"]
    ]
    
    budget_table = Table(budget_data, colWidths=[2*inch, 2*inch])
    budget_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f8fafc')),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.HexColor('#1e293b')),
        ('ALIGN', (0, 0), (0, -1), 'LEFT'),
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 12),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
        ('TOPPADDING', (0, 0), (-1, -1), 12),
        ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#e2e8f0'))
    ]))
    
    elements.append(budget_table)
    elements.append(Spacer(1, 30))
    
    # Expenses heading
    elements.append(Paragraph("Expense Details", heading_style))
    elements.append(Spacer(1, 12))
    
    # Expenses table
    data = [['Date', 'Category', 'Amount', 'Person', 'Description']]
    
    for expense in trip_expenses:
        data.append([
            expense['date'],
            expense['category'],
            f"₹{expense['amount']:,.2f}",
            expense['person'] or '-',
            expense['description'][:50] + '...' if len(expense['description']) > 50 else expense['description'] or '-'
        ])
    
    # Create table
    table = Table(data, colWidths=[1*inch, 1.2*inch, 1*inch, 1*inch, 2.3*inch])
    
    # Table style
    table.setStyle(TableStyle([
        # Header
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1e293b')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        
        # Data rows
        ('BACKGROUND', (0, 1), (-1, -1), colors.white),
        ('TEXTCOLOR', (0, 1), (-1, -1), colors.HexColor('#1e293b')),
        ('ALIGN', (0, 1), (0, -1), 'LEFT'),
        ('ALIGN', (2, 1), (2, -1), 'RIGHT'),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 9),
        ('TOPPADDING', (0, 1), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 8),
        
        # Grid
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e2e8f0')),
        
        # Alternating row colors
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8fafc')])
    ]))
    
    elements.append(table)
    elements.append(Spacer(1, 30))
    
    # Summary
    total = sum(e['amount'] for e in trip_expenses)
    remaining = trip['budget'] - total
    
    summary_data = [
        ['TOTAL SPENT:', f"₹{total:,.2f}"],
        ['TRIP BUDGET:', f"₹{trip['budget']:,.2f}"],
        ['REMAINING:', f"₹{remaining:,.2f}"]
    ]
    
    summary_table = Table(summary_data, colWidths=[2*inch, 2*inch])
    summary_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 1), colors.HexColor('#f8fafc')),
        ('BACKGROUND', (0, 2), (-1, 2), colors.HexColor('#10b981') if remaining >= 0 else colors.HexColor('#ef4444')),
        ('TEXTCOLOR', (0, 0), (-1, 1), colors.HexColor('#1e293b')),
        ('TEXTCOLOR', (0, 2), (-1, 2), colors.white),
        ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 1), 12),
        ('FONTSIZE', (0, 2), (-1, 2), 14),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
        ('TOPPADDING', (0, 0), (-1, -1), 12),
        ('GRID', (0, 0), (-1, -1), 2, colors.HexColor('#1e293b'))
    ]))
    
    elements.append(summary_table)
    elements.append(Spacer(1, 30))
    
    # Footer
    footer_style = ParagraphStyle(
        'Footer',
        parent=styles['Normal'],
        fontSize=8,
        textColor=colors.HexColor('#64748b'),
        alignment=TA_CENTER,
        fontName='Helvetica-Oblique'
    )
    
    elements.append(Paragraph(f"Generated on: {datetime.now().strftime('%B %d, %Y at %I:%M %p')}", footer_style))
    
    # Build PDF
    doc.build(elements)
    
    buffer.seek(0)
    filename = f"{trip['name'].replace(' ', '_')}_{datetime.now().strftime('%Y%m%d')}.pdf"
    
    return send_file(
        buffer,
        mimetype='application/pdf',
        as_attachment=True,
        download_name=filename
    )

@app.route('/api/clear-all', methods=['POST'])
def clear_all_data():
    """Clear all trips and expenses"""
    save_trips([])
    save_expenses([])
    return jsonify({'message': 'All data cleared successfully'})

if __name__ == '__main__':
    init_data_files()
    print("\n" + "="*50)
    print("🚀 Trip Expense Tracker Backend Started!")
    print("="*50)
    print("📍 Server running at: http://localhost:5000")
    print("📝 Open index.html in your browser to use the app")
    print("="*50 + "\n")
    app.run(host='0.0.0.0', debug=False, port=5000)
