// SewMetrik CV module — client-side webcam + MediaPipe Pose landmark overlay.
// This step only visualizes pose landmarks; it does not modify measurements.

import {
  FilesetResolver,
  PoseLandmarker,
  DrawingUtils,
} from "https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.14";

const MODEL_URL =
  "https://storage.googleapis.com/mediapipe-models/pose_landmarker/" +
  "pose_landmarker_lite/float16/1/pose_landmarker_lite.task";
const WASM_URL =
  "https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.14/wasm";

// Major landmarks to highlight (BlazePose indices).
const HIGHLIGHT = {
  LEFT_SHOULDER: 11,
  RIGHT_SHOULDER: 12,
  LEFT_HIP: 23,
  RIGHT_HIP: 24,
};

const els = {
  startBtn: document.getElementById("startCameraBtn"),
  stopBtn: document.getElementById("stopCameraBtn"),
  video: document.getElementById("cameraVideo"),
  canvas: document.getElementById("poseOverlay"),
  status: document.getElementById("detectionStatus"),
};

const ctx = els.canvas.getContext("2d");

let poseLandmarker = null;
let drawingUtils = null;
let stream = null;
let running = false;
let rafId = null;
let lastVideoTime = -1;

// Shared state for the measurements module (read-only from outside).
let detected = false;
let latestLandmarks = null;
const stateListeners = [];

export function getPoseState() {
  return {
    cameraRunning: running,
    detected,
    landmarks: latestLandmarks,
    width: els.canvas.width,
    height: els.canvas.height,
  };
}

export function subscribe(listener) {
  stateListeners.push(listener);
}

function notifyState() {
  const state = getPoseState();
  for (const listener of stateListeners) listener(state);
}

export function setDetectionStatus(text, kind = "none") {
  els.status.textContent = text;
  els.status.className = `detection-status detection-status--${kind}`;
}

// --- Status helpers ---------------------------------------------------------

function setDetection(found) {
  setDetectionStatus(found ? "Body detected" : "No person detected", found ? "found" : "none");
}

function setMessage(text) {
  setDetectionStatus(text, "none");
}

// --- Model setup ------------------------------------------------------------

async function ensureLandmarker() {
  if (poseLandmarker) return;
  setMessage("Loading pose model…");
  const vision = await FilesetResolver.forVisionTasks(WASM_URL);
  poseLandmarker = await PoseLandmarker.createFromOptions(vision, {
    baseOptions: { modelAssetPath: MODEL_URL, delegate: "GPU" },
    runningMode: "VIDEO",
    numPoses: 1,
  });
  drawingUtils = new DrawingUtils(ctx);
}

// --- Drawing ----------------------------------------------------------------

function drawPositionGuide() {
  const w = els.canvas.width;
  const h = els.canvas.height;
  if (!w || !h) return;

  const cx = w * 0.5;

  // Head-to-hips frame occupies about 70% of camera height.
  const frameHeight = h * 0.7;
  const frameTop = (h - frameHeight) * 0.5;
  const frameBottom = frameTop + frameHeight;

  const headCenterY = frameTop + frameHeight * 0.1;
  const shouldersY = frameTop + frameHeight * 0.24;
  const waistY = frameTop + frameHeight * 0.62;
  const hipsY = frameTop + frameHeight * 0.84;

  const shoulderHalf = Math.min(w * 0.23, frameHeight * 0.22);
  const torsoHalf = Math.min(w * 0.18, frameHeight * 0.16);
  const waistHalf = Math.min(w * 0.15, frameHeight * 0.14);
  const hipHalf = Math.min(w * 0.19, frameHeight * 0.17);
  const armOffset = Math.min(w * 0.09, frameHeight * 0.1);
  const armDrop = frameHeight * 0.3;
  const headRadius = Math.min(w, h) * 0.055;
  const labelY = Math.max(20, frameTop - 12);
  const hipLabelY = Math.min(h - 12, frameBottom + 18);

  ctx.save();
  ctx.strokeStyle = "rgba(233, 221, 201, 0.56)";
  ctx.lineWidth = 2.5;
  ctx.setLineDash([10, 8]);

  // Outer torso silhouette from shoulders to hips.
  ctx.beginPath();
  ctx.moveTo(cx - shoulderHalf, shouldersY);
  ctx.lineTo(cx - torsoHalf, waistY - frameHeight * 0.14);
  ctx.lineTo(cx - waistHalf, waistY);
  ctx.lineTo(cx - hipHalf, hipsY);
  ctx.lineTo(cx + hipHalf, hipsY);
  ctx.lineTo(cx + waistHalf, waistY);
  ctx.lineTo(cx + torsoHalf, waistY - frameHeight * 0.14);
  ctx.lineTo(cx + shoulderHalf, shouldersY);
  ctx.stroke();

  // Head marker.
  ctx.beginPath();
  ctx.arc(cx, headCenterY, headRadius, 0, Math.PI * 2);
  ctx.stroke();

  // Shoulder line.
  ctx.beginPath();
  ctx.moveTo(cx - shoulderHalf, shouldersY);
  ctx.lineTo(cx + shoulderHalf, shouldersY);
  ctx.stroke();

  // Arm area guides (left/right).
  ctx.beginPath();
  ctx.moveTo(cx - shoulderHalf - armOffset * 0.45, shouldersY + 6);
  ctx.lineTo(cx - shoulderHalf - armOffset, shouldersY + armDrop);
  ctx.moveTo(cx + shoulderHalf + armOffset * 0.45, shouldersY + 6);
  ctx.lineTo(cx + shoulderHalf + armOffset, shouldersY + armDrop);
  ctx.stroke();

  // Waist and hip lines.
  ctx.beginPath();
  ctx.moveTo(cx - waistHalf, waistY);
  ctx.lineTo(cx + waistHalf, waistY);
  ctx.moveTo(cx - hipHalf, hipsY);
  ctx.lineTo(cx + hipHalf, hipsY);
  ctx.stroke();

  // Subtle framing labels.
  ctx.setLineDash([]);
  ctx.fillStyle = "rgba(233, 221, 201, 0.82)";
  ctx.font = `500 ${Math.max(12, Math.round(h * 0.023))}px sans-serif`;
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  ctx.fillText("Align your upper body inside the guide", cx, labelY);
  ctx.fillText("Keep hips visible", cx, hipLabelY);

  ctx.restore();
}

