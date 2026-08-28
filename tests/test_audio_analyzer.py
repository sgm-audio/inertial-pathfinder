"""
Unit tests for the AudioAnalyzer engine.
"""
import io
import wave
import tempfile
import os
import numpy as np
import pytest
from src.audio_analyzer import AudioAnalyzer, AnalysisResult


def create_wav_file(sample_rate=44100, duration=2.0, stereo=True, out_of_phase=False):
    """Create a temporary WAV file for analysis. Returns file path.

    Args:
        sample_rate: Sample rate in Hz
        duration: Duration in seconds
        stereo: If True, produces 2-channel audio
        out_of_phase: If True, right channel is inverted (for phase testing)
    """
    n_samples = int(sample_rate * duration)
    t = np.linspace(0, duration, n_samples, endpoint=False)

    # A4 tone (440 Hz) as the primary signal
    signal_left = 0.5 * np.sin(2 * np.pi * 440 * t)
    signal_left = signal_left / np.max(np.abs(signal_left)) * 0.8
    signal_left_int = (signal_left * 32767).astype(np.int16)

    if stereo:
        if out_of_phase:
            signal_right = -signal_left
        else:
            signal_right = signal_left
        signal_right_int = (signal_right * 32767).astype(np.int16)
        data = np.column_stack([signal_left_int, signal_right_int])
        nchannels = 2
    else:
        data = signal_left_int
        nchannels = 1

    tmp = tempfile.NamedTemporaryFile(suffix='.wav', delete=False)
    path = tmp.name
    tmp.close()

    with wave.open(path, 'wb') as wf:
        wf.setnchannels(nchannels)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(data.tobytes())

    return path


def create_silence_wav(sample_rate=44100, duration=1.0):
    """Create a near-silent WAV (very quiet signal)."""
    n_samples = int(sample_rate * duration)
    signal = np.zeros((n_samples, 2), dtype=np.int16)
    signal[:, 0] = 1  # Tiny non-zero signal to avoid true silence
    signal[:, 1] = 1

    tmp = tempfile.NamedTemporaryFile(suffix='.wav', delete=False)
    path = tmp.name
    tmp.close()

    with wave.open(path, 'wb') as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(signal.tobytes())

    return path


class TestAudioAnalyzerConstruction:
    """Test AudioAnalyzer initialisation and defaults."""

    def test_default_construction(self):
        analyzer = AudioAnalyzer()
        assert analyzer.lufs_min == -14.0
        assert analyzer.lufs_max == -9.0
        assert analyzer.phase_min == 0.5

    def test_custom_thresholds(self):
        analyzer = AudioAnalyzer(lufs_min=-20.0, lufs_max=-6.0, phase_min=0.3)
        assert analyzer.lufs_min == -20.0
        assert analyzer.lufs_max == -6.0
        assert analyzer.phase_min == 0.3


class TestAudioAnalyzerAnalysis:
    """Test the core analysis pipeline."""

    def test_analyze_returns_correct_type(self):
        analyzer = AudioAnalyzer()
        path = create_wav_file()
        try:
            result = analyzer.analyze(path)
            assert isinstance(result, AnalysisResult)
        finally:
            os.unlink(path)

    def test_duration_and_sample_rate(self):
        analyzer = AudioAnalyzer()
        path = create_wav_file(sample_rate=44100, duration=2.0)
        try:
            result = analyzer.analyze(path)
            assert result.sample_rate == 44100
            assert 1.9 <= result.duration_seconds <= 2.1
        finally:
            os.unlink(path)

    def test_stereo_file_channels(self):
        analyzer = AudioAnalyzer()
        path = create_wav_file(stereo=True)
        try:
            result = analyzer.analyze(path)
            assert result.channels == 2
        finally:
            os.unlink(path)


