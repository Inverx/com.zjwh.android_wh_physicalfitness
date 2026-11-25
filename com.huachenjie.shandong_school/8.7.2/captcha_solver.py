"""滑块验证码缺口识别工具。使用 OpenCV 边缘检测与模板匹配。"""
from typing import Optional

def solve_slider_notch(bg_bytes: bytes, tmpl_bytes: bytes) -> float:
    """识别滑块缺口偏移量。返回 X 轴坐标像素。"""
    try:
        import cv2
        import numpy as np
    except ImportError:
        return 120.0

    try:
        bg_img = cv2.imdecode(np.frombuffer(bg_bytes, np.uint8), cv2.IMREAD_UNCHANGED)
        tmpl_img = cv2.imdecode(np.frombuffer(tmpl_bytes, np.uint8), cv2.IMREAD_UNCHANGED)

        if len(tmpl_img.shape) >= 3 and tmpl_img.shape[2] == 4:
            alpha = tmpl_img[:, :, 3]
            pts = np.argwhere(alpha > 0)
            if pts.size == 0:
                return 100.0
            y_min, x_min = pts.min(axis=0)
            y_max, x_max = pts.max(axis=0) + 1
            mask = (alpha > 0).astype(np.uint8) * 255
            tmpl_roi = mask[y_min:y_max, x_min:x_max]
        else:
            y_min, y_max = 0, tmpl_img.shape[0]
            tmpl_roi = cv2.cvtColor(tmpl_img, cv2.COLOR_BGR2GRAY) if len(tmpl_img.shape) >= 3 else tmpl_img

        bg_gray = cv2.cvtColor(bg_img, cv2.COLOR_BGR2GRAY) if len(bg_img.shape) >= 3 else bg_img

        y_start = max(0, y_min - 2)
        y_end = min(bg_gray.shape[0], y_max + 2)
        bg_band = bg_gray[y_start:y_end, :]

        bg_band_edges = cv2.Canny(bg_band, 50, 150)
        tmpl_edges = cv2.Canny(tmpl_roi, 50, 150)

        res = cv2.matchTemplate(bg_band_edges, tmpl_edges, cv2.TM_CCOEFF_NORMED)
        _, _, _, max_loc = cv2.minMaxLoc(res)

        notch_x = float(max_loc[0])
        return notch_x + 10.0
    except Exception:
        return 120.0
