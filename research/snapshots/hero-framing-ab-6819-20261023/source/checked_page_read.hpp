#pragma once
#include "phase_timing.hpp"
#include <windows.h>
#ifndef PSAPI_VERSION
#define PSAPI_VERSION 2
#endif
#if PSAPI_VERSION < 2
#error This reviewed current-Windows reader requires the Kernel32 PSAPI version.
#endif
#include <psapi.h>
#include <array>
#include <cstring>
#include <cstdint>
namespace citadelcast_memory {
struct ReadCosts {
    std::uint64_t passes=0,requests=0,page_queries=0,range_queries=0,copies=0,rejected=0;
    hero::PhaseCost page,range,copy;
    void write(FILE* out)const{
        std::fprintf(out,"{\"policy\":\"fresh page attributes and current-process copy\",\"passes\":%llu,\"requests\":%llu,\"page_queries\":%llu,\"range_queries\":%llu,\"copies\":%llu,\"rejected\":%llu,",
            static_cast<unsigned long long>(passes),static_cast<unsigned long long>(requests),
            static_cast<unsigned long long>(page_queries),static_cast<unsigned long long>(range_queries),
            static_cast<unsigned long long>(copies),static_cast<unsigned long long>(rejected));
        page.write(out,"page_wall");std::fputs(",",out);range.write(out,"range_wall");
        std::fputs(",",out);copy.write(out,"copy_wall");std::fputs("}",out);
    }
};
inline bool ReadableProtection(DWORD protection){
    return !(protection&(PAGE_NOACCESS|PAGE_GUARD)) &&
        (protection&(PAGE_READONLY|PAGE_READWRITE|PAGE_WRITECOPY|PAGE_EXECUTE_READ|PAGE_EXECUTE_READWRITE|PAGE_EXECUTE_WRITECOPY));
}
// Same-process, bounded read. No persistent metadata or data cache. A copy to
// scratch makes the page resident without exposing bytes; both complete OS copy
// and fresh readable page attributes must pass before publishing any output.
// Querying one page avoids VirtualQuery's scan of a potentially huge heap region.
class CheckedRead {
    ReadCosts* cost_=nullptr;
    static double now(){
        LARGE_INTEGER t{},f{};
        if(!QueryPerformanceFrequency(&f)||!QueryPerformanceCounter(&t)||f.QuadPart<=0)return NAN;
        return static_cast<double>(t.QuadPart)/static_cast<double>(f.QuadPart);
    }
    static std::size_t page_size(){
        static const std::size_t size=[](){SYSTEM_INFO info{};GetSystemInfo(&info);return static_cast<std::size_t>(info.dwPageSize);}();
        return size;
    }
    bool reject(){if(cost_)++cost_->rejected;return false;}
public:
    explicit CheckedRead(ReadCosts* cost=nullptr):cost_(cost){}
    void begin_pass(){if(cost_)++cost_->passes;}
    bool operator()(std::uintptr_t at,void* output,std::size_t size){
        if(cost_)++cost_->requests;
        if(!at||!output||!size||size>64||at>UINTPTR_MAX-(size-1))return reject();
        const auto page=page_size();if(!page)return reject();
        const bool crossing=at/page!=(at+size-1)/page;
        if(crossing){
            // Preserve the original single-region rule for rare crossing
            // fields. Ordinary aligned fields never use this expensive fallback.
            MEMORY_BASIC_INFORMATION info{};const double began=cost_?now():0;
            const bool queried=VirtualQuery(reinterpret_cast<void*>(at),&info,sizeof(info))==sizeof(info);
            if(cost_){++cost_->range_queries;cost_->range.add(began,now());}
            const auto base=reinterpret_cast<std::uintptr_t>(info.BaseAddress);
            if(!queried||info.State!=MEM_COMMIT||!ReadableProtection(info.Protect)||
               at<base||info.RegionSize<size||at-base>info.RegionSize-size)return reject();
        }
        std::array<unsigned char,64> scratch{};SIZE_T copied=0;const double copy_began=cost_?now():0;
        const bool complete=ReadProcessMemory(GetCurrentProcess(),reinterpret_cast<void*>(at),scratch.data(),size,&copied)&&copied==size;
        if(cost_){++cost_->copies;cost_->copy.add(copy_began,now());}
        if(!complete)return reject();
        if(!crossing){
            PSAPI_WORKING_SET_EX_INFORMATION info{};info.VirtualAddress=reinterpret_cast<void*>(at);
            const double began=cost_?now():0;
            const bool queried=QueryWorkingSetEx(GetCurrentProcess(),&info,sizeof(info))!=FALSE;
            if(cost_){++cost_->page_queries;cost_->page.add(began,now());}
            if(!queried||!info.VirtualAttributes.Valid||info.VirtualAttributes.Bad||
               !ReadableProtection(static_cast<DWORD>(info.VirtualAttributes.Win32Protection)))return reject();
        }
        std::memcpy(output,scratch.data(),size);return true;
    }
};
}