class TestLUFS:
    """Test LUFS measurement."""

    def test_integrated_lufs_is_float(self):
        analyzer = AudioAnalyzer()
        path = create_wav_file()
        try:
            result = analyzer.analyze(path)
            assert isinstance(result.integrated_lufs, float)
            assert -30 < result.integrated_lufs < 10
        finally:
            os.unlink(path)

    def test_true_peak_is_finite(self):
        analyzer = AudioAnalyzer()
        path = create_wav_file()
        try:
            result = analyzer.analyze(path)
            assert result.true_peak_db > -100
            assert result.true_peak_db < 50
        finally:
            os.unlink(path)

    def test_short_term_lufs_present(self):
        analyzer = AudioAnalyzer()
        path = create_wav_file(duration=4.0)
        try:
            result = analyzer.analyze(path)
            assert isinstance(result.short_term_lufs_max, float)
        finally:
            os.unlink(path)


class TestPhaseCorrelation:
    """Test phase correlation (stereo)."""

    def test_identical_channels_positive_correlation(self):
        analyzer = AudioAnalyzer()
        path = create_wav_file(stereo=True, out_of_phase=False)
        try:
            result = analyzer.analyze(path)
            # Identical channels should have very high correlation
            assert result.stereo["phase_correlation"] > 0.9
        finally:
            os.unlink(path)

    def test_out_of_phase_channels_negative_correlation(self):
        analyzer = AudioAnalyzer()
        path = create_wav_file(stereo=True, out_of_phase=True)
        try:
            result = analyzer.analyze(path)
            # Out of phase should be near -1
            assert result.stereo["phase_correlation"] < -0.9
        finally:
            os.unlink(path)

    def test_phase_grade_fail_on_negative(self):
        analyzer = AudioAnalyzer()
        path = create_wav_file(stereo=True, out_of_phase=True)
        try:
            result = analyzer.analyze(path)
            assert result.phase_grade == "FAIL"
            assert any("phase" in rec.lower() for rec in result.recommendations)
        finally:
            os.unlink(path)


class TestSpectralBalance:
    """Test spectral balance analysis."""

    def test_all_bands_present(self):
        analyzer = AudioAnalyzer()
        path = create_wav_file()
        try:
            result = analyzer.analyze(path)
            sb = result.spectral_balance
            expected = ['sub', 'low', 'low_mid', 'mid', 'high_mid', 'high', 'brightness']
            for band in expected:
                assert band in sb, f"Missing band: {band}"
                assert isinstance(sb[band], (int, float)), f"Non-numeric band: {band}"
        finally:
            os.unlink(path)

    def test_brightness_is_positive(self):
        analyzer = AudioAnalyzer()
        path = create_wav_file()  # 440 Hz + harmonics
        try:
            result = analyzer.analyze(path)
            # With a 440 Hz tone, centroid should be well above zero
            assert result.spectral_balance["brightness"] > 0
        finally:
            os.unlink(path)

    def test_band_energies_sum_to_roughly_100(self):
        analyzer = AudioAnalyzer()
        path = create_wav_file()
        try:
            result = analyzer.analyze(path)
            sb = result.spectral_balance
            total = sum(
                sb[b] for b in ['sub', 'low', 'low_mid', 'mid', 'high_mid', 'high']
            )
            # Band percentages should sum close to 100
            assert 95 <= total <= 105, f"Band sum {total} not near 100"
        finally:
            os.unlink(path)


class TestDynamics:
    """Test dynamic range analysis."""

    def test_dynamics_structure(self):
        analyzer = AudioAnalyzer()
        path = create_wav_file()
        try:
            result = analyzer.analyze(path)
            d = result.dynamics
            assert "rms_db" in d
            assert "peak_db" in d
            assert "crest_factor_db" in d
            assert "dynamic_range_db" in d
        finally:
            os.unlink(path)

    def test_crest_factor_positive_for_non_dc_signal(self):
        analyzer = AudioAnalyzer()
        path = create_wav_file()
        try:
            result = analyzer.analyze(path)
            # Crest factor should be > 0 for a sine wave
            assert result.dynamics["crest_factor_db"] > 0
        finally:
            os.unlink(path)

    def test_peak_above_rms(self):
        analyzer = AudioAnalyzer()
        path = create_wav_file()
        try:
            result = analyzer.analyze(path)
            assert result.dynamics["peak_db"] > result.dynamics["rms_db"]
        finally:
            os.unlink(path)


