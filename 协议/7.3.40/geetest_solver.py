import asyncio
from dataclasses import dataclass
import functools
import http.server
import io
import json
import logging
import os
import random
import socketserver
import tempfile
import threading
import time
from typing import Optional, Dict, Any, Tuple

import cv2
import numpy as np
from PIL import Image
from playwright.async_api import async_playwright
import requests

logger = logging.getLogger("geetest_solver")


class QuietHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, format, *args):
        pass


# Default GeeTest Captcha IDs for 运动世界校园 App (v7.3.90)
GEETEST_IDS = {
    "DEFAULT": "3b02ad39bd099fd3a8336d9347a189ab",
    "LOGIN": "3b02ad39bd099fd3a8336d9347a189ab",
    "REGISTER": "d30b3493dd08ff6aedc850648e7e0466",
}

HTML_TEMPLATE = """<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>GeeTest v4 Bridge</title>
    <script src="https://static.geetest.com/v4/gt4.js"></script>
    <style>
        body { margin: 0; padding: 20px; background: #fff; }
    </style>
</head>
<body>
    <div id="captcha-container"></div>
    <script>
        window.gt4Result = null;
        window.gt4Error = null;
        window.gt4Ready = false;
        
        function initCaptcha(captchaId) {
            initGeetest4({
                captchaId: captchaId,
                product: 'bind',
                language: 'zh'
            }, function (captcha) {
                window.captchaObj = captcha;
                captcha.onReady(function(){
                    window.gt4Ready = true;
                    console.log("GEETEST_READY");
                }).onSuccess(function(){
                    var result = captcha.getValidate();
                    window.gt4Result = result;
                    console.log("GEETEST_RESULT:" + JSON.stringify(result));
                }).onError(function(e){
                    window.gt4Error = e;
                    console.log("GEETEST_ERROR:" + JSON.stringify(e));
                });
            });
        }
    </script>
</body>
</html>
"""

@dataclass
class GeeTestResult:
    captcha_id: str
    lot_number: str
    pass_token: str
    gen_time: str
    captcha_output: str

    def to_dict(self) -> Dict[str, str]:
        return {
            "captcha_id": self.captcha_id,
            "lot_number": self.lot_number,
            "pass_token": self.pass_token,
            "gen_time": self.gen_time,
            "captcha_output": self.captcha_output,
        }

    def to_app_validate_payload(self, username: str = "", uuid_str: str = "") -> Dict[str, Any]:
        """Format as payload for POST /api/v70270/security/geevalidate"""
        return {
            "lotNumber": self.lot_number,
            "captchaOutput": self.captcha_output,
            "passToken": self.pass_token,
            "genTime": self.gen_time,
            "isOffline": False,
            "osType": 0,
            "businessType": 0,
            "uuid": uuid_str,
            "username": username,
        }


