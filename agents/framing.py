"""
Smart Framing Agent
Autonomous dynamic framing using MediaPipe & OpenCV face detection,
active speaker tracking, EMA-smoothed crop windows, PySceneDetect cut detection,
and 2-speaker split-screen layouts with blurred background fallback.
"""

from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
import cv2
import numpy as np

from schema import CropPlan


class SmartFramingAgent:
    """Agent responsible for intelligent 9:16 framing, face tracking, and split-screen composition."""

    def __init__(self, ema_alpha: float = 0.15, models_dir: Optional[Path] = None):
        self.ema_alpha = ema_alpha
        self.models_dir = models_dir or (Path(__file__).parent.parent / "models")
        self.mp_model_path = self.models_dir / "blaze_face_short_range.tflite"
        self.cascade_path = self.models_dir / "haarcascade_frontalface_default.xml"

    def analyze_framing(
        self,
        video_path: Path,
        start_seconds: float,
        end_seconds: float
    ) -> CropPlan:
        """
        Detects scene cuts, samples frames, tracks faces, and generates the optimal 9:16 crop plan.
        """
        duration = max(1.0, end_seconds - start_seconds)
        
        # 1. Detect scene cuts
        scene_cuts = self.detect_scene_cuts(video_path, start_seconds, end_seconds)

        # 2. Sample frames and detect faces
        face_records, width, height = self._sample_and_detect_faces(
            video_path, start_seconds, duration, sample_fps=2.0
        )

        if not face_records or width <= 0 or height <= 0:
            return self._build_blur_fallback_plan(scene_cuts)

        # Multi-speaker check: if 2 distinct faces appear in >= 35% of frames
        frames_with_two_faces = [r for r in face_records if len(r["faces"]) >= 2]
        if len(frames_with_two_faces) / max(1, len(face_records)) >= 0.35:
            return self._build_split_screen_plan(face_records, width, height, scene_cuts)

        # Single-speaker check: if at least one face appears in >= 25% of frames
        frames_with_faces = [r for r in face_records if len(r["faces"]) >= 1]
        if len(frames_with_faces) / max(1, len(face_records)) >= 0.25:
            return self._build_single_face_plan(face_records, width, height, scene_cuts)

        # Default fallback: Ambient blur layout
        return self._build_blur_fallback_plan(scene_cuts)

    def detect_scene_cuts(
        self,
        video_path: Path,
        start_seconds: float,
        end_seconds: float
    ) -> List[float]:
        """Detect scene cut transition timestamps within the clip range."""
        scene_cuts: List[float] = []
        try:
            from scenedetect import open_video, SceneManager, ContentDetector
            video = open_video(str(video_path))
            scene_manager = SceneManager()
            scene_manager.add_detector(ContentDetector(threshold=27.0))
            scene_manager.detect_scenes(video=video, end_time=end_seconds)
            scenes = scene_manager.get_scene_list()
            for s in scenes:
                t = s[0].get_seconds()
                if start_seconds < t < end_seconds:
                    scene_cuts.append(round(t - start_seconds, 2))
        except Exception as e:
            print(f"[SmartFramingAgent] Scene detection info: {e}")
        return scene_cuts

    def _sample_and_detect_faces(
        self,
        video_path: Path,
        start_seconds: float,
        duration: float,
        sample_fps: float = 2.0
    ) -> Tuple[List[Dict[str, Any]], int, int]:
        """Samples frames across the duration and runs face detection."""
        records: List[Dict[str, Any]] = []
        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            return [], 0, 0

        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0

        # 1. Initialize MediaPipe FaceDetector if model is present
        mp_detector = None
        if self.mp_model_path.exists():
            try:
                import mediapipe as mp
                from mediapipe.tasks import python
                from mediapipe.tasks.python import vision
                base_options = python.BaseOptions(model_asset_path=str(self.mp_model_path.resolve()))
                options = vision.FaceDetectorOptions(base_options=base_options)
                mp_detector = vision.FaceDetector.create_from_options(options)
            except Exception as e:
                mp_detector = None

        # 2. Fallback to OpenCV Haar Cascade if available
        cascade = None
        if not mp_detector and self.cascade_path.exists():
            try:
                c = cv2.CascadeClassifier(str(self.cascade_path.resolve()))
                if not c.empty():
                    cascade = c
            except Exception:
                cascade = None

        total_samples = max(2, int(duration * sample_fps))
        sample_interval = duration / total_samples

        scale_mult = 2.0 if min(width, height) < 480 else 1.0

        for i in range(total_samples):
            t_offset = i * sample_interval
            target_time = start_seconds + t_offset
            target_frame = int(target_time * fps)
            cap.set(cv2.CAP_PROP_POS_FRAMES, target_frame)
            ret, frame = cap.read()
            if not ret or frame is None:
                continue

            if scale_mult != 1.0:
                proc_frame = cv2.resize(frame, (0, 0), fx=scale_mult, fy=scale_mult, interpolation=cv2.INTER_LINEAR)
            else:
                proc_frame = frame

            faces = []
            if mp_detector:
                try:
                    import mediapipe as mp
                    rgb = cv2.cvtColor(proc_frame, cv2.COLOR_BGR2RGB)
                    mp_img = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
                    detection_result = mp_detector.detect(mp_img)
                    for det in detection_result.detections:
                        bbox = det.bounding_box
                        x = int(bbox.origin_x / scale_mult)
                        y = int(bbox.origin_y / scale_mult)
                        w = int(bbox.width / scale_mult)
                        h = int(bbox.height / scale_mult)
                        cx = x + w // 2
                        cy = y + h // 2
                        faces.append({"x": x, "y": y, "w": w, "h": h, "cx": cx, "cy": cy})
                except Exception:
                    pass

            if not faces and cascade and not cascade.empty():
                try:
                    gray = cv2.cvtColor(proc_frame, cv2.COLOR_BGR2GRAY)
                    min_s = int(15 * scale_mult)
                    detected = cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=3, minSize=(min_s, min_s))
                    for (x, y, w, h) in detected:
                        ox = int(x / scale_mult)
                        oy = int(y / scale_mult)
                        ow = int(w / scale_mult)
                        oh = int(h / scale_mult)
                        cx = ox + ow // 2
                        cy = oy + oh // 2
                        faces.append({"x": ox, "y": oy, "w": ow, "h": oh, "cx": cx, "cy": cy})
                except Exception:
                    pass

            faces.sort(key=lambda f: f["cx"])
            records.append({
                "time_offset": round(t_offset, 2),
                "faces": faces
            })

        cap.release()
        return records, width, height

    def _build_single_face_plan(
        self,
        records: List[Dict[str, Any]],
        width: int,
        height: int,
        scene_cuts: List[float]
    ) -> CropPlan:
        """Computes dual-mode smoothed 9:16 crop window centering on the active speaker:
        - Stationary mode (displacement < 0.15 * width): Static median crop (zero micro-jitter/head nodding noise).
        - Dynamic mode (displacement >= 0.15 * width): Deadband hysteresis (25px) with spring-damper easing,
          resetting immediately at PySceneDetect scene cut boundaries.
        """
        target_aspect = 9.0 / 16.0
        crop_h = height
        crop_w = int(crop_h * target_aspect)
        if crop_w > width:
            crop_w = width
            crop_h = int(crop_w / target_aspect)

        all_cx = [r["faces"][0]["cx"] for r in records if r.get("faces")]
        if not all_cx:
            final_cx = width / 2.0
            crop_x = int(np.clip(final_cx - (crop_w / 2.0), 0, width - crop_w))
            crop_y = int((height - crop_h) / 2.0)
            return CropPlan(
                layout="single_face",
                face_count=0,
                scene_cuts=scene_cuts,
                crop_x=crop_x,
                crop_y=crop_y,
                crop_w=crop_w,
                crop_h=crop_h,
                filter_string=f"[0:v]crop={crop_w}:{crop_h}:{crop_x}:{crop_y},scale=1080:1920[merged]"
            )

        max_displacement = max(all_cx) - min(all_cx)
        is_stationary = max_displacement < (0.15 * width)

        if is_stationary:
            # Mode A: Static median crop for stationary speakers (zero micro-jitter)
            final_cx = float(np.median(all_cx))
        else:
            # Mode B: Deadband Hysteresis (25px) + Spring-Damper easing for walking speakers
            deadband = 25.0
            tracked_cx = float(all_cx[0])
            velocity = 0.0
            last_t = 0.0
            tracked_positions = []

            for r in records:
                t = r["time_offset"]
                faces = r.get("faces", [])

                # Scene cut boundary: instantaneous filter reset
                if any(last_t <= cut <= t for cut in scene_cuts):
                    if faces:
                        tracked_cx = float(faces[0]["cx"])
                        velocity = 0.0
                elif faces:
                    raw_cx = float(faces[0]["cx"])
                    delta = raw_cx - tracked_cx
                    if abs(delta) > deadband:
                        target_cx = raw_cx - np.sign(delta) * deadband
                        velocity = 0.65 * velocity + 0.35 * (target_cx - tracked_cx)
                        tracked_cx += velocity
                    else:
                        velocity *= 0.5
                        tracked_cx += velocity

                last_t = t
                tracked_positions.append(tracked_cx)

            final_cx = float(np.mean(tracked_positions)) if tracked_positions else float(np.median(all_cx))

        crop_x = int(np.clip(final_cx - (crop_w / 2.0), 0, width - crop_w))
        crop_y = int((height - crop_h) / 2.0)
        filter_str = f"[0:v]crop={crop_w}:{crop_h}:{crop_x}:{crop_y},scale=1080:1920[merged]"

        return CropPlan(
            layout="single_face",
            face_count=1,
            scene_cuts=scene_cuts,
            crop_x=crop_x,
            crop_y=crop_y,
            crop_w=crop_w,
            crop_h=crop_h,
            filter_string=filter_str
        )

    def _build_split_screen_plan(
        self,
        records: List[Dict[str, Any]],
        width: int,
        height: int,
        scene_cuts: List[float]
    ) -> CropPlan:
        """Builds a stacked 2-speaker split-screen layout (Top 1080x960, Bottom 1080x960) with 4px divider."""
        speaker_a_cx = []
        speaker_b_cx = []

        for r in records:
            faces = r["faces"]
            if len(faces) >= 2:
                speaker_a_cx.append(faces[0]["cx"])
                speaker_b_cx.append(faces[-1]["cx"])

        med_a = float(np.median(speaker_a_cx)) if speaker_a_cx else (width * 0.25)
        med_b = float(np.median(speaker_b_cx)) if speaker_b_cx else (width * 0.75)

        sub_aspect = 9.0 / 8.0
        sub_h = height
        sub_w = int(sub_h * sub_aspect)
        if sub_w > width:
            sub_w = int(width * 0.5)
            sub_h = int(sub_w / sub_aspect)

        crop_a_x = int(np.clip(med_a - (sub_w / 2.0), 0, width - sub_w))
        crop_b_x = int(np.clip(med_b - (sub_w / 2.0), 0, width - sub_w))
        crop_y = int((height - sub_h) / 2.0)

        filter_str = (
            f"[0:v]crop={sub_w}:{sub_h}:{crop_a_x}:{crop_y},scale=1080:960[top];"
            f"[0:v]crop={sub_w}:{sub_h}:{crop_b_x}:{crop_y},scale=1080:960[bottom];"
            f"[top][bottom]vstack[stacked];"
            f"[stacked]drawbox=y=958:h=4:color=black@0.5:t=fill[merged]"
        )

        return CropPlan(
            layout="split_screen",
            face_count=2,
            scene_cuts=scene_cuts,
            crop_w=sub_w,
            crop_h=sub_h,
            split_top_x=crop_a_x,
            split_bottom_x=crop_b_x,
            filter_string=filter_str
        )

    def _build_blur_fallback_plan(self, scene_cuts: List[float]) -> CropPlan:
        """Builds ambient Gaussian blur background with centered foreground overlay."""
        filter_str = (
            "[0:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,boxblur=25:5[bg];"
            "[0:v]scale=1080:-2[fg];"
            "[bg][fg]overlay=(W-w)/2:(H-h)/2[merged]"
        )
        return CropPlan(
            layout="blur_fallback",
            face_count=0,
            scene_cuts=scene_cuts,
            filter_string=filter_str
        )
