// whsport GUI —— EUI-NEO 前端，逻辑仍走 Python 引擎（JSON-RPC）。
// 只在用户点「提交」时才真正发服务器；「预览」纯本地。

#include "eui_neo.h"

#include "engine_client.h"
#include "uda_bridge.h"

#include <functional>
#include <string>
#include <thread>
#include <vector>

namespace app {

namespace {

struct State {
    int tab = 0;
    std::string user;
    std::string pass;
    std::string dist = "2000";
    std::string time = "830";
    std::string steps = "1100";
    std::string weight = "62";
    std::string lat = "43.9423";
    std::string lon = "81.3784";
    bool jitter = true;
    bool policy = true;
    bool busy = false;
    bool toastVisible = false;
    std::string status = "就绪";
    std::string cred = "未登录";
    std::string metrics;
    EngineClient engine;
    bool started = false;
    bool credLoaded = false;
};

State& st() {
    static State instance;
    return instance;
}

// 首次 compose 时按需启动引擎：优先冻结程序，其次 python -m whsport rpc。
void ensureEngine() {
    State& s = st();
    if (s.started) return;
    s.started = true;

    const char* env = std::getenv("WHS_ENGINE");
    const char* py = std::getenv("WHS_PYTHON");
    if (env && *env) {
        s.engine.start(env, {"rpc"});
    } else if (py && *py) {
        s.engine.start(py, {"-m", "whsport", "rpc"});
    } else {
        s.engine.start("whsport-engine", {"rpc"});
        if (!s.engine.running()) s.engine.start("python3", {"-m", "whsport", "rpc"});
    }
}

// 后台执行，回到主线程再用 requestUpdate() 触发重绘。
void runAsync(std::function<void()> work) {
    std::thread([work] {
        try {
            work();
        } catch (const std::exception& exc) {
            st().status = exc.what();
            st().toastVisible = true;
            uda_bridge::notify("出错了", exc.what());
        }
        st().busy = false;
        app::requestUpdate();
    }).detach();
}

void applyCredentials() {
    try {
        auto data = st().engine.request("credentials");
        st().cred = "uid=" + data.value("uid", std::string("-")) +
                    "  " + (data.value("has_token", false) ? "已登录" : "未登录");
    } catch (const std::exception&) {
        st().cred = "引擎未就绪";
    }
}

double num(const std::string& text, double fallback) {
    try {
        return std::stod(text);
    } catch (const std::exception&) {
        return fallback;
    }
}

nlohmann::json runParams() {
    State& s = st();
    return {
        {"distance", num(s.dist, 2000)}, {"duration", (int)num(s.time, 830)},
        {"steps", (int)num(s.steps, 1100)}, {"weight", num(s.weight, 62)},
        {"lat", num(s.lat, 43.9423)}, {"lon", num(s.lon, 81.3784)},
        {"jitter", s.jitter}, {"policy", s.policy},
    };
}

void doPreview() {
    st().busy = true;
    st().status = "预览生成中（本地，不联网）...";
    st().toastVisible = true;
    runAsync([] {
        auto data = st().engine.request("run.preview", runParams());
        auto m = data.value("metrics", nlohmann::json::object());
        char buf[256];
        std::snprintf(buf, sizeof(buf),
                      "距离 %.0f m  用时 %.0f s  步数 %.0f  步频 %.0f  "
                      "配速 %.2f~%.2f  消耗 %.0f 千卡  功率 %.0f W",
                      m.value("distance", 0.0), m.value("time", 0.0),
                      m.value("steps", 0.0), m.value("avg_step_freq", 0.0),
                      m.value("pace_min", 0.0), m.value("pace_max", 0.0),
                      m.value("calorie", 0.0), m.value("power", 0.0));
        st().metrics = buf;
        st().status = "预览完成（未上传）";
        uda_bridge::notify("预览完成", st().status);
    });
}

void doSubmit() {
    st().busy = true;
    st().status = "提交中...";
    st().toastVisible = true;
    runAsync([] {
        auto data = st().engine.request("run.submit", runParams());
        st().status = "提交返回: " + data.value("result", nlohmann::json::object()).dump();
        uda_bridge::notify("提交结果", st().status.substr(0, 120));
    });
}

void doLogin() {
    st().busy = true;
    st().status = "登录中...";
    st().toastVisible = true;
    runAsync([] {
        nlohmann::json params = {{"username", st().user}, {"password", st().pass}};
        auto data = st().engine.request("login", params);
        st().status = "登录成功: uid=" + data.value("uid", std::string("-"));
        applyCredentials();
    });
}

void doQuery(const std::string& cmd) {
    st().busy = true;
    runAsync([cmd] {
        auto data = st().engine.request(cmd, nlohmann::json::object());
        st().metrics = data.dump(2);
        st().status = "查询完成: " + cmd;
    });
}

// 标签 + 输入框。EUI-NEO 的占位符在有值时不可见，所以显式带一个标签。
void field(eui::Ui& ui, const std::string& id, const std::string& label,
           const std::string& value, float width,
           std::function<void(const std::string&)> on_change) {
    ui.column(id).gap(4.0f).content([&] {
        ui.text(id + ".label").text(label).fontSize(13.0f).opacity(0.65f).build();
        components::input(ui, id + ".input")
            .value(value)
            .size(width, 40.0f)
            .onChange(std::move(on_change))
            .build();
    }).build();
}

}  // namespace

const DslAppConfig& dslAppConfig() {
    static const DslAppConfig config = DslAppConfig{}
        .title("运动世界校园 · 工具")
        .pageId("whsport")
        .windowSize(980, 720)
        .textFont("YouSheBiaoTiHei-2.ttf");
    return config;
}

void compose(eui::Ui& ui, const eui::Screen& screen) {
    ensureEngine();
    State& s = st();

    // 首次打开就把开发机/上次登录保存的凭据读出来（后台，不卡首帧）。
    if (!s.credLoaded) {
        s.credLoaded = true;
        runAsync([] { applyCredentials(); });
    }

    ui.column("root")
        .size(screen.width, screen.height)
        .padding(24.0f)
        .gap(14.0f)
        .content([&] {
            ui.text("title").text("运动世界校园").fontSize(26.0f).build();
            ui.text("cred").text(s.cred).fontSize(14.0f).opacity(0.7f).build();

            components::tabs(ui, "tabs")
                .items({"登录", "跑步", "查询"})
                .selected(s.tab)
                .onChange([](int index) { st().tab = index; })
                .build();

            if (s.tab == 0) {
                field(ui, "user", "账号", s.user, 320.0f,
                      [](const std::string& v) { st().user = v; });
                field(ui, "pass", "密码", s.pass, 320.0f,
                      [](const std::string& v) { st().pass = v; });
                components::button(ui, "login").text("登录并保存")
                    .disabled(s.busy).onClick(doLogin).build();
            } else if (s.tab == 1) {
                ui.row("params").gap(12.0f).content([&] {
                    field(ui, "dist", "距离(米)", s.dist, 165.0f,
                          [](const std::string& v) { st().dist = v; });
                    field(ui, "time", "用时(秒)", s.time, 165.0f,
                          [](const std::string& v) { st().time = v; });
                    field(ui, "steps", "步数", s.steps, 165.0f,
                          [](const std::string& v) { st().steps = v; });
                    field(ui, "weight", "体重(kg)", s.weight, 165.0f,
                          [](const std::string& v) { st().weight = v; });
                }).build();
                ui.row("geo").gap(12.0f).content([&] {
                    field(ui, "lat", "纬度", s.lat, 240.0f,
                          [](const std::string& v) { st().lat = v; });
                    field(ui, "lon", "经度", s.lon, 240.0f,
                          [](const std::string& v) { st().lon = v; });
                }).build();
                ui.row("opts").gap(12.0f).content([&] {
                    components::checkbox(ui, "jitter").text("小幅随机")
                        .checked(s.jitter)
                        .onChange([](bool v) { st().jitter = v; }).build();
                    components::checkbox(ui, "policy").text("policy=1")
                        .checked(s.policy)
                        .onChange([](bool v) { st().policy = v; }).build();
                }).build();
                ui.row("run_actions").gap(12.0f).content([&] {
                    components::button(ui, "preview").text("① 预览（本地 dry-run）")
                        .disabled(s.busy).onClick(doPreview).build();
                    components::button(ui, "submit").text("② 提交到服务器")
                        .disabled(s.busy).onClick(doSubmit).build();
                }).build();
            } else {
                ui.row("query_actions").gap(12.0f).content([&] {
                    components::button(ui, "q_score").text("学期成绩")
                        .onClick([] { doQuery("score"); }).build();
                    components::button(ui, "q_policy").text("跑步规则")
                        .onClick([] { doQuery("policy"); }).build();
                    components::button(ui, "q_history").text("历史记录")
                        .onClick([] { doQuery("history"); }).build();
                    components::button(ui, "q_rank").text("排行榜")
                        .onClick([] { doQuery("rank"); }).build();
                }).build();
            }

            if (!s.metrics.empty()) {
                ui.text("metrics_text").text(s.metrics).fontSize(14.0f).build();
            }

            components::toast(ui, "toast")
                .visible(s.toastVisible)
                .title("提示")
                .message(s.status)
                .screen(screen.width, screen.height)
                .build();
        })
        .build();
}

}  // namespace app
