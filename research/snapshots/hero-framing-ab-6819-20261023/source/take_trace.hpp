#pragma once
#include <windows.h>
#include <array>
#include <cmath>
#include <cstdint>
#include <cstdio>

namespace walker_trace {
constexpr unsigned kFrames=16;
struct Frame { const char* module="other";std::uintptr_t rva=0; };
struct Sample {
    bool present=false;
    double elapsed=0;
    float native_start=0,native_now=0;
    int key_index=0;
    bool finished=false;
    std::array<float,7> pose{};
};
struct Exit {
    bool present=false;
    const char* event="none";
    const char* active_type="not sampled";
    unsigned count=0;
    std::array<Frame,kFrames> frames{};
};
inline Frame Classify(std::uintptr_t address,std::uintptr_t module,
                      std::uintptr_t client,std::uintptr_t engine,std::uintptr_t self) {
    if(!module || address<module) return {};
    if(client && module==client) return {"client",address-module};
    if(engine && module==engine) return {"engine",address-module};
    if(self && module==self) return {"adapter",address-module};
    return {};
}
// OS unwinding of this owned callback only, with fixed storage and no debugger,
// external-process reads, native selection changes or per-frame stack walking.
inline Exit Capture(const char* event,const char* active_type,
                    std::uintptr_t client,std::uintptr_t engine,std::uintptr_t self) {
    Exit result;result.present=true;result.event=event;result.active_type=active_type;
    std::array<void*,kFrames> addresses{};
    result.count=CaptureStackBackTrace(1,kFrames,addresses.data(),nullptr);
    if(result.count>kFrames) result.count=kFrames;
    for(unsigned n=0;n<result.count;++n) {
        HMODULE module{};
        if(GetModuleHandleExA(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS|GET_MODULE_HANDLE_EX_FLAG_UNCHANGED_REFCOUNT,
            reinterpret_cast<LPCSTR>(addresses[n]),&module))
            result.frames[n]=Classify(reinterpret_cast<std::uintptr_t>(addresses[n]),
                reinterpret_cast<std::uintptr_t>(module),client,engine,self);
    }
    return result;
}
inline void Number(FILE* out,double value) {
    if(std::isfinite(value)) std::fprintf(out,"%.9g",value);
    else std::fputs("null",out);
}
inline void Write(FILE* out,const Sample& sample,const Exit& exit) {
    std::fprintf(out,",\"take_diagnostic\":{\"sample_present\":%s,\"elapsed\":",
        sample.present?"true":"false");Number(out,sample.elapsed);
    std::fputs(",\"native_start\":",out);Number(out,sample.native_start);
    std::fputs(",\"native_now\":",out);Number(out,sample.native_now);
    std::fprintf(out,",\"native_key_index\":%d,\"native_finished\":%s,\"native_pose_before_adapter\":[",
        sample.key_index,sample.finished?"true":"false");
    for(unsigned n=0;n<sample.pose.size();++n) { if(n)std::fputc(',',out);Number(out,sample.pose[n]); }
    std::fprintf(out,"],\"exit_present\":%s,\"event\":\"%s\",\"active_type_at_exit\":\"%s\",\"frames\":[",
        exit.present?"true":"false",exit.event,exit.active_type);
    for(unsigned n=0;n<exit.count && n<kFrames;++n) {
        if(n)std::fputc(',',out);
        std::fprintf(out,"{\"module\":\"%s\",\"rva\":%llu}",exit.frames[n].module,
            static_cast<unsigned long long>(exit.frames[n].rva));
    }
    std::fputs("]}",out);
}
} // namespace walker_trace
