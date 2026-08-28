"""
Sonic Mind Forge - PDF Report Generator

Creates professional audio analysis reports with visual meters and grading.
"""

import io
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, 
    HRFlowable, Image
)
from reportlab.graphics.shapes import Drawing, Rect, String
from reportlab.graphics.charts.barcharts import HorizontalBarChart
from reportlab.lib.enums import TA_CENTER, TA_LEFT

# Import the analysis result type
from .audio_analyzer import AnalysisResult


# Color scheme - Premium dark theme feel
COLORS = {
    'primary': colors.HexColor('#6366F1'),      # Indigo
    'secondary': colors.HexColor('#8B5CF6'),    # Purple
    'success': colors.HexColor('#10B981'),      # Green
    'warning': colors.HexColor('#F59E0B'),      # Amber
    'danger': colors.HexColor('#EF4444'),       # Red
    'dark': colors.HexColor('#1F2937'),         # Dark gray
    'light': colors.HexColor('#F3F4F6'),        # Light gray
    'white': colors.white,
    'black': colors.black,
}

GRADE_COLORS = {
    'PASS': COLORS['success'],
    'EXCELLENT': COLORS['success'],
    'GOOD': COLORS['primary'],
    'WARNING': COLORS['warning'],
    'NEEDS WORK': COLORS['warning'],
    'FAIL': COLORS['danger'],
    'CRITICAL ISSUES': COLORS['danger'],
}


@dataclass
class ReportConfig:
    """Configuration for report generation."""
    title: str = "Sonic Mind Forge"
    subtitle: str = "AI Audio Analysis Report"
    brand_color: str = "#6366F1"
    logo_path: Optional[str] = None
    include_spectral_chart: bool = True
    include_recommendations: bool = True


