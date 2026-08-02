import { getPoseState, subscribe } from "./pose.js";
import { getCalibrationState, isCalibrated, subscribeCalibration } from "./calibration.js";

const LANDMARKS = {
  NOSE: 0,
  LEFT_SHOULDER: 11,
  RIGHT_SHOULDER: 12,
  LEFT_ELBOW: 13,
  RIGHT_ELBOW: 14,
  LEFT_HIP: 23,
  RIGHT_HIP: 24,
};

const VISIBILITY_THRESHOLD = 0.5;
const SHOULDER_THRESHOLD = 0.55;
const HIP_THRESHOLD = 0.5;
const ELBOW_THRESHOLD = 0.45;
const CENTER_TOLERANCE = 0.14;
const UPPER_BODY_MIN_RATIO = 0.42;
const UPPER_BODY_MAX_RATIO = 0.9;

let holdFrames = 0;
let lastEstimate = null;

const els = {
  captureBtn: document.getElementById("captureMeasurementsBtn"),
  applyBtn: document.getElementById("applyEstimatesBtn"),
  retakeBtn: document.getElementById("retakeScanBtn"),
  calibStatus: document.getElementById("calibStatus"),
  calibScale: document.getElementById("scaleDisplay"),
  scanStatus: document.getElementById("scanMessage"),
  calibError: document.getElementById("calibError"),
  estimateCard: document.getElementById("estimateCard"),
  estimateGrid: document.getElementById("estimateGrid"),
  readiness: {
    head: document.getElementById("readyHead"),
    shoulders: document.getElementById("readyShoulders"),
    arms: document.getElementById("readyArms"),
    waistHips: document.getElementById("readyWaistHips"),
    centered: document.getElementById("readyCentered"),
  },
};

function setReadinessTick(el, ok) {
  if (!el) return;
  el.textContent = ok ? "✓" : "✗";
  el.classList.toggle("ok", ok);
}

function getLandmark(landmarks, idx) {
  return landmarks?.[idx] ?? null;
}

function visible(lm, threshold = VISIBILITY_THRESHOLD) {
  return !!lm && (lm.visibility ?? 0) >= threshold;
}

function pxDist(a, b, width, height) {
  const dx = (a.x - b.x) * width;
  const dy = (a.y - b.y) * height;
  return Math.hypot(dx, dy);
}

function midpoint(a, b) {
  return {
    x: (a.x + b.x) / 2,
    y: (a.y + b.y) / 2,
    visibility: Math.min(a.visibility ?? 1, b.visibility ?? 1),
  };
}

function estimateMeasurementsFromLandmarks(landmarks, width, height, pxPerCm) {
  const lShoulder = getLandmark(landmarks, LANDMARKS.LEFT_SHOULDER);
  const rShoulder = getLandmark(landmarks, LANDMARKS.RIGHT_SHOULDER);
  const lElbow = getLandmark(landmarks, LANDMARKS.LEFT_ELBOW);
  const rElbow = getLandmark(landmarks, LANDMARKS.RIGHT_ELBOW);
  const lHip = getLandmark(landmarks, LANDMARKS.LEFT_HIP);
  const rHip = getLandmark(landmarks, LANDMARKS.RIGHT_HIP);

  const shoulderPx = pxDist(lShoulder, rShoulder, width, height);
  const hipPx = pxDist(lHip, rHip, width, height);
  const shoulderMid = midpoint(lShoulder, rShoulder);
  const hipMid = midpoint(lHip, rHip);
  const torsoPx = pxDist(shoulderMid, hipMid, width, height);

  const leftUpperArmPx = pxDist(lShoulder, lElbow, width, height);
  const rightUpperArmPx = pxDist(rShoulder, rElbow, width, height);
  const upperArmPx = (leftUpperArmPx + rightUpperArmPx) / 2;

  const shoulderCm = shoulderPx / pxPerCm;
  const upperArmCircCm = (upperArmPx / pxPerCm) * 0.95;
  const bustCm = shoulderCm * 2.6 + hipPx / pxPerCm * 0.55;
  const waistCm = bustCm * 0.83;
  const blouseLengthCm = torsoPx / pxPerCm * 1.12;
  const armholeDepthCm = shoulderCm * 0.58;
  const sleeveLengthCm = shoulderCm * 0.62 + upperArmCircCm * 0.2;

  return {
    bust: bustCm,
    waist: waistCm,
    shoulderWidth: shoulderCm,
    blouseLength: blouseLengthCm,
    armholeDepth: armholeDepthCm,
    sleeveLength: sleeveLengthCm,
    upperArmCircumference: upperArmCircCm,
    pxPerCm,
  };
}

