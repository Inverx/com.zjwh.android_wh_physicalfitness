#pragma once

// UniDesktop（UDA）可选桥接：Win/Linux 用系统通知/主题；macOS 无 UDA，自动降级为 no-op。
// 切换开关是 CMake 的 -DWITH_UDA（默认 ON，APPLE 下强制 OFF）。

#include <string>

namespace uda_bridge {

// 是否编译期接入了 UDA。
bool available();

// 发一条系统通知（未接入时静默忽略）。
void notify(const std::string& title, const std::string& body);

// 系统主题："dark" / "light" / "unknown"。
std::string theme();

}  // namespace uda_bridge