function drawHighlights(landmarks) {
  ctx.save();
  ctx.lineWidth = 2;
  ctx.strokeStyle = "#ffffff";
  ctx.fillStyle = "rgba(176, 64, 47, 0.9)";
  for (const index of Object.values(HIGHLIGHT)) {
    const lm = landmarks[index];
    if (!lm) continue;
    const x = lm.x * els.canvas.width;
    const y = lm.y * els.canvas.height;
    ctx.beginPath();
    ctx.arc(x, y, 8, 0, Math.PI * 2);
    ctx.fill();
    ctx.stroke();
  }
  ctx.restore();
}

function renderResult(result) {
  ctx.clearRect(0, 0, els.canvas.width, els.canvas.height);
  drawPositionGuide();

  const poses = result.landmarks;
  if (!poses || poses.length === 0) {
    latestLandmarks = null;
    if (detected) {
      detected = false;
    }
    notifyState();
    return;
  }

  latestLandmarks = poses[0];
  if (!detected) {
    detected = true;
  }

  for (const landmarks of poses) {
    drawingUtils.drawConnectors(landmarks, PoseLandmarker.POSE_CONNECTIONS, {
      color: "#e9ddc9",
      lineWidth: 3,
    });
    drawingUtils.drawLandmarks(landmarks, { color: "#8fb9ff", radius: 3 });
    drawHighlights(landmarks);
  }

  // Per-frame notify so readiness UI can update live.
  notifyState();
}

// --- Detection loop ---------------------------------------------------------

function loop() {
  if (!running) return;
  if (els.video.readyState >= 2) {
    if (els.canvas.width !== els.video.videoWidth) {
      els.canvas.width = els.video.videoWidth;
      els.canvas.height = els.video.videoHeight;
      notifyState();
    }
    if (els.video.currentTime !== lastVideoTime) {
      lastVideoTime = els.video.currentTime;
      const result = poseLandmarker.detectForVideo(els.video, performance.now());
      renderResult(result);
    }
  }
  rafId = requestAnimationFrame(loop);
}

// --- Camera control ---------------------------------------------------------

async function startCamera() {
  els.startBtn.disabled = true;
  try {
    await ensureLandmarker();
    stream = await navigator.mediaDevices.getUserMedia({
      video: {
        facingMode: "user",
        width: { ideal: 720 },
        height: { ideal: 960 },
      },
      audio: false,
    });
    els.video.srcObject = stream;
    await els.video.play();

    running = true;
    els.stopBtn.disabled = false;
    setDetection(false);
    notifyState();
    loop();
  } catch (err) {
    els.startBtn.disabled = false;
    setMessage(`Camera error: ${err.message || err.name}`);
    notifyState();
  }
}

function stopCamera() {
  running = false;
  if (rafId) {
    cancelAnimationFrame(rafId);
    rafId = null;
  }
  if (stream) {
    stream.getTracks().forEach((track) => track.stop());
    stream = null;
  }
  els.video.srcObject = null;
  lastVideoTime = -1;
  ctx.clearRect(0, 0, els.canvas.width, els.canvas.height);
  detected = false;
  latestLandmarks = null;
  setDetection(false);
  els.startBtn.disabled = false;
  els.stopBtn.disabled = true;
  notifyState();
}

els.startBtn.addEventListener("click", startCamera);
els.stopBtn.addEventListener("click", stopCamera);
