"""
Transcription module for handling audio transcription.

convert_pcm_to_mp3 is gone: the API accepts audio/wav, and a WAV header is
stdlib, so converting to MP3 through pydub meant requiring ffmpeg on the machine
for nothing. pcm_to_wav replaces it. Nothing outside this module used it.
"""

from .transcription_handler import transcribe_audio, pcm_to_wav

__all__ = ['transcribe_audio', 'pcm_to_wav']
