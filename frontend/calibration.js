import { getPoseState, subscribe as subscribePose } from "./pose.js";

const CARD_WIDTH_CM = 8.56;
const SAMPLE_MAX_SIDE = 420;
const REQUIRED_VALID_FRAMES = 12;
const MAX_CALIBRATION_FRAMES = 42;
const MAX_WIDTH_SPREAD_RATIO = 0.12;

const els = {
  video: document.getElementById("cameraVideo"),
  calibrateBtn: document.getElementById("calibrateCameraBtn"),
  status: document.getElementById("calibStatus"),
  scale: document.getElementById("scaleDisplay"),
  error: document.getElementById("calibError"),
};

let pixelsPerCm = null;
let busy = false;
const listeners = [];

function notifyCalibration() {
  const state = getCalibrationState();
  for (const listener of listeners) listener(state);
}

export function subscribeCalibration(listener) {
  listeners.push(listener);
}

export function getCalibrationState() {
  return {
    calibrated: Number.isFinite(pixelsPerCm),
    pixelsPerCm,
    busy,
  };
}

export function getPixelsPerCm() {
  return pixelsPerCm;
}

export function isCalibrated() {
  return Number.isFinite(pixelsPerCm);
}

function setCalibrationVisual(stateText, scaleText, statusClass = "") {
  els.status.textContent = stateText;
  els.status.className = `calib-status ${statusClass}`.trim();
  els.scale.textContent = scaleText;
}

function resetCalibration(keepError = false) {
  pixelsPerCm = null;
  setCalibrationVisual("Not calibrated", "Scale: — px/cm");
  if (!keepError) {
    els.error.textContent = "";
  }
  notifyCalibration();
}

