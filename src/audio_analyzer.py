"""
Sonic Mind Forge - Core Audio Analysis Engine

Audio analysis for mix feedback.
Measures LUFS, phase correlation, spectral balance, dynamic range, and stereo width.
"""

import numpy as np
import librosa
import pyloudnorm as pyln
from typing import TypedDict, Optional
from dataclasses import dataclass, asdict
from scipy import signal


class SpectralBalance(TypedDict):
    """Frequency band energy distribution."""
    sub: float          # < 60 Hz
    low: float          # 60 - 250 Hz
    low_mid: float      # 250 Hz - 500 Hz
    mid: float          # 500 Hz - 2 kHz
    high_mid: float     # 2 kHz - 8 kHz
    high: float         # 8 kHz +
    brightness: float   # Spectral centroid


class DynamicRange(TypedDict):
    """Dynamic characteristics of the audio."""
    rms_db: float           # Average RMS level in dB
    peak_db: float          # Peak level in dB
    crest_factor_db: float  # Peak-to-RMS ratio
    dynamic_range_db: float # Loudness Range (LRA approximation)


class StereoAnalysis(TypedDict):
    """Stereo field characteristics."""
    width: float              # Stereo width (0 = mono, 1 = full stereo)
    phase_correlation: float  # -1 to +1 (< 0.5 = mono compatibility issues)
    balance: float            # L/R balance (-1 = left, 0 = center, 1 = right)


@dataclass
class AnalysisResult:
    """Complete audio analysis result."""
    # Loudness
    integrated_lufs: float
    short_term_lufs_max: float
    true_peak_db: float
    
    # Spectral
    spectral_balance: SpectralBalance
    
    # Dynamics
    dynamics: DynamicRange
    
    # Stereo
    stereo: StereoAnalysis
    
    # Metadata
    duration_seconds: float
    sample_rate: int
    channels: int
    
    # Grading (pass/fail indicators)
    lufs_grade: str
    phase_grade: str
    spectral_grade: str
    overall_grade: str
    recommendations: list[str]
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        def convert_value(v):
            """Recursively convert numpy types to Python native types."""
            if isinstance(v, dict):
                return {k: convert_value(val) for k, val in v.items()}
            elif isinstance(v, list):
                return [convert_value(item) for item in v]
            elif hasattr(v, 'item'):  # numpy scalar
                return v.item()
            elif isinstance(v, float):
                return float(v)
            elif isinstance(v, int):
                return int(v)
            return v
        
        return convert_value(asdict(self))


