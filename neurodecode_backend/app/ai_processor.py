from __future__ import annotations

import base64
import os
import threading
from typing import Any

import cv2
import numpy as np


class NeuroDecodeAI:
    """Lazy-loaded AI inference helper for vision/audio observer notes.

    This class intentionally degrades gracefully: if model load or inference fails,
    it returns an empty note so the live WebSocket flow is never blocked.
    """

    def __init__(self) -> None:
        self._video_extractor: Any | None = None
        self._audio_extractor: Any | None = None
        self._vgg16_eyes: Any | None = None
        self._models_loaded = False
        self._lock = threading.Lock()

    def _lazy_load_models(self) -> None:
        if self._models_loaded:
            return

        with self._lock:
            if self._models_loaded:
                return

            print("[AI Engine] Lazy loading TensorFlow + Keras models...")
            try:
                from tensorflow.keras.applications.vgg16 import VGG16
                from tensorflow.keras.models import load_model

                base_dir = os.path.dirname(os.path.abspath(__file__))

                audio_path = os.path.join(base_dir, "models", "autism_audio_extractor.keras")
                if os.path.exists(audio_path):
                    self._audio_extractor = load_model(audio_path)
                    print("[AI Engine] Loaded audio extractor")

                video_path = os.path.join(base_dir, "models", "autism_behavior_extractor.keras")
                if os.path.exists(video_path):
                    self._video_extractor = load_model(video_path)
                    # VGG16 produces dense visual features that match the Colab pipeline.
                    self._vgg16_eyes = VGG16(weights="imagenet", include_top=False, pooling="avg")
                    print("[AI Engine] Loaded video extractor + VGG16")

                self._models_loaded = True
                print("[AI Engine] Lazy load complete")
            except Exception as e:
                # Keep serving even if model loading fails.
                print(f"[AI Engine] Model load failed: {e}")

    @staticmethod
    def _sigmoid(x: float) -> float:
        return float(1.0 / (1.0 + np.exp(-x)))

    def process_audio_chunk(self, audio_bytes: bytes, sr: int = 16000) -> str:
        """Return an observer note if audio pattern indicates distress risk."""
        self._lazy_load_models()
        if self._audio_extractor is None:
            return ""

        try:
            import librosa

            audio_arr = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32) / 32768.0
            if audio_arr.size < 1024:
                return ""

            mfcc = librosa.feature.mfcc(y=audio_arr, sr=sr, n_mfcc=40)
            mfcc_scaled = np.mean(mfcc.T, axis=0)
            input_data = np.expand_dims(np.expand_dims(mfcc_scaled, axis=0), axis=2)

            features = self._audio_extractor.predict(input_data, verbose=0)
            raw_score = float(np.mean(np.abs(features[0])))
            distress_score = self._sigmoid(raw_score)
            print(f"[AI Engine] Audio: raw={raw_score:.4f} sigmoid={distress_score:.4f} threshold=0.68")

            if distress_score > 0.68:
                return (
                    "[Audio Observer Note] Potential distress pattern detected in vocal tone. "
                    "Offer calm, short verbal reassurance and reduce stimulation."
                )
            return ""
        except Exception as e:
            print(f"[AI Engine] Audio inference error: {e}")
            return ""

    def process_vision_frame(self, base64_image: str) -> str:
        """Return an observer note if visual pattern indicates repetitive movement risk."""
        self._lazy_load_models()
        if self._video_extractor is None or self._vgg16_eyes is None:
            return ""

        try:
            from tensorflow.keras.applications.vgg16 import preprocess_input

            img_bytes = base64.b64decode(base64_image)
            np_arr = np.frombuffer(img_bytes, np.uint8)
            frame = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
            if frame is None:
                return ""

            frame_resized = cv2.resize(frame, (224, 224))
            frame_rgb = cv2.cvtColor(frame_resized, cv2.COLOR_BGR2RGB)

            x = np.expand_dims(frame_rgb.astype(np.float32), axis=0)
            x = preprocess_input(x)
            feature_512 = self._vgg16_eyes.predict(x, verbose=0)  # expected shape (1, 512)

            input_shape = getattr(self._video_extractor, "input_shape", None)
            if isinstance(input_shape, list):
                input_shape = input_shape[0]

            # Adapt to either (batch, 512) or (batch, timesteps, 512)-style models.
            if isinstance(input_shape, tuple) and len(input_shape) == 2:
                model_input = feature_512
            elif isinstance(input_shape, tuple) and len(input_shape) == 3:
                timesteps = input_shape[1] if isinstance(input_shape[1], int) and input_shape[1] > 0 else 1
                model_input = np.repeat(feature_512[:, np.newaxis, :], repeats=timesteps, axis=1)
            else:
                model_input = feature_512

            behavior_features = self._video_extractor.predict(model_input, verbose=0)
            raw_score = float(np.max(np.abs(behavior_features[0])))
            stimming_confidence = self._sigmoid(raw_score)
            print(f"[AI Engine] Vision: raw={raw_score:.4f} sigmoid={stimming_confidence:.4f} threshold=0.7")

            if stimming_confidence > 0.7:
                return (
                    "[Visual Observer Note] Possible repetitive movement pattern detected. "
                    "Guide caregiver to reduce sensory load and offer grounding support."
                )
            return ""
        except Exception as e:
            print(f"[AI Engine] Vision inference error: {e}")
            return ""


ai_engine = NeuroDecodeAI()
