#include "uda_bridge.h"

#if WHS_HAVE_UDA
#include "uda.h"  // UniDesktop C-ABI（include/uda.h）
#endif

namespace uda_bridge {

bool available() {
#if WHS_HAVE_UDA
    return true;
#else
    return false;
#endif
}

void notify(const std::string& title, const std::string& body) {
#if WHS_HAVE_UDA
    uint32_t id = 0;
    // 失败不打断流程：通知只是锦上添花。
    uda_notify("运动世界校园", title.c_str(), body.c_str(), nullptr, nullptr, &id);
#else
    (void)title;
    (void)body;
#endif
}

std::string theme() {
#if WHS_HAVE_UDA
    int32_t value = UDA_THEME_UNKNOWN;
    if (uda_detect_theme(&value) == UDA_OK) {
        if (value == UDA_THEME_DARK) return "dark";
        if (value == UDA_THEME_LIGHT) return "light";
    }
#endif
    return "unknown";
}

}  // namespace uda_bridge
