#pragma once
#include <array>
#include <cmath>
#include <cstdio>
#include <cstdint>
namespace hero_motion {
using Row=std::array<double,27>;
// Only numeric known-root/pose diagnostics; no addresses, pointer traversal,
// camera output or game APIs. The adapter owns gates and sample provenance.
class Trace {
    static constexpr std::size_t capacity_=8192;
    std::array<Row,capacity_> rows_{};
    std::size_t count_=0;
    std::uint64_t dropped_=0,rejected_=0;
    double origin_=0;
    bool enabled_=false,sealed_=true;
public:
    void reset(double origin){count_=0;dropped_=rejected_=0;origin_=origin;enabled_=std::isfinite(origin);sealed_=!enabled_;}
    void stop(){sealed_=true;}
    std::size_t size()const{return count_;}
    std::uint64_t dropped()const{return dropped_;}
    bool append(const Row& input,bool allowed){
        if(!allowed||!enabled_||sealed_){++rejected_;return false;}
        for(double x:input)if(!std::isfinite(x)){++rejected_;return false;}
        Row row=input;row[0]-=origin_;
        if(!std::isfinite(row[0])||row[0]<0||(count_&&row[0]<rows_[count_-1][0])||
           row[1]<1||row[1]>3||std::floor(row[1])!=row[1]||
           row[2]<0||row[2]>31||std::floor(row[2])!=row[2]){++rejected_;return false;}
        if(count_==capacity_){++dropped_;return false;}
        rows_[count_++]=row;return true;
    }
    void write(FILE*out,bool include_rows)const{
        std::fprintf(out,"{\"format\":\"citadelcast-motion-phase-v1\",\"capacity\":8192,\"count\":%llu,\"dropped\":%llu,\"rejected\":%llu,\"rows_included\":%s,\"columns\":[",
            static_cast<unsigned long long>(count_),static_cast<unsigned long long>(dropped_),static_cast<unsigned long long>(rejected_),include_rows?"true":"false");
        constexpr const char* names[]={"time","phase_before","flags","before_root_x","before_root_y","before_root_z","after_root_x","after_root_y","after_root_z","before_camera_x","before_camera_y","before_camera_z","before_pitch","before_yaw","before_roll","after_camera_x","after_camera_y","after_camera_z","after_pitch","after_yaw","after_roll","driven_root_x","driven_root_y","driven_root_z","applied_frames","recenters","entry_elapsed"};
        static_assert(std::size(names)==27);
        for(unsigned n=0;n<27;++n)std::fprintf(out,"%s\"%s\"",n?",":"",names[n]);
        std::fputs("],\"rows\":[",out);
        if(include_rows)for(std::size_t n=0;n<count_;++n){
            std::fputs(n?",[":"[",out);
            for(unsigned k=0;k<27;++k)std::fprintf(out,"%s%.9g",k?",":"",rows_[n][k]);
            std::fputs("]",out);
        }
        std::fputs("]}",out);
    }
};
}
