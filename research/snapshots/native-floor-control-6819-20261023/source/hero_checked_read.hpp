#pragma once
#include "phase_timing.hpp"
#include <windows.h>
#include <array>
#include <cstring>
#include <cstdint>

namespace hero {
struct ReadCosts {
    std::uint64_t passes=0,requests=0,queries=0,region_hits=0,copies=0,rejected=0;
    PhaseCost query,copy;
    void write(FILE* out)const{
        std::fprintf(out,"{\"passes\":%llu,\"requests\":%llu,\"queries\":%llu,\"region_hits\":%llu,\"copies\":%llu,\"rejected\":%llu,",
            static_cast<unsigned long long>(passes),static_cast<unsigned long long>(requests),
            static_cast<unsigned long long>(queries),static_cast<unsigned long long>(region_hits),
            static_cast<unsigned long long>(copies),static_cast<unsigned long long>(rejected));
        query.write(out,"query_wall");std::fputs(",",out);copy.write(out,"copy_wall");std::fputs("}",out);
    }
};
// Same-process only: no process argument or OpenProcess. Region metadata lasts
// one coherent pass. Field bytes are NEVER cached; the OS checks each complete
// read again. Copy into scratch so a failed/partial read cannot publish output.
// A new pass refreshes every region, including protection and commitment.
class CheckedRead {
    struct Region {std::uintptr_t base=0;std::size_t size=0;};
    std::array<Region,16> regions_{};
    std::size_t used_=0;
    ReadCosts* cost_=nullptr;
    static double now(){
        LARGE_INTEGER t{},f{};
        if(!QueryPerformanceFrequency(&f)||!QueryPerformanceCounter(&t)||f.QuadPart<=0)return NAN;
        return static_cast<double>(t.QuadPart)/static_cast<double>(f.QuadPart);
    }
    static bool contains(const Region& region,std::uintptr_t at,std::size_t size){
        return at>=region.base && region.size>=size && at-region.base<=region.size-size;
    }
    bool reject(){if(cost_)++cost_->rejected;return false;}
public:
    explicit CheckedRead(ReadCosts* cost=nullptr):cost_(cost){}
    void begin_pass(){used_=0;if(cost_)++cost_->passes;}
    bool operator()(std::uintptr_t at,void* output,std::size_t size){
        if(cost_)++cost_->requests;
        // Largest current target field is12bytes;64 is an explicit fixed bound.
        if(!at||!output||!size||size>64||at>UINTPTR_MAX-(size-1))return reject();
        bool known=false;
        for(std::size_t n=0;n<used_;++n)if(contains(regions_[n],at,size)){known=true;break;}
        if(known){if(cost_)++cost_->region_hits;}
        else{
            MEMORY_BASIC_INFORMATION page{};const double began=cost_?now():0;
            const bool queried=VirtualQuery(reinterpret_cast<void*>(at),&page,sizeof(page))==sizeof(page);
            if(cost_){++cost_->queries;cost_->query.add(began,now());}
            if(!queried||page.State!=MEM_COMMIT||(page.Protect&(PAGE_NOACCESS|PAGE_GUARD))||
               !(page.Protect&(PAGE_READONLY|PAGE_READWRITE|PAGE_WRITECOPY|PAGE_EXECUTE_READ|PAGE_EXECUTE_READWRITE|PAGE_EXECUTE_WRITECOPY)))return reject();
            const Region region{reinterpret_cast<std::uintptr_t>(page.BaseAddress),page.RegionSize};
            if(!contains(region,at,size))return reject();
            // Full cache falls back to a fresh query; it never trusts an
            // unvalidated region or refuses an otherwise valid finite read.
            if(used_<regions_.size())regions_[used_++]=region;
        }
        std::array<unsigned char,64> scratch{};SIZE_T copied=0;
        const double began=cost_?now():0;
        const bool complete=ReadProcessMemory(GetCurrentProcess(),reinterpret_cast<void*>(at),scratch.data(),size,&copied)&&copied==size;
        if(cost_){++cost_->copies;cost_->copy.add(began,now());}
        if(!complete){used_=0;return reject();}
        std::memcpy(output,scratch.data(),size);return true;
    }
};
}
