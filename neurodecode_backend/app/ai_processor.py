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
        self._model_load_attempted = False
        self._warmup_started = False
        self._lock = threading.Lock()

    @staticmethod
    def _resolve_vgg16_weights_path(base_dir: str) -> str | None:
        candidates = [
            os.getenv("NEURODECODE_VGG16_WEIGHTS_PATH", "").strip(),
            os.path.join(
                base_dir,
                "models",
                "vgg16_weights_tf_dim_ordering_tf_kernels_notop.h5",
            ),
        ]
        for candidate in candidates:
            if candidate and os.path.exists(candidate):
                return candidate
        return None

    def start_background_warmup(self) -> None:
        if self._warmup_started:
            return
        with self._lock:
            if self._warmup_started:
                return
            self._warmup_started = True
        threading.Thread(target=self._lazy_load_models, daemon=True).start()

    @staticmethod
    def _validate_local_model_path(model_path: str, models_dir: str) -> str:
        real_models_dir = os.path.realpath(models_dir)
        real_model_path = os.path.realpath(model_path)

        # Prevent path traversal / unexpected file loading.
        if not real_model_path.startswith(real_models_dir + os.sep):
            raise ValueError("Model path must stay inside app/models")

        # This service only expects native Keras v3 model files.
        if not real_model_path.lower().endswith(".keras"):
            raise ValueError("Only .keras model files are allowed")

        if not os.path.exists(real_model_path):
            raise FileNotFoundError(real_model_path)

        # Defensive limit to reduce accidental oversized/corrupted model loads.
        max_bytes = 256 * 1024 * 1024
        if os.path.getsize(real_model_path) > max_bytes:
            raise ValueError("Model file is unexpectedly large")

        return real_model_path

    @staticmethod
    def _load_keras_model(model_path: str, models_dir: str) -> Any:
        from keras import initializers
        from keras.models import load_model

        custom_objects = {
            "Orthogonal": initializers.Orthogonal,
            "GlorotUniform": initializers.GlorotUniform,
            "Zeros": initializers.Zeros,
        }

        safe_model_path = NeuroDecodeAI._validate_local_model_path(
            model_path,
            models_dir,
        )

        return load_model(
            safe_model_path,
            compile=False,
            custom_objects=custom_objects,
            safe_mode=True,
        )

    def _lazy_load_models(self) -> None:
        if self._models_loaded or self._model_load_attempted:
            return

        with self._lock:
            if self._models_loaded or self._model_load_attempted:
                return

            self._model_load_attempted = True

            print("[AI Engine] Lazy loading TensorFlow + Keras models...")
            try:
                # NOTE: The training notebook saves models via `keras` (not `tf.keras`).
                # Loading them with `tensorflow.keras` can fail with errors like:
                # "keras.src.models.functional cannot be imported".
                from keras.applications.vgg16 import VGG16

                base_dir = os.path.dirname(os.path.abspath(__file__))

                models_dir = os.path.join(base_dir, "models")

                audio_path = os.path.join(models_dir, "autism_audio_extractor.keras")
                if os.path.exists(audio_path):
                    self._audio_extractor = self._load_keras_model(
                        audio_path,
                        models_dir,
                    )
                    print("[AI Engine] Loaded audio extractor")

                video_path = os.path.join(models_dir, "autism_behavior_extractor.keras")
                if os.path.exists(video_path):
                    self._video_extractor = self._load_keras_model(
                        video_path,
                        models_dir,
                    )
                    # VGG16 produces dense visual features that match the Colab pipeline.
                    local_vgg16_weights = self._resolve_vgg16_weights_path(base_dir)
                    if local_vgg16_weights:
                        self._vgg16_eyes = VGG16(
                            weights=local_vgg16_weights,
                            include_top=False,
                            pooling="avg",
                        )
                        print("[AI Engine] Loaded video extractor + local VGG16 weights")
                    else:
                        print(
                            "[AI Engine] Local VGG16 weights not found; vision observer disabled for this process"
                        )

                self._models_loaded = True
                print("[AI Engine] Lazy load complete")
            except Exception as e:
                # Keep serving even if model loading fails.
                print(f"[AI Engine] Model load failed: {e}")
                print("[AI Engine] Observer models disabled for this process after load failure")

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
            # Model output is a 256-dim ReLU embedding (feature extractor, not classifier).
            # np.mean(abs) collapses to ~1.66 for all inputs — not discriminative.
            # Use 90th-percentile activation as proxy: higher when more neurons fire strongly.
            embedding = features[0]  # shape (256,)
            p90 = float(np.percentile(embedding, 90))
            p50 = float(np.percentile(embedding, 50))
            nonzero = int(np.sum(embedding > 0))
            # p90 of ReLU(Dense(256)) for this model empirically ranges ~0-10.
            # Cap at 8.0 so score=1.0 only for strongly activated embeddings.
            raw_score = min(p90 / 8.0, 1.0)
            distress_score = raw_score  # already [0,1], no sigmoid needed
            print(f"[AI Engine] Audio: p90={p90:.4f} p50={p50:.4f} nonzero={nonzero}/256 score={distress_score:.4f} threshold=0.68")

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
            from keras.applications.vgg16 import preprocess_input

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
            print(f"[AI Engine] Vision: raw={raw_score:.4f} sigmoid={stimming_confidence:.4f} threshold=0.55")

            if stimming_confidence > 0.55:
                return (
                    "[Visual Observer Note] Possible repetitive movement pattern detected. "
                    "Guide caregiver to reduce sensory load and offer grounding support."
                )
            return ""
        except Exception as e:
            print(f"[AI Engine] Vision inference error: {e}")
            return ""


ai_engine = NeuroDecodeAI()
