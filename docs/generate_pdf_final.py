#!/usr/bin/env python3
"""
Final script to generate OPCP-Ai-Powered-Store-Marketing.pdf from OPCP-Ai-Powered-Store.md content
with complete Unicode character handling
"""

import sys
from datetime import datetime
from fpdf import FPDF

class MarketingPDF(FPDF):
    def header(self):
        self.set_font('Arial', 'B', 16)
        self.cell(0, 10, 'OPCP AI-Powered Store - Marketing Document', 0, 1, 'C')
        self.set_font('Arial', '', 10)
        self.cell(0, 10, f'Generated on {datetime.now().strftime("%Y-%m-%d")}', 0, 1, 'C')
        self.ln(10)

    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.cell(0, 10, f'Page {self.page_no()}', 0, 0, 'C')

    def title(self, title):
        self.set_font('Arial', 'B', 14)
        self.cell(0, 10, title, 0, 1, 'L')
        self.ln(5)

    def subtitle(self, subtitle):
        self.set_font('Arial', 'I', 12)
        self.cell(0, 8, subtitle, 0, 1, 'L')
        self.ln(3)

    def text_block(self, text):
        self.set_font('Arial', '', 11)
        self.multi_cell(0, 5, text)
        self.ln(3)

    def code_block(self, code):
        self.set_font('Courier', '', 10)
        self.multi_cell(0, 5, code)
        self.set_font('Arial', '', 11)
        self.ln(3)

    def table_block(self, lines):
        # Simple table rendering - just display as text for now
        for line in lines:
            self.text_block(line)

def generate_marketing_pdf():
    # Read the OPCP-Ai-Powered-Store.md content
    try:
        with open('OPCP-Ai-Powered-Store.md', 'r', encoding='utf-8') as f:
            content = f.read()
    except FileNotFoundError:
        print("Error: OPCP-Ai-Powered-Store.md not found in current directory")
        return False
    
    # Replace all problematic Unicode characters that cause latin-1 encoding issues
    # These are emojis and special characters that can't be encoded in latin-1
    replacements = {
        '🔐': '[LOCK]',
        '🌐': '[WEB]',
        '📱': '[PHONE]',
        '🔑': '[KEY]',
        '🚀': '[ROCKET]',
        '🐳': '[WHALE]',
        '🖥': '[DESKTOP]',
        '🔌': '[PLUG]',
        '🤖': '[ROBOT]',
        '🛡': '[SHIELD]',
        '🔄': '[ARROW]',
        '💰': '[MONEY]',
        '📊': '[CHART]',
        '🔀': '[SHUFFLE]',
        '📖': '[BOOK]',
        '🔧': '[TOOL]',
        '🎮': '[GAME]',
        '⚡': '[LIGHTNING]',
        '🎭': '[THEATER]',
        '🔒': '[LOCK]',
        '✅': '[CHECK]',
        '→': '[RIGHT_ARROW]'
    }
    
    # Apply all replacements
    for unicode_char, ascii_replacement in replacements.items():
        content = content.replace(unicode_char, ascii_replacement)
    
    # Create PDF
    pdf = MarketingPDF()
    pdf.add_page()
    
    # Split content into paragraphs (separated by double newlines)
    paragraphs = content.split('\n\n')
    
    # Process each paragraph
    i = 0
    while i < len(paragraphs):
        paragraph = paragraphs[i].strip()
        if not paragraph:
            i += 1
            continue
            
        # Handle different section types
        if paragraph.startswith('# '):
            title = paragraph[2:].strip()
            pdf.title(title)
        elif paragraph.startswith('## '):
            subtitle = paragraph[3:].strip()
            pdf.subtitle(subtitle)
        elif paragraph.startswith('### '):
            subtitle = paragraph[4:].strip()
            pdf.subtitle(subtitle)
        elif paragraph.startswith('|') and '|' in paragraph:
            # Handle table - collect all table lines
            table_lines = []
            j = i
            while j < len(paragraphs) and (paragraphs[j].strip().startswith('|') or not paragraphs[j].strip()):
                table_lines.append(paragraphs[j].strip())
                j += 1
            if table_lines:
                pdf.table_block(table_lines)
                i = j - 1  # Skip processed lines
        elif paragraph.startswith('```'):
            # Handle code block
            code_lines = []
            j = i + 1
            while j < len(paragraphs) and not paragraphs[j].strip() == '```':
                code_lines.append(paragraphs[j].strip())
                j += 1
            if code_lines:
                code_text = '\n'.join(code_lines)
                pdf.code_block(code_text)
            i = j  # Skip to end of code block
        elif paragraph.startswith('- ') or paragraph.startswith('* '):
            # Bullet point - treat as regular text
            pdf.text_block(paragraph)
        elif paragraph.startswith('> '):
            # Blockquote - treat as regular text
            pdf.text_block(paragraph)
        else:
            # Regular paragraph
            pdf.text_block(paragraph)
        
        i += 1
    
    # Save PDF
    output_file = 'OPCP-Ai-Powered-Store-Marketing.pdf'
    try:
        pdf.output(output_file)
        print(f"Successfully generated {output_file}")
        return True
    except Exception as e:
        print(f"Error generating PDF: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = generate_marketing_pdf()
    if not success:
        sys.exit(1)