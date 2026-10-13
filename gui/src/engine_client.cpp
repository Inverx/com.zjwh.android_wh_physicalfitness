#include "engine_client.h"

#include <cstdio>
#include <stdexcept>

#if WHS_WINDOWS
#include <windows.h>
#else
#include <csignal>
#include <cstring>
#include <spawn.h>
#include <sys/wait.h>
#include <unistd.h>
extern char** environ;
#endif

using nlohmann::json;

EngineClient::~EngineClient() { stop(); }

bool EngineClient::start(const std::string& program,
                         const std::vector<std::string>& args) {
    if (handle_ != 0) return true;

#if WHS_WINDOWS
    SECURITY_ATTRIBUTES sa{sizeof(sa), nullptr, TRUE};
    HANDLE inR = nullptr, inW = nullptr, outR = nullptr, outW = nullptr;
    if (!CreatePipe(&inR, &inW, &sa, 0) || !CreatePipe(&outR, &outW, &sa, 0)) return false;
    SetHandleInformation(inW, HANDLE_FLAG_INHERIT, 0);
    SetHandleInformation(outR, HANDLE_FLAG_INHERIT, 0);

    std::string cmdline = "\"" + program + "\"";
    for (const auto& a : args) cmdline += " \"" + a + "\"";

    STARTUPINFOA si{};
    si.cb = sizeof(si);
    si.dwFlags = STARTF_USESTDHANDLES;
    si.hStdInput = inR;
    si.hStdOutput = outW;
    si.hStdError = GetStdHandle(STD_ERROR_HANDLE);
    PROCESS_INFORMATION pi{};
    std::vector<char> mutableCmd(cmdline.begin(), cmdline.end());
    mutableCmd.push_back('\0');
    if (!CreateProcessA(nullptr, mutableCmd.data(), nullptr, nullptr, TRUE,
                        CREATE_NO_WINDOW, nullptr, nullptr, &si, &pi)) {
        CloseHandle(inR); CloseHandle(inW); CloseHandle(outR); CloseHandle(outW);
        return false;
    }
    CloseHandle(inR); CloseHandle(outW); CloseHandle(pi.hThread);
    handle_ = pi.hProcess; writeFd_ = inW; readFd_ = outR;
    return true;
#else
    int inPipe[2], outPipe[2];
    if (pipe(inPipe) != 0) return false;
    if (pipe(outPipe) != 0) { close(inPipe[0]); close(inPipe[1]); return false; }

    pid_t pid = fork();
    if (pid < 0) return false;
    if (pid == 0) {
        dup2(inPipe[0], STDIN_FILENO);
        dup2(outPipe[1], STDOUT_FILENO);
        close(inPipe[0]); close(inPipe[1]);
        close(outPipe[0]); close(outPipe[1]);
        std::vector<char*> argv;
        argv.push_back(const_cast<char*>(program.c_str()));
        for (const auto& a : args) argv.push_back(const_cast<char*>(a.c_str()));
        argv.push_back(nullptr);
        execvp(program.c_str(), argv.data());
        _exit(127);
    }
    close(inPipe[0]);
    close(outPipe[1]);
    handle_ = pid;
    writeFd_ = inPipe[1];
    readFd_ = outPipe[0];
    return true;
#endif
}

void EngineClient::stop() {
    if (handle_ == 0) return;
#if WHS_WINDOWS
    CloseHandle((HANDLE)writeFd_);
    CloseHandle((HANDLE)readFd_);
    TerminateProcess((HANDLE)handle_, 0);
    CloseHandle((HANDLE)handle_);
#else
    close(writeFd_);
    close(readFd_);
    kill((pid_t)handle_, SIGTERM);
    waitpid((pid_t)handle_, nullptr, 0);
#endif
    handle_ = 0; writeFd_ = readFd_ = 0;
#if WHS_WINDOWS
    writeFd_ = readFd_ = nullptr;
#else
    writeFd_ = readFd_ = -1;
#endif
}

bool EngineClient::writeLine(const std::string& line) {
    std::string payload = line + "\n";
#if WHS_WINDOWS
    DWORD written = 0;
    return WriteFile((HANDLE)writeFd_, payload.data(), (DWORD)payload.size(), &written,
                     nullptr) && written == payload.size();
#else
    size_t off = 0;
    while (off < payload.size()) {
        ssize_t n = write(writeFd_, payload.data() + off, payload.size() - off);
        if (n <= 0) return false;
        off += (size_t)n;
    }
    return true;
#endif
}

bool EngineClient::readLine(std::string& out) {
    out.clear();
    char ch;
    while (true) {
#if WHS_WINDOWS
        DWORD read = 0;
        if (!ReadFile((HANDLE)readFd_, &ch, 1, &read, nullptr) || read == 0) return !out.empty();
#else
        ssize_t n = read(readFd_, &ch, 1);
        if (n <= 0) return !out.empty();
#endif
        if (ch == '\n') return true;
        out.push_back(ch);
    }
}

json EngineClient::request(const std::string& cmd, const json& params) {
    std::lock_guard<std::mutex> lock(mutex_);
    if (handle_ == 0) throw std::runtime_error("引擎未启动");

    const long long id = nextId_++;
    json req = {{"id", id}, {"cmd", cmd}, {"params", params}};
    if (!writeLine(req.dump())) throw std::runtime_error("写入引擎失败");

    std::string line;
    while (readLine(line)) {
        if (line.empty()) continue;
        json resp;
        try {
            resp = json::parse(line);
        } catch (const json::parse_error&) {
            continue;  // 引擎的诊断输出不会出现在 stdout，这里只做防御
        }
        if (resp.value("id", -1LL) != id) continue;
        if (!resp.value("ok", false)) {
            throw std::runtime_error(resp.value("error", std::string("引擎错误")));
        }
        return resp.value("data", json::object());
    }
    throw std::runtime_error("引擎连接已断开");
}
