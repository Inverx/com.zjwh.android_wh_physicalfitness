cmake_minimum_required(VERSION 3.16)
project(whsport_gui LANGUAGES C CXX)

# 跨三平台：Windows / Linux / macOS。
# EUI-NEO 通过 FetchContent 拉取（也可用已安装 SDK：-DEUI_NEO_SDK=/path 走 find_package）。

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

if(NOT CMAKE_BUILD_TYPE AND NOT CMAKE_CONFIGURATION_TYPES)
    set(CMAKE_BUILD_TYPE Release CACHE STRING "" FORCE)
endif()

# 供 clangd / IDE 解析 FetchContent 拉来的 EUI-NEO 头（配合 gui/.clangd）
set(CMAKE_EXPORT_COMPILE_COMMANDS ON)

option(WITH_UDA "接入 UniDesktop SDK（Windows/Linux 通知/托盘；macOS 自动关闭）" ON)
if(APPLE)
    set(WITH_UDA OFF)
endif()

include(FetchContent)

# ── JSON（引擎 JSON-RPC 用）─────────────────────────────────────────────
FetchContent_Declare(json
    GIT_REPOSITORY https://github.com/nlohmann/json.git
    GIT_TAG        v3.11.3
    GIT_SHALLOW    TRUE)
FetchContent_MakeAvailable(json)

# ── EUI-NEO ────────────────────────────────────────────────────────────
if(DEFINED EUI_NEO_SDK)
    find_package(EuiNeo CONFIG REQUIRED)
else()
    FetchContent_Declare(EUI-NEO
        GIT_REPOSITORY https://github.com/sudoevolve/EUI-NEO.git
        GIT_TAG        v0.5.9
        GIT_SHALLOW    TRUE)
    set(EUI_BUILD_APPS      OFF CACHE BOOL "" FORCE)
    set(EUI_BUILD_USER_APPS OFF CACHE BOOL "" FORCE)
    FetchContent_MakeAvailable(EUI-NEO)
endif()

# ── UniDesktop SDK（可选；Rust workspace，用 cargo 构建，不能用 FetchContent）
if(WITH_UDA)
    set(UDA_SOURCE_DIR "${CMAKE_CURRENT_SOURCE_DIR}/3rd/UniDesktop-SDK"
        CACHE PATH "UniDesktop SDK 源码目录")
    if(NOT EXISTS "${UDA_SOURCE_DIR}/crates/uda-ffi/Cargo.toml")
        message(FATAL_ERROR
            "WITH_UDA=ON 需要 UniDesktop SDK 源码：\n"
            "  git clone https://github.com/UniDesktop/SDK '${UDA_SOURCE_DIR}'\n"
            "或用 -DUDA_SOURCE_DIR=/path 指定；也可 -DWITH_UDA=OFF 关闭。")
    endif()
    if(WIN32)
        set(UDA_LIB "${UDA_SOURCE_DIR}/target/release/uda_ffi.dll")
    elseif(APPLE)
        set(UDA_LIB "${UDA_SOURCE_DIR}/target/release/libuda_ffi.dylib")
    else()
        set(UDA_LIB "${UDA_SOURCE_DIR}/target/release/libuda_ffi.so")
    endif()
    add_custom_command(
        OUTPUT "${UDA_LIB}"
        COMMAND cargo build --release -p uda-ffi
        WORKING_DIRECTORY "${UDA_SOURCE_DIR}"
        COMMENT "用 cargo 构建 UniDesktop C-ABI"
        VERBATIM)
    add_custom_target(uda_ffi DEPENDS "${UDA_LIB}")
endif()

# ── 应用 ───────────────────────────────────────────────────────────────
add_executable(whsport_gui
    src/main.cpp
    src/engine_client.cpp
    src/uda_bridge.cpp)

target_include_directories(whsport_gui PRIVATE src)
target_link_libraries(whsport_gui PRIVATE nlohmann_json::nlohmann_json)

if(WIN32)
    target_link_libraries(whsport_gui PRIVATE ws2_32)
    target_compile_definitions(whsport_gui PRIVATE WHS_WINDOWS=1)
else()
    target_compile_definitions(whsport_gui PRIVATE WHS_WINDOWS=0)
endif()

if(WITH_UDA)
    add_dependencies(whsport_gui uda_ffi)
    target_compile_definitions(whsport_gui PRIVATE WHS_HAVE_UDA=1)
    target_include_directories(whsport_gui PRIVATE "${UDA_SOURCE_DIR}/include")
    target_link_libraries(whsport_gui PRIVATE "${UDA_LIB}")
else()
    target_compile_definitions(whsport_gui PRIVATE WHS_HAVE_UDA=0)
endif()

# EUI-NEO：自动加入窗口入口/输入/渲染后端（不要自己写 main 循环源文件）
eui_neo_configure_app(whsport_gui)

# EUI-NEO 在 Release 下默认 -fno-exceptions；本应用在后台线程里用异常做错误分发，
# 异常不会穿过 EUI-NEO 回调边界，所以把自己的目标重新打开异常（后加覆盖先加）。
if(MSVC)
    target_compile_options(whsport_gui PRIVATE /EHsc)
else()
    target_compile_options(whsport_gui PRIVATE -fexceptions)
endif()
