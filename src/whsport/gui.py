"""轻量图形界面（Tkinter，仅标准库，无需额外依赖）。

运行：python -m whsport gui   或   wh-gui

设计要点：
* 所有耗时操作（联网/轨迹生成）都在后台线程执行，界面不卡；
* 默认只做「预览（dry-run，纯本地，不联网、不提交）」；
* 「提交」按钮会二次确认，避免误触把数据发到服务器。
"""

from __future__ import annotations

import queue
import threading
import tkinter as tk
import traceback
from tkinter import messagebox, scrolledtext, ttk

from whsport.credentials import resolve, save_credentials

DEFAULT_LAT, DEFAULT_LON = 43.9423, 81.3784


class SportGUI:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("运动世界校园 · 工具")
        self.root.geometry("900x680")
        self._queue: queue.Queue = queue.Queue()
        self._last_points: list = []

        notebook = ttk.Notebook(root)
        notebook.pack(fill="both", expand=True, padx=8, pady=8)
        self._build_run_tab(notebook)
        self._build_query_tab(notebook)
        self._build_log(root)
        self._pump()

    # ── 跑步页 ────────────────────────────────────────────────────────
    def _build_run_tab(self, nb: ttk.Notebook) -> None:
        tab = ttk.Frame(nb)
        nb.add(tab, text="跑步")

        auth = ttk.LabelFrame(tab, text="凭据（已登录过会自动读取本地存档）")
        auth.pack(fill="x", padx=6, pady=6)
        self.var_user = tk.StringVar()
        self.var_pass = tk.StringVar()
        ttk.Label(auth, text="账号").grid(row=0, column=0, sticky="e", padx=4, pady=4)
        ttk.Entry(auth, textvariable=self.var_user, width=22).grid(row=0, column=1, padx=4)
        ttk.Label(auth, text="密码").grid(row=0, column=2, sticky="e", padx=4)
        ttk.Entry(auth, textvariable=self.var_pass, show="*", width=22).grid(row=0, column=3, padx=4)
        ttk.Button(auth, text="登录并保存", command=self._on_login).grid(row=0, column=4, padx=6)
        self.var_cred = tk.StringVar()
        ttk.Label(auth, textvariable=self.var_cred, foreground="#555").grid(
            row=1, column=0, columnspan=5, sticky="w", padx=6, pady=(0, 4))
        self._refresh_cred()

        form = ttk.LabelFrame(tab, text="本次跑步")
        form.pack(fill="x", padx=6, pady=6)
        self.var_type = tk.StringVar(value="1")
        self.var_dist = tk.StringVar(value="2000")
        self.var_time = tk.StringVar(value="830")
        self.var_steps = tk.StringVar(value="1100")
        self.var_weight = tk.StringVar(value="62")
        self.var_lat = tk.StringVar(value=f"{DEFAULT_LAT}")
        self.var_lon = tk.StringVar(value=f"{DEFAULT_LON}")
        self.var_jitter = tk.BooleanVar(value=True)
        self.var_policy = tk.BooleanVar(value=True)

        rows = [
            ("类型", ttk.Combobox(form, textvariable=self.var_type, width=6,
                                 values=("1", "4"), state="readonly"),
             "1=计分跑  4=自由跑"),
            ("距离(米)", ttk.Entry(form, textvariable=self.var_dist, width=10), ""),
            ("用时(秒)", ttk.Entry(form, textvariable=self.var_time, width=10), ""),
            ("步数", ttk.Entry(form, textvariable=self.var_steps, width=10), ""),
            ("体重(kg)", ttk.Entry(form, textvariable=self.var_weight, width=10), ""),
            ("纬度", ttk.Entry(form, textvariable=self.var_lat, width=14), ""),
            ("经度", ttk.Entry(form, textvariable=self.var_lon, width=14), ""),
        ]
        for i, (label, widget, hint) in enumerate(rows):
            ttk.Label(form, text=label).grid(row=i // 2, column=(i % 2) * 3, sticky="e", padx=4, pady=3)
            widget.grid(row=i // 2, column=(i % 2) * 3 + 1, sticky="w", padx=4)
            ttk.Label(form, text=hint, foreground="#777").grid(
                row=i // 2, column=(i % 2) * 3 + 2, sticky="w")

        opts = ttk.Frame(form)
        opts.grid(row=4, column=0, columnspan=6, sticky="w", padx=4, pady=4)
        ttk.Checkbutton(opts, text="距离/用时/步数小幅随机（更自然）",
                        variable=self.var_jitter).pack(side="left", padx=4)
        ttk.Checkbutton(opts, text="policy=1（对齐本账号历史）",
                        variable=self.var_policy).pack(side="left", padx=12)

        actions = ttk.Frame(tab)
        actions.pack(fill="x", padx=6, pady=4)
        ttk.Button(actions, text="① 预览（本地 dry-run，不提交）",
                   command=self._on_preview).pack(side="left", padx=4)
        self.btn_submit = ttk.Button(actions, text="② 提交到服务器",
                                     command=self._on_submit, state="disabled")
        self.btn_submit.pack(side="left", padx=4)
        ttk.Label(actions, text="（必须先生成预览，且提交前会二次确认）",
                  foreground="#999").pack(side="left", padx=8)

        self.canvas = tk.Canvas(tab, height=190, background="white", highlightthickness=1)
        self.canvas.pack(fill="both", expand=True, padx=6, pady=6)

    # ── 查询页 ────────────────────────────────────────────────────────
    def _build_query_tab(self, nb: ttk.Notebook) -> None:
        tab = ttk.Frame(nb)
        nb.add(tab, text="查询")
        bar = ttk.Frame(tab)
        bar.pack(fill="x", padx=6, pady=10)
        for label, kind in (("学期成绩", "score"), ("跑步规则", "policy"),
                            ("历史记录", "history"), ("排行榜", "rank")):
            ttk.Button(bar, text=label, command=lambda k=kind: self._on_query(k)).pack(
                side="left", padx=6)

    # ── 日志区 ────────────────────────────────────────────────────────
    def _build_log(self, root: tk.Tk) -> None:
        frame = ttk.LabelFrame(root, text="输出")
        frame.pack(fill="both", expand=False, padx=8, pady=(0, 8))
        self.log = scrolledtext.ScrolledText(frame, height=13, state="disabled", wrap="word")
        self.log.pack(fill="both", expand=True)

    # ── 基础设施 ──────────────────────────────────────────────────────
    def _log_line(self, msg: str) -> None:
        self.log.configure(state="normal")
        self.log.insert("end", msg + "\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    def _pump(self) -> None:
        try:
            while True:
                kind, payload = self._queue.get_nowait()
                if kind == "log":
                    self._log_line(payload)
                elif kind == "preview":
                    self._draw_track(payload)
                elif kind == "error":
                    self._log_line("错误: " + payload)
                elif kind == "refresh_cred":
                    self._refresh_cred()
                elif kind == "enable_submit":
                    self.btn_submit.configure(state="normal")
        except queue.Empty:
            pass
        self.root.after(120, self._pump)

    def _run_bg(self, fn) -> None:
        def worker():
            try:
                fn()
            except Exception:
                self._queue.put(("error", traceback.format_exc(limit=3)))
        threading.Thread(target=worker, daemon=True).start()

    def _refresh_cred(self) -> None:
        token, uid, unid = resolve()
        self.var_cred.set(
            f"本地凭据: uid={uid or '-'} unid={unid or '-'} "
            f"token={'有' if token else '无'}")

    def _apply_jitter(self, distance, duration, steps):
        import random
        if not self.var_jitter.get():
            return distance, duration, steps
        jr = random.Random()
        distance = float(int(round(distance * jr.uniform(1.005, 1.095))))
        duration = int(round(duration * jr.uniform(0.96, 1.07)))
        steps = int(round(steps * jr.uniform(0.96, 1.07)))
        return distance, duration, steps

    def _read_form(self):
        distance = float(self.var_dist.get())
        duration = int(self.var_time.get())
        steps = int(self.var_steps.get())
        weight = float(self.var_weight.get())
        lat = float(self.var_lat.get())
        lon = float(self.var_lon.get())
        sport_type = int(self.var_type.get())
        distance, duration, steps = self._apply_jitter(distance, duration, steps)
        return distance, duration, steps, weight, lat, lon, sport_type

    # ── 登录 ──────────────────────────────────────────────────────────
    def _on_login(self) -> None:
        user, pwd = self.var_user.get().strip(), self.var_pass.get().strip()
        if not user or not pwd:
            messagebox.showwarning("提示", "请填写账号与密码")
            return

        def job():
            from whsport.sport_client import SportClient
            self._queue.put(("log", "正在登录..."))
            client = SportClient()
            resp = client.login(username=user, password=pwd,
                                progress_callback=lambda m: self._queue.put(("log", m)))
            data = resp.get("data") if isinstance(resp.get("data"), dict) else None
            if resp.get("error") == 10000 and data:
                path = save_credentials(token=data.get("token"), uid=data.get("uid"),
                                        unid=data.get("unid"), username=user)
                self._queue.put(("log", f"登录成功，凭据已保存: {path}"))
                self._queue.put(("refresh_cred", None))
            else:
                self._queue.put(("log", f"登录失败: {resp.get('message')}"))

        self._run_bg(job)

    # ── 预览（纯本地，不联网、不提交）──────────────────────────────────
    def _on_preview(self) -> None:
        try:
            distance, duration, steps, weight, lat, lon, sport_type = self._read_form()
        except ValueError:
            messagebox.showerror("输入错误", "距离/用时/步数/体重/经纬度必须是数字")
            return
        policy = 1 if self.var_policy.get() else 0

        def job():
            import random
            import time as _t

            from whsport.running_protocol import (
                OutdoorRunRecordBuilder,
                generate_synthetic_gps_track,
            )

            self._queue.put(("log", "生成轨迹中（本地，不联网）..."))
            stop = int(_t.time() * 1000)
            start = stop - duration * 1000
            points, five = generate_synthetic_gps_track(
                lat, lon, int(round(distance)), duration, start,
                total_steps=steps, rng=random.Random())
            _, record, _ = OutdoorRunRecordBuilder(
                uid=1, unid=0, sport_type=sport_type,
                sel_distance_m=int(round(distance)), sel_run_time_s=duration,
            ).build_record(int(round(distance)), duration, steps, start, stop,
                           points, five, weight_kg=weight, policy=policy)
            self._last_points = points
            self._queue.put(("preview", [(p.lat, p.lon) for p in points]))
            paces = [1000.0 / (p.speed * 60.0) for p in points if p.speed > 0]
            self._queue.put(("log",
                             f"预览完成（未上传）\n"
                             f"  距离 {record['totalDis']} m  用时 {record['totalTime']} s  "
                             f"步数 {record['totalSteps']}  步频 {record['avgStepFreq']}\n"
                             f"  配速 {min(paces):.2f}~{max(paces):.2f} 分/公里  "
                             f"消耗 {record['calorie']} 千卡  功率 {record['avgPower']} W  "
                             f"爬升 {record['totalAscent']} m"))
            self._queue.put(("enable_submit", None))

        self.btn_submit.configure(state="disabled")
        self._run_bg(job)

    # ── 提交（二次确认）────────────────────────────────────────────────
    def _on_submit(self) -> None:
        if not self._last_points:
            messagebox.showwarning("提示", "请先预览")
            return
        if not messagebox.askyesno(
                "确认提交",
                "将把这条跑步记录提交到服务器（会消耗当日额度）。确定继续吗？"):
            return
        try:
            distance, duration, steps, weight, lat, lon, sport_type = self._read_form()
        except ValueError:
            messagebox.showerror("输入错误", "参数必须是数字")
            return
        token, uid, unid = resolve()
        if not token or not uid:
            messagebox.showerror("未登录", "请先在「跑步」页登录")
            return
        policy = 1 if self.var_policy.get() else 0

        def job():
            from whsport.sport_client import SportClient
            self._queue.put(("log", "正在提交..."))
            client = SportClient(uid=uid, token=token, unid=int(unid or 0))
            res = client.submit_outdoor_run(
                total_distance_m=distance, total_time_sec=duration,
                total_steps=steps, sport_type=sport_type,
                start_lat=lat, start_lon=lon, weight_kg=weight,
                policy=policy)
            self._queue.put(("log", f"提交结果: {res}"))

        self._run_bg(job)

    # ── 查询 ──────────────────────────────────────────────────────────
    def _on_query(self, kind: str) -> None:
        token, uid, unid = resolve()
        if not token or not uid:
            messagebox.showerror("未登录", "请先在「跑步」页登录")
            return

        def job():
            from whsport.sport_client import SportClient
            client = SportClient(uid=uid, token=token, unid=int(unid or 0))
            self._queue.put(("log", f"查询 {kind} ..."))
            if kind == "score":
                sid = 0
                info = client.get_semester_info(1)
                if isinstance(info.get("data"), dict):
                    sid = int(info["data"].get("sid") or 0)
                d = client.get_semester_completed(sid=sid).get("data") or {}
                self._queue.put(("log",
                                 f"学期 {d.get('sname')}  总里程 {d.get('semesterDis')} m  "
                                 f"有效 {d.get('semesterValidDis')} m"))
            elif kind == "policy":
                d = client.get_run_policy(1).get("data") or {}
                r = d.get("runRuleModel") or {}
                self._queue.put(("log",
                                 f"单日上限 {r.get('dayGoal')} m  单次最低 {r.get('minDistance')} m  "
                                 f"配速 {r.get('speedTop')}~{r.get('speedBottom')} 分钟/公里  "
                                 f"步频 {r.get('stepBottom')}~{r.get('stepTop')}"))
            elif kind == "history":
                rows = client.get_run_history(page_num=1, page_size=8, sid=0,
                                              sport_type=1).get("data") or []
                for i, row in enumerate(rows, 1):
                    self._queue.put(("log", f"  {i}. {row.get('totalDis')} m  "
                                            f"{row.get('totalTime')} s"))
            elif kind == "rank":
                d = client.get_main_rank(rank_type=1, sort_type=1, gender=0).get("data")
                self._queue.put(("log", f"排行返回类型: {type(d).__name__}"))

        self._run_bg(job)

    # ── 轨迹绘制 ──────────────────────────────────────────────────────
    def _draw_track(self, lls: list) -> None:
        self.canvas.delete("all")
        if not lls:
            return
        w = self.canvas.winfo_width() or 860
        h = self.canvas.winfo_height() or 190
        lats = [p[0] for p in lls]
        lons = [p[1] for p in lls]
        span_lat = (max(lats) - min(lats)) or 1e-6
        span_lon = (max(lons) - min(lons)) or 1e-6
        scale = min((w - 40) / span_lon, (h - 40) / span_lat)
        pts = [((p[1] - min(lons)) * scale + 20, h - ((p[0] - min(lats)) * scale + 20))
               for p in lls]
        self.canvas.create_line(*[c for xy in pts for c in xy], fill="#1a9e54", width=2,
                                smooth=True)
        self.canvas.create_oval(pts[0][0] - 4, pts[0][1] - 4, pts[0][0] + 4, pts[0][1] + 4,
                                fill="#e08a2b", outline="")


def main() -> None:
    root = tk.Tk()
    SportGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