function validateValues(values) {
  const ranges = {
    bust: [60, 150],
    waist: [50, 130],
    shoulderWidth: [28, 55],
    blouseLength: [28, 55],
    armholeDepth: [12, 30],
    sleeveLength: [10, 50],
    upperArmCircumference: [18, 55],
  };

  return Object.entries(ranges).every(([k, [min, max]]) => {
    const v = values[k];
    return Number.isFinite(v) && v >= min && v <= max;
  });
}

function evaluateReadiness(state) {
  const lm = state.landmarks;
  if (!state.cameraRunning || !state.detected || !lm) {
    return {
      head: false,
      shoulders: false,
      arms: false,
      waistHips: false,
      centered: false,
      upperBodyVisible: false,
      upperBodyTooSmall: true,
      ready: false,
    };
  }

  const nose = getLandmark(lm, LANDMARKS.NOSE);
  const ls = getLandmark(lm, LANDMARKS.LEFT_SHOULDER);
  const rs = getLandmark(lm, LANDMARKS.RIGHT_SHOULDER);
  const le = getLandmark(lm, LANDMARKS.LEFT_ELBOW);
  const re = getLandmark(lm, LANDMARKS.RIGHT_ELBOW);
  const lh = getLandmark(lm, LANDMARKS.LEFT_HIP);
  const rh = getLandmark(lm, LANDMARKS.RIGHT_HIP);

  const head = visible(nose, VISIBILITY_THRESHOLD);
  const shoulders = visible(ls, SHOULDER_THRESHOLD) && visible(rs, SHOULDER_THRESHOLD);
  const arms = visible(le, ELBOW_THRESHOLD) && visible(re, ELBOW_THRESHOLD);
  const waistHips = visible(lh, HIP_THRESHOLD) && visible(rh, HIP_THRESHOLD);

  const shoulderMid = shoulders ? midpoint(ls, rs) : null;
  const hipMid = waistHips ? midpoint(lh, rh) : null;

  let centered = false;
  let upperBodyVisible = false;
  let upperBodyTooSmall = true;

  if (head && shoulderMid && hipMid && state.height > 0) {
    const topY = Math.min(nose.y, ls.y, rs.y);
    const bottomY = Math.max(lh.y, rh.y);
    const upperBodyRatio = (bottomY - topY) * state.height / state.height;
    upperBodyVisible = upperBodyRatio >= UPPER_BODY_MIN_RATIO && upperBodyRatio <= UPPER_BODY_MAX_RATIO;
    upperBodyTooSmall = upperBodyRatio < UPPER_BODY_MIN_RATIO;

    const centerX = (shoulderMid.x + hipMid.x) / 2;
    centered = Math.abs(centerX - 0.5) <= CENTER_TOLERANCE;
  }

  const ready = head && shoulders && arms && waistHips && centered && upperBodyVisible && !upperBodyTooSmall;

  return {
    head,
    shoulders,
    arms,
    waistHips,
    centered,
    upperBodyVisible,
    upperBodyTooSmall,
    ready,
  };
}

function guidanceMessage(state, readiness) {
  if (!state.detected) return ["Move back — keep your complete upper body visible", "guide"];
  if (!readiness.shoulders) return ["Keep both shoulders visible", "guide"];
  if (!readiness.arms) return ["Keep your arms slightly away from your torso", "guide"];
  if (!readiness.waistHips) return ["Keep your waist and hips visible", "guide"];
  if (!readiness.head || !readiness.upperBodyVisible) {
    return ["Move back — keep your complete upper body visible", "guide"];
  }
  if (readiness.upperBodyTooSmall) return ["Move back — keep your complete upper body visible", "guide"];
  if (!readiness.centered) return ["Center your upper body", "guide"];
  if (holdFrames < 12) return ["Hold position...", "guide"];
  return ["Ready to scan", "found"];
}

function updateReadinessUI(state) {
  const readiness = evaluateReadiness(state);

  setReadinessTick(els.readiness.head, readiness.head);
  setReadinessTick(els.readiness.shoulders, readiness.shoulders);
  setReadinessTick(els.readiness.arms, readiness.arms);
  setReadinessTick(els.readiness.waistHips, readiness.waistHips);
  setReadinessTick(els.readiness.centered, readiness.centered);

  if (readiness.ready) {
    holdFrames += 1;
  } else {
    holdFrames = 0;
  }

  const [text, cls] = guidanceMessage(state, readiness);
  els.scanStatus.textContent = text;
  els.scanStatus.className = `scan-status ${cls}`;

  const calibration = getCalibrationState();
  if (!calibration.busy) {
    els.calibStatus.textContent = calibration.calibrated ? "Calibration Complete" : "Not calibrated";
    els.calibStatus.classList.toggle("ok", !!calibration.calibrated);
    els.calibScale.textContent = calibration.calibrated
      ? `Scale: ${calibration.pixelsPerCm.toFixed(2)} px/cm`
      : "Scale: — px/cm";
  }

  const readyToCapture = state.cameraRunning && state.detected && holdFrames >= 12 && isCalibrated();
  els.captureBtn.disabled = !readyToCapture;
}

