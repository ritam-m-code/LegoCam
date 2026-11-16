"""Find the silhouette rectangle in a full-resolution image."""

import cv2
import numpy as np


def outline(image, roi):
    x, y, w, h = roi
    if min(w, h) < 5 or min(x, y) < 0 or x + w > image.shape[1] or y + h > image.shape[0]:
        raise ValueError("Select a rectangle around the whole part, with bright margins")
    gray = cv2.cvtColor(image[y : y + h, x : x + w], cv2.COLOR_BGR2GRAY)
    gray = cv2.GaussianBlur(gray, (5, 5), 0)
    _, mask = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    contours = sorted(contours, key=cv2.contourArea, reverse=True)
    if not contours or cv2.contourArea(contours[0]) < 25:
        raise ValueError("No usable dark part found")
    if len(contours) > 1 and cv2.contourArea(contours[1]) > 0.1 * cv2.contourArea(contours[0]):
        raise ValueError("Multiple parts found; tighten selection or join the assembly")
    contour = contours[0]
    bx, by, bw, bh = cv2.boundingRect(contour)
    if bx <= 1 or by <= 1 or bx + bw >= w - 1 or by + bh >= h - 1:
        raise ValueError("Part touches selection boundary; leave bright margins")
    contour = contour + np.array([[[x, y]]])
    rect = cv2.minAreaRect(contour)
    length, width = sorted(rect[1], reverse=True)
    if width <= 0:
        raise ValueError("Degenerate part outline")
    return float(length), float(width), cv2.boxPoints(rect).astype(np.int32)


def select(image):
    scale = min(1, 1200 / image.shape[1], 800 / image.shape[0])
    preview = cv2.resize(image, None, fx=scale, fy=scale)
    print("Drag around ONE whole part with bright margins. Enter confirms; C cancels.", flush=True)
    try:
        roi = cv2.selectROI("Select part - Enter confirms", preview, fromCenter=False)
    finally:
        cv2.destroyWindow("Select part - Enter confirms")
    if not roi[2] or not roi[3]:
        raise ValueError("Selection cancelled")
    sx, sy = image.shape[1] / preview.shape[1], image.shape[0] / preview.shape[0]
    return [round(roi[0] * sx), round(roi[1] * sy), round(roi[2] * sx), round(roi[3] * sy)]


def detect(image, roi):
    length, width, box = outline(image, roi)
    # Recover floating-point rectangle edges; integer overlay corners are for display only.
    x, y, w, h = roi
    gray = cv2.cvtColor(image[y : y + h, x : x + w], cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    _, mask = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    contour = max(contours, key=cv2.contourArea)
    rect = cv2.minAreaRect(contour)
    corners = cv2.boxPoints(rect)
    edges = [corners[1] - corners[0], corners[2] - corners[1]]
    edges.sort(key=lambda edge: float(np.linalg.norm(edge)), reverse=True)
    dark = gray[mask > 0]
    bright = gray[mask == 0]
    contrast = float(np.median(bright) - np.median(dark)) if bright.size and dark.size else 0
    if contrast < 20:
        raise ValueError("Insufficient silhouette contrast")
    return {
        "length_px": length,
        "width_px": width,
        "vectors": [edge.astype(float).tolist() for edge in edges],
        "centre_px": [float(rect[0][0] + x), float(rect[0][1] + y)],
        "box": box.tolist(),
        "contrast_dn": contrast,
        "background_clipped_fraction": float(np.mean(bright >= 254)),
        "image_size": [image.shape[1], image.shape[0]],
    }