class AudioAnalyzer:
    """
    Professional audio analysis engine.
    
    Targets (customizable):
    - LUFS: -14 to -9 (streaming/mastering range)
    - Phase correlation: > 0.5 (mono compatible)
    - Sub bass: < 15% of total energy
    - Muddy range (200-500Hz): < 25% of total energy
    """
    
    # Analysis target thresholds
    LUFS_TARGET_MIN = -14.0
    LUFS_TARGET_MAX = -9.0
    PHASE_CORRELATION_MIN = 0.5
    SUB_BASS_MAX_PERCENT = 15.0
    MUDDY_MAX_PERCENT = 25.0
    
    # Frequency band boundaries (Hz)
    FREQ_BANDS = {
        'sub': (20, 60),
        'low': (60, 250),
        'low_mid': (250, 500),
        'mid': (500, 2000),
        'high_mid': (2000, 8000),
        'high': (8000, 20000)
    }
    
    def __init__(
        self,
        lufs_min: float = LUFS_TARGET_MIN,
        lufs_max: float = LUFS_TARGET_MAX,
        phase_min: float = PHASE_CORRELATION_MIN
    ):
        self.lufs_min = lufs_min
        self.lufs_max = lufs_max
        self.phase_min = phase_min
        self.meter = pyln.Meter(44100)  # Will be reinitialized per file
    
    def analyze(self, file_path: str) -> AnalysisResult:
        """
        Perform complete audio analysis on a file.
        
        Args:
            file_path: Path to audio file (WAV, MP3, FLAC, etc.)
            
        Returns:
            AnalysisResult with all metrics and grades
        """
        # Load audio
        y, sr = librosa.load(file_path, sr=None, mono=False)
        
        # Handle mono files
        if y.ndim == 1:
            y = np.stack([y, y])  # Duplicate to stereo for consistent processing
            channels = 1
        else:
            channels = y.shape[0]
        
        # Reinitialize meter for this sample rate
        self.meter = pyln.Meter(sr)
        
        duration = len(y[0]) / sr
        
        # Perform all analyses
        lufs_data = self._analyze_loudness(y, sr)
        spectral = self._analyze_spectral(y, sr)
        dynamics = self._analyze_dynamics(y)
        stereo = self._analyze_stereo(y)
        
        # Generate grades and recommendations
        grades = self._generate_grades(lufs_data, stereo, spectral)
        
        return AnalysisResult(
            integrated_lufs=lufs_data['integrated'],
            short_term_lufs_max=lufs_data['short_term_max'],
            true_peak_db=lufs_data['true_peak'],
            spectral_balance=spectral,
            dynamics=dynamics,
            stereo=stereo,
            duration_seconds=round(duration, 2),
            sample_rate=sr,
            channels=channels,
            lufs_grade=grades['lufs'],
            phase_grade=grades['phase'],
            spectral_grade=grades['spectral'],
            overall_grade=grades['overall'],
            recommendations=grades['recommendations']
        )
    
    def _analyze_loudness(self, y: np.ndarray, sr: int) -> dict:
        """Analyze loudness using ITU-R BS.1770-4 standard."""
        # Prepare stereo array for pyloudnorm (samples x channels)
        audio_stereo = y.T
        
        # Integrated LUFS
        try:
            integrated = self.meter.integrated_loudness(audio_stereo)
        except Exception:
            integrated = -23.0  # Default if analysis fails
        
        # Short-term loudness (3 second windows)
        window_samples = int(3 * sr)
        hop_samples = int(sr)  # 1 second hop
        short_term_values = []
        
        for i in range(0, len(audio_stereo) - window_samples, hop_samples):
            chunk = audio_stereo[i:i + window_samples]
            try:
                st_lufs = self.meter.integrated_loudness(chunk)
                if not np.isinf(st_lufs):
                    short_term_values.append(st_lufs)
            except Exception:
                continue
        
        short_term_max = max(short_term_values) if short_term_values else integrated
        
        # True peak
        true_peak = 20 * np.log10(np.max(np.abs(y)) + 1e-10)
        
        return {
            'integrated': round(integrated, 1),
            'short_term_max': round(short_term_max, 1),
            'true_peak': round(true_peak, 1)
        }
    
    def _analyze_spectral(self, y: np.ndarray, sr: int) -> SpectralBalance:
        """Analyze frequency distribution across bands."""
        # Mix to mono for spectral analysis
        y_mono = np.mean(y, axis=0)
        
        # Compute STFT
        n_fft = 4096
        D = np.abs(librosa.stft(y_mono, n_fft=n_fft))
        freqs = librosa.fft_frequencies(sr=sr, n_fft=n_fft)
        
        # Calculate energy in each band
        total_energy = np.sum(D ** 2)
        band_energies = {}
        
        for band_name, (low_freq, high_freq) in self.FREQ_BANDS.items():
            mask = (freqs >= low_freq) & (freqs < high_freq)
            band_energy = np.sum(D[mask] ** 2)
            band_energies[band_name] = float(round(
                (band_energy / total_energy) * 100, 1
            )) if total_energy > 0 else 0.0
        
        # Spectral centroid (brightness indicator)
        centroid = librosa.feature.spectral_centroid(y=y_mono, sr=sr)
        brightness = float(np.mean(centroid))
        
        return SpectralBalance(
            sub=band_energies['sub'],
            low=band_energies['low'],
            low_mid=band_energies['low_mid'],
            mid=band_energies['mid'],
            high_mid=band_energies['high_mid'],
            high=band_energies['high'],
            brightness=round(brightness, 0)
        )
    
    def _analyze_dynamics(self, y: np.ndarray) -> DynamicRange:
        """Analyze dynamic range and crest factor."""
        # Mix to mono
        y_mono = np.mean(y, axis=0)
        
        # RMS (with small epsilon to avoid log of zero)
        rms = np.sqrt(np.mean(y_mono ** 2))
        rms_db = 20 * np.log10(rms + 1e-10)
        
        # Peak
        peak = np.max(np.abs(y_mono))
        peak_db = 20 * np.log10(peak + 1e-10)
        
        # Crest factor (peak-to-RMS ratio)
        crest_factor = peak_db - rms_db
        
        # Dynamic range approximation (simplified LRA)
        # Calculate RMS in 400ms windows
        window_size = int(0.4 * 44100)  # Approximate
        hop_size = window_size // 4
        
        rms_windows = []
        for i in range(0, len(y_mono) - window_size, hop_size):
            chunk_rms = np.sqrt(np.mean(y_mono[i:i + window_size] ** 2))
            if chunk_rms > 1e-6:  # Exclude silence
                rms_windows.append(20 * np.log10(chunk_rms + 1e-10))
        
        if len(rms_windows) > 10:
            rms_windows = np.array(rms_windows)
            # LRA approximation: difference between 95th and 10th percentile
            dynamic_range = float(np.percentile(rms_windows, 95) - np.percentile(rms_windows, 10))
        else:
            dynamic_range = 0.0
        
        return DynamicRange(
            rms_db=round(rms_db, 1),
            peak_db=round(peak_db, 1),
            crest_factor_db=round(crest_factor, 1),
            dynamic_range_db=round(dynamic_range, 1)
        )
    
    def _analyze_stereo(self, y: np.ndarray) -> StereoAnalysis:
        """Analyze stereo field characteristics."""
        left = y[0]
        right = y[1]
        
        # Mid/Side encoding
        mid = (left + right) / 2
        side = (left - right) / 2
        
        # Stereo width (ratio of side to mid energy)
        mid_energy = np.sum(mid ** 2)
        side_energy = np.sum(side ** 2)
        
        total_energy = mid_energy + side_energy
        if total_energy > 0:
            width = float(np.clip(side_energy / total_energy, 0.0, 1.0))
        else:
            width = 0.0
        
        # Phase correlation (Pearson correlation coefficient)
        # +1 = perfectly correlated (mono), 0 = uncorrelated, -1 = out of phase
        if np.std(left) > 0 and np.std(right) > 0:
            correlation = np.corrcoef(left, right)[0, 1]
        else:
            correlation = 1.0
        
        # L/R Balance
        left_rms = np.sqrt(np.mean(left ** 2))
        right_rms = np.sqrt(np.mean(right ** 2))
        
        if left_rms + right_rms > 0:
            balance = (right_rms - left_rms) / (left_rms + right_rms)
        else:
            balance = 0.0
        
        return StereoAnalysis(
            width=round(float(width), 2),
            phase_correlation=round(float(correlation), 2),
            balance=round(float(balance), 2)
        )
    
    def _generate_grades(
        self,
        lufs_data: dict,
        stereo: StereoAnalysis,
        spectral: SpectralBalance
    ) -> dict:
        """Generate pass/fail grades and recommendations."""
        recommendations = []
        grades = {}
        
        # LUFS Grade
        lufs = lufs_data['integrated']
        if self.lufs_min <= lufs <= self.lufs_max:
            grades['lufs'] = 'PASS'
        elif lufs < self.lufs_min:
            grades['lufs'] = 'FAIL'
            recommendations.append(
                f"Mix is too quiet ({lufs} LUFS). Target: {self.lufs_min} to {self.lufs_max} LUFS."
            )
        else:
            grades['lufs'] = 'WARNING'
            recommendations.append(
                f"Mix may be over-compressed ({lufs} LUFS). Consider more dynamics."
            )
        
        # Phase Grade
        phase = stereo['phase_correlation']
        if phase >= self.phase_min:
            grades['phase'] = 'PASS'
        elif phase >= 0:
            grades['phase'] = 'WARNING'
            recommendations.append(
                f"Phase correlation is low ({phase}). May have mono compatibility issues."
            )
        else:
            grades['phase'] = 'FAIL'
            recommendations.append(
                f"CRITICAL: Negative phase correlation ({phase}). Mix will cancel in mono!"
            )
        
        # Spectral Grade
        spectral_issues = []
        
        if spectral['sub'] > self.SUB_BASS_MAX_PERCENT:
            spectral_issues.append(f"Excessive sub-bass ({spectral['sub']}% > {self.SUB_BASS_MAX_PERCENT}%)")
        
        muddy = spectral['low_mid']
        if muddy > self.MUDDY_MAX_PERCENT:
            spectral_issues.append(f"Muddy low-mids ({muddy}% > {self.MUDDY_MAX_PERCENT}%)")
        
        if spectral['high'] < 5:
            spectral_issues.append("Mix lacks high-frequency presence (< 5%)")
        
        if spectral_issues:
            grades['spectral'] = 'WARNING'
            recommendations.extend(spectral_issues)
        else:
            grades['spectral'] = 'PASS'
        
        # Overall Grade
        grade_values = {'PASS': 2, 'WARNING': 1, 'FAIL': 0}
        avg_grade = np.mean([grade_values[g] for g in [grades['lufs'], grades['phase'], grades['spectral']]])
        
        if avg_grade >= 1.8:
            grades['overall'] = 'EXCELLENT'
        elif avg_grade >= 1.3:
            grades['overall'] = 'GOOD'
        elif avg_grade >= 0.8:
            grades['overall'] = 'NEEDS WORK'
        else:
            grades['overall'] = 'CRITICAL ISSUES'
        
        if not recommendations:
            recommendations.append("Mix meets all technical standards. Great job!")
        
        grades['recommendations'] = recommendations
        return grades


# Quick test function
if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        analyzer = AudioAnalyzer()
        result = analyzer.analyze(sys.argv[1])
        import json
        print(json.dumps(result.to_dict(), indent=2))