function round1(v) {
  return Math.round(v * 10) / 10;
}

function writeEstimateCard(est) {
  const rows = [
    ["Bust", round1(est.bust)],
    ["Waist", round1(est.waist)],
    ["Shoulder Width", round1(est.shoulderWidth)],
    ["Blouse Length", round1(est.blouseLength)],
    ["Armhole Depth", round1(est.armholeDepth)],
    ["Sleeve Length", round1(est.sleeveLength)],
    ["Upper Arm Circumference", round1(est.upperArmCircumference)],
  ];
  els.estimateGrid.innerHTML = rows
    .map(
      ([label, value]) =>
        `<div class="dim-item"><span>${label}</span><strong>${value.toFixed(1)} cm</strong></div>`,
    )
    .join("");
}

function applyEstimatesToForm(est) {
  const map = {
    bust: "bust",
    waist: "waist",
    shoulderWidth: "shoulder_width",
    blouseLength: "blouse_length",
    armholeDepth: "armhole_depth",
    sleeveLength: "sleeve_length",
    upperArmCircumference: "upper_arm_circumference",
  };

  Object.entries(map).forEach(([key, name]) => {
    const el = document.querySelector(`input[name="${name}"]`);
    if (el && Number.isFinite(est[key])) {
      el.value = round1(est[key]).toFixed(2);
    }
  });
}

function clearEstimateCard() {
  lastEstimate = null;
  els.estimateCard.hidden = true;
  els.applyBtn.disabled = true;
}

async function captureMeasurements() {
  els.calibError.textContent = "";

  const calibration = getCalibrationState();
  if (!calibration.calibrated || !Number.isFinite(calibration.pixelsPerCm)) {
    els.calibError.textContent = "Calibrate camera before capturing measurements.";
    return;
  }

  const sampleDurationMs = 2000;
  const sampleIntervalMs = 120;
  const started = performance.now();
  const samples = [];

  els.captureBtn.disabled = true;
  els.captureBtn.textContent = "Capturing...";

  while (performance.now() - started < sampleDurationMs) {
    const state = getPoseState();
    const readiness = evaluateReadiness(state);

    if (state.detected && readiness.ready && state.landmarks) {
      try {
        const estimate = estimateMeasurementsFromLandmarks(
          state.landmarks,
          state.width,
          state.height,
          calibration.pixelsPerCm,
        );
        if (validateValues(estimate)) {
          samples.push(estimate);
        }
      } catch {
        // Ignore bad sample frame.
      }
    }

    await new Promise((resolve) => setTimeout(resolve, sampleIntervalMs));
  }

  els.captureBtn.textContent = "Capture Measurements";

  if (samples.length < 4) {
    els.calibError.textContent = "Move back — keep your complete upper body visible.";
    return;
  }

  const avg = samples.reduce(
    (acc, s) => {
      Object.keys(acc).forEach((k) => {
        acc[k] += s[k];
      });
      return acc;
    },
    {
      bust: 0,
      waist: 0,
      shoulderWidth: 0,
      blouseLength: 0,
      armholeDepth: 0,
      sleeveLength: 0,
      upperArmCircumference: 0,
      pxPerCm: 0,
    },
  );

  Object.keys(avg).forEach((k) => {
    avg[k] /= samples.length;
  });

  if (!validateValues(avg)) {
    els.calibError.textContent = "Estimation out of range. Retake with better framing and lighting.";
    return;
  }

  lastEstimate = avg;
  writeEstimateCard(avg);
  els.estimateCard.hidden = false;
  els.applyBtn.disabled = false;

  els.calibStatus.textContent = "Calibrated";
  els.calibStatus.classList.add("ok");
  els.calibScale.textContent = `Scale: ${avg.pxPerCm.toFixed(2)} px/cm`;

  els.scanStatus.textContent = "Scan complete";
  els.scanStatus.className = "scan-status found";
}

function initButtons() {
  els.captureBtn?.addEventListener("click", captureMeasurements);

  els.applyBtn?.addEventListener("click", () => {
    if (!lastEstimate) return;
    applyEstimatesToForm(lastEstimate);
    els.scanStatus.textContent = "Measurements applied to form";
    els.scanStatus.className = "scan-status found";
  });

  els.retakeBtn?.addEventListener("click", () => {
    clearEstimateCard();
    holdFrames = 0;
    els.scanStatus.textContent = "Retake ready. Reframe and capture again.";
    els.scanStatus.className = "scan-status guide";
    els.calibError.textContent = "";
  });
}

function init() {
  initButtons();
  clearEstimateCard();

  subscribe((state) => {
    updateReadinessUI(state);
  });

  subscribeCalibration(() => {
    updateReadinessUI(getPoseState());
  });

  updateReadinessUI(getPoseState());
}

init();