class TestStereoWidthAndBalance:
    """Test stereo width and balance."""

    def test_identical_channels_narrow_width(self):
        analyzer = AudioAnalyzer()
        path = create_wav_file(stereo=True, out_of_phase=False)
        try:
            result = analyzer.analyze(path)
            # Identical channels should have near-zero stereo width
            assert result.stereo["width"] < 0.1
        finally:
            os.unlink(path)

    def test_out_of_phase_wide_width(self):
        analyzer = AudioAnalyzer()
        path = create_wav_file(stereo=True, out_of_phase=True)
        try:
            result = analyzer.analyze(path)
            # Out-of-phase should have high stereo width
            assert result.stereo["width"] > 0.5
        finally:
            os.unlink(path)

    def test_balance_near_zero_for_identical_channels(self):
        analyzer = AudioAnalyzer()
        path = create_wav_file(stereo=True, out_of_phase=False)
        try:
            result = analyzer.analyze(path)
            assert abs(result.stereo["balance"]) < 0.1
        finally:
            os.unlink(path)


class TestGrading:
    """Test the grading engine."""

    def test_overall_grade_is_string(self):
        analyzer = AudioAnalyzer()
        path = create_wav_file()
        try:
            result = analyzer.analyze(path)
            assert result.overall_grade in (
                "EXCELLENT", "GOOD", "NEEDS WORK", "CRITICAL ISSUES"
            )
        finally:
            os.unlink(path)

    def test_lufs_grade_is_string(self):
        analyzer = AudioAnalyzer()
        path = create_wav_file()
        try:
            result = analyzer.analyze(path)
            assert result.lufs_grade in ("PASS", "FAIL", "WARNING")
        finally:
            os.unlink(path)

    def test_recommendations_not_empty(self):
        analyzer = AudioAnalyzer()
        path = create_wav_file()
        try:
            result = analyzer.analyze(path)
            assert len(result.recommendations) > 0
            assert all(isinstance(r, str) for r in result.recommendations)
        finally:
            os.unlink(path)

    def test_phase_fail_gives_recommendation(self):
        analyzer = AudioAnalyzer()
        path = create_wav_file(stereo=True, out_of_phase=True)
        try:
            result = analyzer.analyze(path)
            assert result.phase_grade == "FAIL"
            assert any("phase" in r.lower() for r in result.recommendations)
        finally:
            os.unlink(path)


class TestToDict:
    """Test serialization."""

    def test_to_dict_is_json_serializable(self):
        import json
        analyzer = AudioAnalyzer()
        path = create_wav_file()
        try:
            result = analyzer.analyze(path)
            d = result.to_dict()
            output = json.dumps(d)
            assert isinstance(output, str)
            assert len(output) > 0
        finally:
            os.unlink(path)

    def test_to_dict_contains_all_top_level_keys(self):
        analyzer = AudioAnalyzer()
        path = create_wav_file()
        try:
            result = analyzer.analyze(path)
            d = result.to_dict()
            for key in (
                "integrated_lufs", "short_term_lufs_max", "true_peak_db",
                "spectral_balance", "dynamics", "stereo",
                "duration_seconds", "sample_rate", "channels",
                "lufs_grade", "phase_grade", "spectral_grade",
                "overall_grade", "recommendations"
            ):
                assert key in d, f"Missing key: {key}"
        finally:
            os.unlink(path)

    def test_to_dict_no_numpy_types(self):
        analyzer = AudioAnalyzer()
        path = create_wav_file()
        try:
            result = analyzer.analyze(path)
            d = result.to_dict()

            def _check_no_numpy(obj, path=""):
                if isinstance(obj, dict):
                    for k, v in obj.items():
                        _check_no_numpy(v, f"{path}.{k}")
                elif isinstance(obj, list):
                    for i, v in enumerate(obj):
                        _check_no_numpy(v, f"{path}[{i}]")
                else:
                    assert not hasattr(obj, "item"), (
                        f"Numpy scalar at {path}: {type(obj)}"
                    )

            _check_no_numpy(d)
        finally:
            os.unlink(path)
