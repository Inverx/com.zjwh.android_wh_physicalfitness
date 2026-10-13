#pragma once

// 与 Python 引擎（`python -m whsport rpc` 或冻结后的 whsport-engine）通信。
// 传输：子进程 stdin/stdout 上的「一行一个 JSON」协议。

#include <mutex>
#include <string>
#include <vector>

#include <nlohmann/json.hpp>

class EngineClient {
public:
    EngineClient() = default;
    ~EngineClient();
    EngineClient(const EngineClient&) = delete;
    EngineClient& operator=(const EngineClient&) = delete;

    // 启动引擎；args 为附加参数（默认 ["-m","whsport","rpc"]）。返回是否成功。
    bool start(const std::string& program, const std::vector<std::string>& args);
    void stop();
    bool running() const { return handle_ != 0; }

    // 同步请求（一次一个，内部加锁）。失败时抛 std::runtime_error。
    nlohmann::json request(const std::string& cmd,
                           const nlohmann::json& params = nlohmann::json::object());

private:
    bool writeLine(const std::string& line);
    bool readLine(std::string& out);

    std::mutex mutex_;
    long long nextId_ = 1;
#if defined(WHS_WINDOWS)
    void* handle_ = nullptr;   // HANDLE
    void* writeFd_ = nullptr;  // HANDLE
    void* readFd_ = nullptr;   // HANDLE
#else
    int handle_ = 0;   // pid
    int writeFd_ = -1;
    int readFd_ = -1;
#endif
};