class GeeTestV4Solver:
    """Automated solver for GeeTest v4 sliding captcha."""

    def __init__(self, temp_dir: Optional[str] = None):
        if temp_dir is None:
            temp_dir = tempfile.gettempdir()
        self.temp_dir = os.path.abspath(temp_dir)
        self.html_file = os.path.join(self.temp_dir, "gt4_bridge.html")
        self._ensure_html()

    def _ensure_html(self):
        with open(self.html_file, "w", encoding="utf-8") as f:
            f.write(HTML_TEMPLATE)

    @staticmethod
    def find_slider_gap(slice_bytes: bytes, bg_bytes: bytes) -> Tuple[int, int, float]:
        """Locate exact cutout position using OpenCV Canny edge template matching with alpha mask."""
        bg_arr = np.frombuffer(bg_bytes, np.uint8)
        slice_arr = np.frombuffer(slice_bytes, np.uint8)

        bg = cv2.imdecode(bg_arr, cv2.IMREAD_COLOR)
        slice_img = cv2.imdecode(slice_arr, cv2.IMREAD_UNCHANGED)

        slice_alpha = slice_img[:, :, 3]
        slice_bgr = slice_img[:, :, :3]

        rows = np.where(np.any(slice_alpha > 50, axis=1))[0]
        cols = np.where(np.any(slice_alpha > 50, axis=0))[0]
        ymin, ymax = rows[0], rows[-1]
        xmin, xmax = cols[0], cols[-1]

        crop_slice_gray = cv2.cvtColor(slice_bgr[ymin:ymax+1, xmin:xmax+1], cv2.COLOR_BGR2GRAY)
        bg_gray = cv2.cvtColor(bg, cv2.COLOR_BGR2GRAY)

        bg_edge = cv2.Canny(bg_gray, 100, 200)
        slice_edge = cv2.Canny(crop_slice_gray, 100, 200)

        res = cv2.matchTemplate(bg_edge, slice_edge, cv2.TM_CCORR_NORMED)
        _, max_val, _, max_loc = cv2.minMaxLoc(res)

        distance = max_loc[0] - xmin
        return distance, max_loc[0], max_val

    @staticmethod
    def generate_human_track(distance: float) -> list:
        """Generate human-like mouse movement track with Sigmoid easing and micro-tremors."""
        track = []
        n_points = random.randint(48, 65)
        total_time = random.uniform(0.85, 1.25)

        times = np.linspace(0, 1, n_points)
        k = random.uniform(7.8, 9.6)
        t0 = random.uniform(0.40, 0.46)
        sig = 1 / (1 + np.exp(-k * (times - t0)))
        sig = (sig - sig[0]) / (sig[-1] - sig[0])

        arc_height = random.uniform(-1.2, 1.2)
        y_drift = arc_height * np.sin(np.pi * times) + np.random.normal(0, 0.2, n_points)

        prev_x = 0
        prev_y = 0
        dt_base = total_time / n_points

        for i in range(1, n_points):
            x = distance * sig[i]
            y = y_drift[i]
            dx = x - prev_x
            dy = y - prev_y
            prev_x = x
            prev_y = y
            dt = dt_base * random.uniform(0.85, 1.25)
            track.append((dx, dy, dt))

        return track

    async def _solve_once(self, captcha_id: str, proxy: Optional[str] = None, timeout: float = 20.0) -> Optional[GeeTestResult]:
        handler = functools.partial(QuietHTTPRequestHandler, directory=self.temp_dir)
        httpd = socketserver.TCPServer(("127.0.0.1", 0), handler)
        port = httpd.server_address[1]
        t = threading.Thread(target=httpd.serve_forever)
        t.daemon = True
        t.start()

        result = None
        try:
            async with async_playwright() as p:
                launch_kwargs = {
                    "headless": True,
                    "args": [
                        "--disable-blink-features=AutomationControlled",
                        "--no-sandbox",
                        "--disable-infobars"
                    ]
                }
                browser = await p.chromium.launch(**launch_kwargs)
                context_kwargs = {
                    "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    "viewport": {"width": 1280, "height": 800}
                }
                if proxy:
                    context_kwargs["proxy"] = {"server": proxy}

                context = await browser.new_context(**context_kwargs)
                await context.add_init_script("""
                    Object.defineProperty(navigator, 'webdriver', {
                        get: () => undefined
                    });
                    window.chrome = { runtime: {} };
                """)
                page = await context.new_page()

                await page.goto(f"http://127.0.0.1:{port}/gt4_bridge.html", wait_until="networkidle")
                await page.evaluate(f"initCaptcha('{captcha_id}')")
                await page.wait_for_function("window.gt4Ready === true", timeout=10000)
                await page.evaluate("window.captchaObj.showCaptcha()")
                await asyncio.sleep(2.0)

                btn = await page.wait_for_selector(".geetest_btn", timeout=5000)
                btn_box = await btn.bounding_box()

                dom_info = await page.evaluate("""() => {
                    function cleanUrl(bg) {
                        if (!bg || bg === 'none') return '';
                        let s = bg.trim();
                        if (s.startsWith('url(')) s = s.slice(4);
                        if (s.endsWith(')')) s = s.slice(0, -1);
                        if ((s.startsWith('"') && s.endsWith('"')) || (s.startsWith("'") && s.endsWith("'"))) {
                            s = s.slice(1, -1);
                        }
                        return s;
                    }
                    const bgEl = document.querySelector('.geetest_bg');
                    const sliceEl = document.querySelector('.geetest_slice_bg');
                    return {
                        bgUrl: cleanUrl(window.getComputedStyle(bgEl).backgroundImage),
                        bgRect: bgEl.getBoundingClientRect(),
                        sliceUrl: cleanUrl(window.getComputedStyle(sliceEl).backgroundImage)
                    };
                }""")

                bg_bytes = requests.get(dom_info["bgUrl"]).content
                slice_bytes = requests.get(dom_info["sliceUrl"]).content

                bg_img = Image.open(io.BytesIO(bg_bytes))
                scale = dom_info["bgRect"]["width"] / bg_img.size[0]

                raw_dist, raw_x, score = self.find_slider_gap(slice_bytes, bg_bytes)
                target_dist = raw_dist * scale

                await btn.hover()
                await asyncio.sleep(random.uniform(0.15, 0.25))

                start_x = btn_box["x"] + btn_box["width"] / 2
                start_y = btn_box["y"] + btn_box["height"] / 2

                await page.mouse.down()
                await asyncio.sleep(random.uniform(0.08, 0.12))

                curr_x = start_x
                curr_y = start_y
                track = self.generate_human_track(target_dist)

                for dx, dy, delay in track:
                    curr_x += dx
                    curr_y += dy
                    await page.mouse.move(curr_x, curr_y)
                    await asyncio.sleep(delay)

                await asyncio.sleep(random.uniform(0.12, 0.22))
                await page.mouse.up()

                for _ in range(40):
                    res = await page.evaluate("window.gt4Result")
                    if res:
                        result = GeeTestResult(
                            captcha_id=res.get("captcha_id", captcha_id),
                            lot_number=res["lot_number"],
                            pass_token=res["pass_token"],
                            gen_time=res["gen_time"],
                            captcha_output=res["captcha_output"]
                        )
                        break
                    err = await page.evaluate("window.gt4Error")
                    if err:
                        break
                    await asyncio.sleep(0.1)

                await browser.close()
        finally:
            httpd.shutdown()

        return result

    def solve(self, captcha_id: str = GEETEST_IDS["LOGIN"], proxy: Optional[str] = None, max_retries: int = 3, timeout_per_try: float = 20.0) -> GeeTestResult:
        """Solve GeeTest v4 captcha synchronously with automatic retry."""
        last_err = None
        for attempt in range(1, max_retries + 1):
            try:
                result = asyncio.run(self._solve_once(captcha_id, proxy=proxy, timeout=timeout_per_try))
                if result is not None:
                    return result
            except Exception as e:
                last_err = e

            time.sleep(random.uniform(0.5, 1.0))

        raise RuntimeError(f"安全验证失败（已重试 {max_retries} 次）: {last_err}")
