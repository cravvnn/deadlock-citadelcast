#pragma once
#include <algorithm>
#include <cmath>
#include <cstdio>
#include <cstdint>

namespace hero {
struct PhaseCost {
    std::uint64_t count=0;
    double total_ms=0,max_ms=0;
    void add(double began,double ended){
        if(!std::isfinite(began)||!std::isfinite(ended)||ended<began)return;
        const double ms=1000*(ended-began);++count;total_ms+=ms;max_ms=(std::max)(max_ms,ms);
    }
    void write(FILE* out,const char* name)const{
        std::fprintf(out,"\"%s\":{\"count\":%llu,\"total_ms\":%.9g,\"mean_ms\":%.9g,\"max_ms\":%.9g}",name,
            static_cast<unsigned long long>(count),total_ms,count?total_ms/count:0,max_ms);
    }
};
struct PhaseCosts {
    PhaseCost gates,target,native_data,compose,publish,native_manager;
    PhaseCost countdown_gates,countdown_manager,playing_gap,countdown_gap;
    void write(FILE* out)const{
        std::fputs("{",out);gates.write(out,"gates");std::fputs(",",out);target.write(out,"target");
        std::fputs(",",out);native_data.write(out,"native_data");std::fputs(",",out);compose.write(out,"compose");
        std::fputs(",",out);publish.write(out,"publish");std::fputs(",",out);native_manager.write(out,"native_manager_inclusive");
        std::fputs(",",out);countdown_gates.write(out,"countdown_gates");std::fputs(",",out);countdown_manager.write(out,"countdown_native_manager_inclusive");
        std::fputs(",",out);playing_gap.write(out,"frame_gap_playing");std::fputs(",",out);countdown_gap.write(out,"frame_gap_countdown");
        std::fputs("}",out);
    }
};
}