function wait(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function median(values) {
  if (!values.length) return NaN;
  const sorted = [...values].sort((a, b) => a - b);
  const mid = Math.floor(sorted.length / 2);
  return sorted.length % 2 ? sorted[mid] : (sorted[mid - 1] + sorted[mid]) / 2;
}

function getSampleSize(width, height) {
  const maxSide = Math.max(width, height);
  if (maxSide <= SAMPLE_MAX_SIDE) {
    return { sw: width, sh: height, scaleToSource: 1 };
  }
  const ratio = SAMPLE_MAX_SIDE / maxSide;
  return {
    sw: Math.max(1, Math.round(width * ratio)),
    sh: Math.max(1, Math.round(height * ratio)),
    scaleToSource: 1 / ratio,
  };
}

function buildMask(imageData, threshold = 64) {
  const { data, width, height } = imageData;
  const mask = new Uint8Array(width * height);
  for (let i = 0, p = 0; i < data.length; i += 4, p += 1) {
    const gray = data[i] * 0.299 + data[i + 1] * 0.587 + data[i + 2] * 0.114;
    mask[p] = gray < threshold ? 1 : 0;
  }
  return { mask, width, height };
}

function componentStats(maskObj) {
  const { mask, width, height } = maskObj;
  const visited = new Uint8Array(mask.length);
  const results = [];

  const qx = new Int32Array(mask.length);
  const qy = new Int32Array(mask.length);

  for (let y = 0; y < height; y += 1) {
    for (let x = 0; x < width; x += 1) {
      const idx = y * width + x;
      if (!mask[idx] || visited[idx]) continue;

      let head = 0;
      let tail = 0;
      qx[tail] = x;
      qy[tail] = y;
      tail += 1;
      visited[idx] = 1;

      let area = 0;
      let minX = x;
      let maxX = x;
      let minY = y;
      let maxY = y;

      while (head < tail) {
        const cx = qx[head];
        const cy = qy[head];
        head += 1;
        area += 1;

        if (cx < minX) minX = cx;
        if (cx > maxX) maxX = cx;
        if (cy < minY) minY = cy;
        if (cy > maxY) maxY = cy;

        const neighbors = [
          [cx - 1, cy],
          [cx + 1, cy],
          [cx, cy - 1],
          [cx, cy + 1],
        ];
        for (const [nx, ny] of neighbors) {
          if (nx < 0 || ny < 0 || nx >= width || ny >= height) continue;
          const nIdx = ny * width + nx;
          if (!mask[nIdx] || visited[nIdx]) continue;
          visited[nIdx] = 1;
          qx[tail] = nx;
          qy[tail] = ny;
          tail += 1;
        }
      }

      results.push({ area, minX, maxX, minY, maxY });
    }
  }

  return results;
}

function countDarkInRect(maskObj, x1, y1, x2, y2) {
  const { mask, width } = maskObj;
  const left = Math.max(0, Math.floor(x1));
  const right = Math.max(left + 1, Math.ceil(x2));
  const top = Math.max(0, Math.floor(y1));
  const bottom = Math.max(top + 1, Math.ceil(y2));
  let count = 0;
  for (let y = top; y < bottom; y += 1) {
    const row = y * width;
    for (let x = left; x < right; x += 1) {
      if (mask[row + x]) count += 1;
    }
  }
  return { count, area: (right - left) * (bottom - top) };
}

function edgeSpanAtY(maskObj, y, minX, maxX) {
  const { mask, width, height } = maskObj;
  const yy = Math.max(0, Math.min(height - 1, Math.round(y)));
  const row = yy * width;
  let first = -1;
  let last = -1;
  for (let x = minX; x <= maxX; x += 1) {
    if (!mask[row + x]) continue;
    if (first < 0) first = x;
    last = x;
  }
  if (first < 0 || last < 0) return 0;
  return last - first + 1;
}

function edgeSpanAtX(maskObj, x, minY, maxY) {
  const { mask, width, height } = maskObj;
  const xx = Math.max(0, Math.min(width - 1, Math.round(x)));
  let first = -1;
  let last = -1;
  for (let y = minY; y <= maxY; y += 1) {
    const yy = Math.max(0, Math.min(height - 1, y));
    if (!mask[yy * width + xx]) continue;
    if (first < 0) first = yy;
    last = yy;
  }
  if (first < 0 || last < 0) return 0;
  return last - first + 1;
}

function evaluateComponent(maskObj, comp) {
  const { width: frameW, height: frameH } = maskObj;
  const boxW = comp.maxX - comp.minX + 1;
  const boxH = comp.maxY - comp.minY + 1;
  const boxArea = boxW * boxH;
  if (boxW < frameW * 0.14 || boxH < frameH * 0.1) return null;
  if (boxArea < frameW * frameH * 0.025) return null;

  // Reject partial markers clipped by frame boundary.
  const edgePad = 2;
  if (
    comp.minX <= edgePad ||
    comp.minY <= edgePad ||
    comp.maxX >= frameW - edgePad - 1 ||
    comp.maxY >= frameH - edgePad - 1
  ) {
    return null;
  }

  const aspect = boxW / boxH;
  if (aspect < 1.25 || aspect > 1.95) return null;

  const fillRatio = comp.area / boxArea;
  if (fillRatio < 0.08 || fillRatio > 0.48) return null;

  const bandX = Math.max(3, Math.round(boxW * 0.12));
  const bandY = Math.max(3, Math.round(boxH * 0.12));

  const top = countDarkInRect(maskObj, comp.minX, comp.minY, comp.maxX + 1, comp.minY + bandY);
  const bottom = countDarkInRect(maskObj, comp.minX, comp.maxY - bandY + 1, comp.maxX + 1, comp.maxY + 1);
  const left = countDarkInRect(maskObj, comp.minX, comp.minY, comp.minX + bandX, comp.maxY + 1);
  const right = countDarkInRect(maskObj, comp.maxX - bandX + 1, comp.minY, comp.maxX + 1, comp.maxY + 1);

  const inner = countDarkInRect(
    maskObj,
    comp.minX + bandX,
    comp.minY + bandY,
    comp.maxX - bandX + 1,
    comp.maxY - bandY + 1,
  );

  const topDensity = top.count / Math.max(1, top.area);
  const bottomDensity = bottom.count / Math.max(1, bottom.area);
  const leftDensity = left.count / Math.max(1, left.area);
  const rightDensity = right.count / Math.max(1, right.area);
  const innerDensity = inner.count / Math.max(1, inner.area);

  if (topDensity < 0.22 || bottomDensity < 0.22 || leftDensity < 0.2 || rightDensity < 0.2) return null;
  if (innerDensity > 0.11) return null;

  const topSpan = edgeSpanAtY(maskObj, comp.minY + bandY * 0.5, comp.minX, comp.maxX);
  const bottomSpan = edgeSpanAtY(maskObj, comp.maxY - bandY * 0.5, comp.minX, comp.maxX);
  const leftSpan = edgeSpanAtX(maskObj, comp.minX + bandX * 0.5, comp.minY, comp.maxY);
  const rightSpan = edgeSpanAtX(maskObj, comp.maxX - bandX * 0.5, comp.minY, comp.maxY);
  if (!topSpan || !bottomSpan || !leftSpan || !rightSpan) return null;

  const widthSkew = Math.max(topSpan, bottomSpan) / Math.max(1, Math.min(topSpan, bottomSpan));
  const heightSkew = Math.max(leftSpan, rightSpan) / Math.max(1, Math.min(leftSpan, rightSpan));
  if (widthSkew > 1.3 || heightSkew > 1.3) return null;

  const confidence =
    Math.min(1, topDensity + bottomDensity + leftDensity + rightDensity) *
    Math.max(0.2, 1 - Math.abs(aspect - 1.585) / 0.45) *
    Math.max(0.2, 1 - innerDensity * 2.5);

  return {
    widthPx: (topSpan + bottomSpan) / 2,
    confidence,
  };
}

function detectCalibrationMarkerInImageData(imageData) {
  const maskObj = buildMask(imageData);
  const components = componentStats(maskObj);
  if (!components.length) return null;

  let best = null;
  for (const comp of components) {
    const candidate = evaluateComponent(maskObj, comp);
    if (!candidate) continue;
    if (!best || candidate.confidence > best.confidence) {
      best = candidate;
    }
  }
  return best;
}

function getVideoFrameImageData() {
  const vw = els.video.videoWidth;
  const vh = els.video.videoHeight;
  if (!vw || !vh) return null;

  const { sw, sh, scaleToSource } = getSampleSize(vw, vh);
  const offscreen = document.createElement("canvas");
  offscreen.width = sw;
  offscreen.height = sh;
  const octx = offscreen.getContext("2d", { willReadFrequently: true });
  octx.drawImage(els.video, 0, 0, sw, sh);
  const imageData = octx.getImageData(0, 0, sw, sh);
  return { imageData, scaleToSource };
}

function stableWidth(widths) {
  const med = median(widths);
  const maxDev = Math.max(...widths.map((w) => Math.abs(w - med)));
  return maxDev / Math.max(1, med) <= MAX_WIDTH_SPREAD_RATIO;
}

export async function calibrateCamera() {
  const poseState = getPoseState();
  if (!poseState.cameraRunning) {
    els.error.textContent = "Start camera first.";
    return false;
  }

  busy = true;
  els.error.textContent = "";
  setCalibrationVisual("Calibrating...", "Scale: — px/cm", "calib-status--busy");
  els.calibrateBtn.disabled = true;
  notifyCalibration();

  const widths = [];
  let checkedFrames = 0;

  while (checkedFrames < MAX_CALIBRATION_FRAMES) {
    const sample = getVideoFrameImageData();
    if (!sample) {
      await wait(80);
      checkedFrames += 1;
      continue;
    }

    const hit = detectCalibrationMarkerInImageData(sample.imageData);
    if (hit && hit.confidence >= 0.46) {
      widths.push(hit.widthPx * sample.scaleToSource);
    }

    if (widths.length >= REQUIRED_VALID_FRAMES && stableWidth(widths.slice(-REQUIRED_VALID_FRAMES))) {
      const used = widths.slice(-REQUIRED_VALID_FRAMES);
      const detectedCardWidthPx = median(used);
      pixelsPerCm = detectedCardWidthPx / CARD_WIDTH_CM;
      setCalibrationVisual("Calibration Complete", `Scale: ${pixelsPerCm.toFixed(2)} px/cm`, "calib-status--done");
      busy = false;
      notifyCalibration();
      return true;
    }

    await wait(80);
    checkedFrames += 1;
  }

  resetCalibration(true);
  els.error.textContent = "Calibration marker not detected clearly. Hold the card flat and try again.";
  busy = false;
  notifyCalibration();
  return false;
}

function onPoseUpdate(state) {
  if (!state.cameraRunning) {
    resetCalibration();
    els.calibrateBtn.disabled = true;
    return;
  }

  els.calibrateBtn.disabled = busy;
}

function init() {
  els.calibrateBtn?.addEventListener("click", calibrateCamera);
  subscribePose(onPoseUpdate);
  onPoseUpdate(getPoseState());

  // Optional synthetic-test hook for browser automation of failure/success states.
  window.__sewmetrikCalibrationTest = {
    detectFromCanvas(canvas) {
      const c = document.createElement("canvas");
      c.width = canvas.width;
      c.height = canvas.height;
      const cctx = c.getContext("2d", { willReadFrequently: true });
      cctx.drawImage(canvas, 0, 0);
      const imageData = cctx.getImageData(0, 0, c.width, c.height);
      return detectCalibrationMarkerInImageData(imageData);
    },
    stableWidth,
  };
}

init();