class ReportGenerator:
    """Generate professional PDF reports from audio analysis results."""
    
    def __init__(self, config: Optional[ReportConfig] = None):
        self.config = config or ReportConfig()
        self.styles = getSampleStyleSheet()
        self._setup_styles()
    
    def _setup_styles(self):
        """Set up custom paragraph styles."""
        self.styles.add(ParagraphStyle(
            'Title_Custom',
            parent=self.styles['Title'],
            fontSize=28,
            textColor=COLORS['primary'],
            spaceAfter=6,
            alignment=TA_CENTER
        ))
        
        self.styles.add(ParagraphStyle(
            'Subtitle_Custom',
            parent=self.styles['Normal'],
            fontSize=14,
            textColor=COLORS['dark'],
            spaceAfter=20,
            alignment=TA_CENTER
        ))
        
        self.styles.add(ParagraphStyle(
            'Section_Header',
            parent=self.styles['Heading2'],
            fontSize=16,
            textColor=COLORS['primary'],
            spaceBefore=20,
            spaceAfter=10
        ))
        
        self.styles.add(ParagraphStyle(
            'Metric_Label',
            parent=self.styles['Normal'],
            fontSize=11,
            textColor=COLORS['dark']
        ))
        
        self.styles.add(ParagraphStyle(
            'Metric_Value',
            parent=self.styles['Normal'],
            fontSize=14,
            textColor=COLORS['black'],
            fontName='Helvetica-Bold'
        ))
        
        self.styles.add(ParagraphStyle(
            'Recommendation',
            parent=self.styles['Normal'],
            fontSize=11,
            textColor=COLORS['dark'],
            leftIndent=20,
            spaceBefore=6
        ))
    
    def generate(
        self, 
        result: AnalysisResult, 
        output_path: Optional[str] = None,
        filename: str = "analysis"
    ) -> bytes:
        """
        Generate a PDF report from analysis results.
        
        Args:
            result: AnalysisResult from AudioAnalyzer
            output_path: Optional path to save PDF (if None, returns bytes)
            filename: Original filename being analyzed
            
        Returns:
            PDF content as bytes
        """
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=letter,
            rightMargin=0.75*inch,
            leftMargin=0.75*inch,
            topMargin=0.75*inch,
            bottomMargin=0.75*inch
        )
        
        story = []
        
        # Header
        story.extend(self._build_header(filename))
        
        # Overall Grade Section
        story.extend(self._build_grade_section(result))
        
        # Loudness Section
        story.extend(self._build_loudness_section(result))
        
        # Stereo Analysis Section
        story.extend(self._build_stereo_section(result))
        
        # Spectral Balance Section
        if self.config.include_spectral_chart:
            story.extend(self._build_spectral_section(result))
        
        # Dynamics Section
        story.extend(self._build_dynamics_section(result))
        
        # Recommendations Section
        if self.config.include_recommendations:
            story.extend(self._build_recommendations_section(result))
        
        # Footer
        story.extend(self._build_footer())
        
        # Build PDF
        doc.build(story)
        
        pdf_bytes = buffer.getvalue()
        buffer.close()
        
        # Optionally save to file
        if output_path:
            with open(output_path, 'wb') as f:
                f.write(pdf_bytes)
        
        return pdf_bytes
    
    def _build_header(self, filename: str) -> list:
        """Build report header section."""
        elements = []
        
        # Title
        elements.append(Paragraph(self.config.title, self.styles['Title_Custom']))
        elements.append(Paragraph(self.config.subtitle, self.styles['Subtitle_Custom']))
        
        # Divider
        elements.append(HRFlowable(
            width="100%",
            thickness=2,
            color=COLORS['primary'],
            spaceAfter=20
        ))
        
        # File info
        info_text = f"<b>File:</b> {filename}<br/><b>Analyzed:</b> {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        elements.append(Paragraph(info_text, self.styles['Normal']))
        elements.append(Spacer(1, 20))
        
        return elements
    
    def _build_grade_section(self, result: AnalysisResult) -> list:
        """Build overall grade display."""
        elements = []
        
        # Create grade badge
        grade_color = GRADE_COLORS.get(result.overall_grade, COLORS['primary'])
        
        grade_table = Table(
            [[Paragraph(f"<b>OVERALL: {result.overall_grade}</b>", 
                       ParagraphStyle('Grade', fontSize=18, textColor=COLORS['white'], alignment=TA_CENTER))]],
            colWidths=[3*inch],
            rowHeights=[0.6*inch]
        )
        grade_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), grade_color),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('ROUNDEDCORNERS', [10, 10, 10, 10]),
        ]))
        
        # Center the grade table
        wrapper = Table([[grade_table]], colWidths=[7*inch])
        wrapper.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ]))
        
        elements.append(wrapper)
        elements.append(Spacer(1, 20))
        
        # Quick stats row
        stats = [
            ['LUFS', 'PHASE', 'SPECTRAL'],
            [result.lufs_grade, result.phase_grade, result.spectral_grade]
        ]
        
        stats_table = Table(stats, colWidths=[2*inch, 2*inch, 2*inch])
        stats_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica'),
            ('FONTNAME', (0, 1), (-1, 1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('FONTSIZE', (0, 1), (-1, 1), 14),
            ('TEXTCOLOR', (0, 1), (0, 1), GRADE_COLORS.get(result.lufs_grade, COLORS['dark'])),
            ('TEXTCOLOR', (1, 1), (1, 1), GRADE_COLORS.get(result.phase_grade, COLORS['dark'])),
            ('TEXTCOLOR', (2, 1), (2, 1), GRADE_COLORS.get(result.spectral_grade, COLORS['dark'])),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ]))
        
        elements.append(stats_table)
        elements.append(Spacer(1, 10))
        
        return elements
    
    def _build_loudness_section(self, result: AnalysisResult) -> list:
        """Build loudness metrics section."""
        elements = []
        
        elements.append(Paragraph("📊 Loudness Analysis", self.styles['Section_Header']))
        
        data = [
            ['Metric', 'Value', 'Target'],
            ['Integrated LUFS', f'{result.integrated_lufs} LUFS', '-14 to -9 LUFS'],
            ['Short-term Max', f'{result.short_term_lufs_max} LUFS', '-'],
            ['True Peak', f'{result.true_peak_db} dB', '< -1 dB'],
        ]
        
        table = Table(data, colWidths=[2.5*inch, 2*inch, 2*inch])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), COLORS['primary']),
            ('TEXTCOLOR', (0, 0), (-1, 0), COLORS['white']),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('GRID', (0, 0), (-1, -1), 0.5, COLORS['light']),
            ('BACKGROUND', (0, 1), (-1, -1), COLORS['white']),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [COLORS['white'], COLORS['light']]),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
            ('TOPPADDING', (0, 0), (-1, -1), 10),
        ]))
        
        elements.append(table)
        elements.append(Spacer(1, 10))
        
        return elements
    
    def _build_stereo_section(self, result: AnalysisResult) -> list:
        """Build stereo analysis section."""
        elements = []
        
        elements.append(Paragraph("🎧 Stereo Analysis", self.styles['Section_Header']))
        
        stereo = result.stereo
        data = [
            ['Metric', 'Value', 'Status'],
            ['Phase Correlation', f'{stereo["phase_correlation"]}', 
             'GOOD' if stereo["phase_correlation"] >= 0.5 else 'CHECK'],
            ['Stereo Width', f'{int(stereo["width"] * 100)}%', 
             'Normal' if 0.2 <= stereo["width"] <= 0.7 else 'Wide' if stereo["width"] > 0.7 else 'Narrow'],
            ['L/R Balance', f'{stereo["balance"]:+.2f}', 
             'Centered' if abs(stereo["balance"]) < 0.1 else 'Off-center'],
        ]
        
        table = Table(data, colWidths=[2.5*inch, 2*inch, 2*inch])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), COLORS['secondary']),
            ('TEXTCOLOR', (0, 0), (-1, 0), COLORS['white']),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('GRID', (0, 0), (-1, -1), 0.5, COLORS['light']),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [COLORS['white'], COLORS['light']]),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
            ('TOPPADDING', (0, 0), (-1, -1), 10),
        ]))
        
        elements.append(table)
        elements.append(Spacer(1, 10))
        
        return elements
    
    def _build_spectral_section(self, result: AnalysisResult) -> list:
        """Build spectral balance section with bar chart."""
        elements = []
        
        elements.append(Paragraph("🎚️ Spectral Balance", self.styles['Section_Header']))
        
        spectral = result.spectral_balance
        
        # Create horizontal bar chart
        drawing = Drawing(500, 150)
        
        chart = HorizontalBarChart()
        chart.x = 100
        chart.y = 10
        chart.width = 350
        chart.height = 120
        
        chart.data = [[
            spectral['sub'],
            spectral['low'],
            spectral['low_mid'],
            spectral['mid'],
            spectral['high_mid'],
            spectral['high']
        ]]
        
        chart.categoryAxis.categoryNames = [
            'Sub (<60Hz)',
            'Low (60-250Hz)',
            'Low-Mid (250-500Hz)',
            'Mid (500Hz-2kHz)',
            'High-Mid (2-8kHz)',
            'High (8kHz+)'
        ]
        
        chart.bars[0].fillColor = COLORS['primary']
        chart.categoryAxis.labels.fontName = 'Helvetica'
        chart.categoryAxis.labels.fontSize = 9
        chart.valueAxis.valueMin = 0
        chart.valueAxis.valueMax = 50
        chart.valueAxis.valueStep = 10
        chart.barWidth = 12
        chart.barSpacing = 3
        
        drawing.add(chart)
        elements.append(drawing)
        
        # Brightness indicator
        elements.append(Paragraph(
            f"<b>Spectral Brightness (Centroid):</b> {int(spectral['brightness'])} Hz",
            self.styles['Normal']
        ))
        elements.append(Spacer(1, 10))
        
        return elements
    
    def _build_dynamics_section(self, result: AnalysisResult) -> list:
        """Build dynamics analysis section."""
        elements = []
        
        elements.append(Paragraph("⚡ Dynamics Analysis", self.styles['Section_Header']))
        
        dynamics = result.dynamics
        data = [
            ['Metric', 'Value'],
            ['RMS Level', f'{dynamics["rms_db"]:.1f} dB'],
            ['Peak Level', f'{dynamics["peak_db"]:.1f} dB'],
            ['Crest Factor', f'{dynamics["crest_factor_db"]:.1f} dB'],
            ['Dynamic Range', f'{dynamics["dynamic_range_db"]:.1f} dB'],
        ]
        
        table = Table(data, colWidths=[3*inch, 3*inch])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), COLORS['dark']),
            ('TEXTCOLOR', (0, 0), (-1, 0), COLORS['white']),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('GRID', (0, 0), (-1, -1), 0.5, COLORS['light']),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [COLORS['white'], COLORS['light']]),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
            ('TOPPADDING', (0, 0), (-1, -1), 10),
        ]))
        
        elements.append(table)
        elements.append(Spacer(1, 10))
        
        return elements
    
    def _build_recommendations_section(self, result: AnalysisResult) -> list:
        """Build recommendations section."""
        elements = []
        
        elements.append(Paragraph("💡 Recommendations", self.styles['Section_Header']))
        
        for i, rec in enumerate(result.recommendations, 1):
            # Determine recommendation severity
            if 'CRITICAL' in rec.upper():
                bullet = '🔴'
            elif any(word in rec.upper() for word in ['EXCESSIVE', 'LOW', 'QUIET', 'COMPRESSED']):
                bullet = '🟡'
            else:
                bullet = '🟢'
            
            elements.append(Paragraph(
                f"{bullet} {rec}",
                self.styles['Recommendation']
            ))
        
        elements.append(Spacer(1, 20))
        return elements
    
    def _build_footer(self) -> list:
        """Build report footer."""
        elements = []
        
        elements.append(HRFlowable(
            width="100%",
            thickness=1,
            color=COLORS['light'],
            spaceBefore=20,
            spaceAfter=10
        ))
        
        footer_text = (
            f"<i>Generated by {self.config.title} • "
            f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} • "
            f"Zero-Touch AI Audio Analysis</i>"
        )
        elements.append(Paragraph(footer_text, ParagraphStyle(
            'Footer',
            fontSize=9,
            textColor=COLORS['dark'],
            alignment=TA_CENTER
        )))
        
        return elements


# Quick test
if __name__ == "__main__":
    from audio_analyzer import AudioAnalyzer
    import sys
    
    if len(sys.argv) > 1:
        analyzer = AudioAnalyzer()
        result = analyzer.analyze(sys.argv[1])
        
        generator = ReportGenerator()
        pdf_bytes = generator.generate(result, output_path="test_report.pdf", filename=sys.argv[1])
        print(f"Generated report: {len(pdf_bytes)} bytes")
