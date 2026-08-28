"""
Unit tests for the ReportGenerator.
"""
import io
import numpy as np
import pytest
from src.audio_analyzer import AudioAnalyzer, AnalysisResult
from src.report_generator import ReportGenerator, ReportConfig, COLORS, GRADE_COLORS

# Re-use the same WAV fixture helper
import wave
import tempfile
import os


def _create_wav(sample_rate=44100, duration=1.0):
    """Quick WAV fixture for report tests."""
    n = int(sample_rate * duration)
    t = np.linspace(0, duration, n, endpoint=False)
    left = (0.5 * np.sin(2 * np.pi * 440 * t) * 0.8 * 32767).astype(np.int16)
    right = left
    data = np.column_stack([left, right])
    tmp = tempfile.NamedTemporaryFile(suffix='.wav', delete=False)
    path = tmp.name
    tmp.close()
    with wave.open(path, 'wb') as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(data.tobytes())
    return path


def _get_analysis_result(path):
    analyzer = AudioAnalyzer()
    return analyzer.analyze(path)


class TestReportConfig:
    """Test report configuration."""

    def test_default_config(self):
        config = ReportConfig()
        assert config.title == "Sonic Mind Forge"
        assert config.subtitle == "AI Audio Analysis Report"
        assert config.include_spectral_chart is True
        assert config.include_recommendations is True

    def test_custom_config(self):
        config = ReportConfig(
            title="Custom Title",
            include_spectral_chart=False,
            include_recommendations=False
        )
        assert config.title == "Custom Title"
        assert config.include_spectral_chart is False


class TestReportGeneration:
    """Test PDF report generation."""

    def test_generate_returns_bytes(self):
        path = _create_wav()
        try:
            result = _get_analysis_result(path)
            generator = ReportGenerator()
            pdf_bytes = generator.generate(result, filename="test.wav")
            assert isinstance(pdf_bytes, bytes)
            assert len(pdf_bytes) > 0
        finally:
            os.unlink(path)

    def test_generate_produces_valid_pdf(self):
        path = _create_wav()
        try:
            result = _get_analysis_result(path)
            generator = ReportGenerator()
            pdf_bytes = generator.generate(result, filename="test.wav")
            # PDF must start with %PDF-
            assert pdf_bytes.startswith(b'%PDF-'), (
                f"First 20 bytes: {pdf_bytes[:20]!r}"
            )
        finally:
            os.unlink(path)

    def test_generate_with_output_path(self):
        path = _create_wav()
        try:
            result = _get_analysis_result(path)
            generator = ReportGenerator()
            out = tempfile.NamedTemporaryFile(suffix='.pdf', delete=False)
            out_path = out.name
            out.close()
            try:
                pdf_bytes = generator.generate(
                    result, output_path=out_path, filename="test.wav"
                )
                assert os.path.exists(out_path)
                with open(out_path, 'rb') as f:
                    saved = f.read()
                assert saved == pdf_bytes
            finally:
                os.unlink(out_path)
        finally:
            os.unlink(path)

    def test_non_trivial_size(self):
        path = _create_wav()
        try:
            result = _get_analysis_result(path)
            generator = ReportGenerator()
            pdf_bytes = generator.generate(result, filename="test.wav")
            # Should be more than a few hundred bytes
            assert len(pdf_bytes) > 500
        finally:
            os.unlink(path)


class TestColorConstants:
    """Verify the color and grade mappings are complete."""

    def test_grade_colors_have_expected_keys(self):
        expected = {'PASS', 'EXCELLENT', 'GOOD', 'WARNING', 'NEEDS WORK',
                     'FAIL', 'CRITICAL ISSUES'}
        assert expected == set(GRADE_COLORS.keys())

    def test_color_dict_has_keys(self):
        for key in ('primary', 'secondary', 'success', 'warning', 'danger',
                     'dark', 'light', 'white', 'black'):
            assert key in COLORS, f"Missing color: {key}"
